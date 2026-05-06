from datetime import datetime, timedelta, timezone

import pytest

from phosphene.memory_store import DensityMetrics, MemoryNote
from phosphene.scoring import UnresolvednessWeights, compute_unresolvedness


NOW = datetime(2026, 5, 6, tzinfo=timezone.utc)


def note(
    note_id: str = "note-1",
    *,
    tier: int = 1,
    unresolvedness: float = 0.0,
    links: list[str] | None = None,
    friction_target: str | None = None,
    link_count: int = 0,
    created_at: datetime = NOW,
) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content="Body",
        title="Title",
        importance=0.0,
        unresolvedness=unresolvedness,
        links=links or [],
        tags=[],
        source=None,
        friction_target=friction_target,
        embedding=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=created_at,
        updated_at=created_at,
        link_count=link_count,
        decay_deadline=None,
    )


def density_metrics() -> DensityMetrics:
    return DensityMetrics(
        note_count=0,
        tier_counts={},
        mean_link_degree=0.0,
        cluster_count=0,
        unresolved_count=0,
        max_unresolvedness=0.0,
    )


def test_zero_inputs_return_zero() -> None:
    assert compute_unresolvedness(note(), density_metrics(), [], now=NOW) == 0.0


def test_high_link_count_on_tier1_note_raises_composite() -> None:
    score = compute_unresolvedness(
        note(link_count=5),
        density_metrics(),
        [],
        weights=UnresolvednessWeights(
            rising_links=1.0,
            reappearance=0.0,
            conflicting_alignments=0.0,
            survival=0.0,
        ),
        now=NOW,
    )

    assert score == 1.0


def test_promoted_note_has_zero_link_without_promotion_contribution() -> None:
    score = compute_unresolvedness(
        note(tier=2, link_count=5),
        density_metrics(),
        [],
        weights=UnresolvednessWeights(
            rising_links=1.0,
            reappearance=0.0,
            conflicting_alignments=0.0,
            survival=0.0,
        ),
        now=NOW,
    )

    assert score == 0.0


def test_similar_unresolved_notes_raise_reappearance_signal() -> None:
    similar = [
        (note("note-2", unresolvedness=0.4), 0.8),
        (note("note-3", unresolvedness=0.9), 0.95),
        (note("note-4", unresolvedness=0.2), 0.99),
        (note("note-5", unresolvedness=0.8), 0.7),
    ]

    score = compute_unresolvedness(
        note(),
        density_metrics(),
        similar,  # type: ignore[arg-type]
        weights=UnresolvednessWeights(
            rising_links=0.0,
            reappearance=1.0,
            conflicting_alignments=0.0,
            survival=0.0,
        ),
        now=NOW,
    )

    assert score == pytest.approx(2 / 3)


def test_conflicting_connected_notes_raise_alignment_signal() -> None:
    base = note(links=["note-2", "note-3"])
    similar = [
        note("note-2", friction_target="note-3"),
        note("note-3", friction_target="note-2"),
        note("note-4", friction_target="note-2"),
    ]

    score = compute_unresolvedness(
        base,
        density_metrics(),
        similar,
        weights=UnresolvednessWeights(
            rising_links=0.0,
            reappearance=0.0,
            conflicting_alignments=1.0,
            survival=0.0,
        ),
        now=NOW,
    )

    assert score == pytest.approx(1 / 3)


def test_near_decay_deadline_note_raises_survival_signal() -> None:
    score = compute_unresolvedness(
        note(created_at=NOW - timedelta(days=27)),
        density_metrics(),
        [],
        weights=UnresolvednessWeights(
            rising_links=0.0,
            reappearance=0.0,
            conflicting_alignments=0.0,
            survival=1.0,
        ),
        tier1_base_retention_days=30,
        now=NOW,
    )

    assert score == pytest.approx(0.9)


def test_composite_is_clamped_to_unit_interval() -> None:
    score = compute_unresolvedness(
        note(link_count=100, created_at=NOW - timedelta(days=100)),
        density_metrics(),
        [note("note-2", unresolvedness=1.0)] * 10,
        weights=UnresolvednessWeights(
            rising_links=10.0,
            reappearance=10.0,
            conflicting_alignments=10.0,
            survival=10.0,
        ),
        tier1_base_retention_days=30,
        now=NOW,
    )

    assert 0.0 <= score <= 1.0


def test_custom_weights_shift_the_composite() -> None:
    base = note(link_count=5)

    rising_only = compute_unresolvedness(
        base,
        density_metrics(),
        [],
        weights=UnresolvednessWeights(
            rising_links=1.0,
            reappearance=0.0,
            conflicting_alignments=0.0,
            survival=0.0,
        ),
        now=NOW,
    )
    survival_only = compute_unresolvedness(
        base,
        density_metrics(),
        [],
        weights=UnresolvednessWeights(
            rising_links=0.0,
            reappearance=0.0,
            conflicting_alignments=0.0,
            survival=1.0,
        ),
        now=NOW,
    )

    assert rising_only == 1.0
    assert survival_only == 0.0
