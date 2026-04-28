from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

import phosphene.memory_store.store as store_module
from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteNotFoundError
from phosphene.memory_store.types import MemoryNote
from phosphene.memory_store.vault import note_path, serialize_note


def make_store(tmp_path: Path, *, embeddings: bool = False) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if embeddings else None,
            tier1_base_retention_days=30,
            tier1_extended_retention_days=90,
            tier2_cycle_window_days=30,
            link_density_threshold=2,
        )
    )


def make_note(
    note_id: str,
    *,
    tier: int = 1,
    created_at: datetime,
    links: list[str] | None = None,
    attractor_relevance: float | None = None,
    supersedes: str | None = None,
    decay_deadline: datetime | None = None,
) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"{note_id} body",
        title=note_id.title(),
        importance=0.5,
        unresolvedness=0.2,
        links=list(links or []),
        tags=[],
        source=None,
        friction_target=None,
        embedding=None,
        attractor_relevance=attractor_relevance,
        cluster_group=None,
        supersedes=supersedes,
        created_at=created_at,
        updated_at=created_at,
        link_count=len(links or []),
        decay_deadline=decay_deadline,
    )


def write_note(vault_path: Path, note: MemoryNote) -> None:
    path = note_path(vault_path, note.tier, note.note_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_note(note), encoding="utf-8")


def seed_store(tmp_path: Path, notes: list[MemoryNote], *, embeddings: bool = False) -> MemoryStore:
    vault_path = tmp_path / "vault"
    for note in notes:
        write_note(vault_path, note)

    embedding_path = tmp_path / "embeddings"
    if embeddings:
        embedding_path.mkdir(parents=True, exist_ok=True)
        for note in notes:
            np.save(embedding_path / f"{note.note_id}.npy", np.array([1.0, 2.0]))

    return make_store(tmp_path, embeddings=embeddings)


def days_ago(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def test_run_decay_empty_vault_returns_empty_report(tmp_path: Path) -> None:
    report = make_store(tmp_path).run_decay()

    assert report.expired_count == 0
    assert report.expired_ids == []
    assert report.extended_count == 0
    assert report.tier_breakdown == {1: 0, 2: 0, 3: 0}


def test_tier_one_note_past_base_retention_without_inbound_expires(tmp_path: Path) -> None:
    expired = make_note("expired", created_at=days_ago(31))
    store = seed_store(tmp_path, [expired], embeddings=True)
    markdown_path = tmp_path / "vault" / "tier1" / "expired.md"
    embedding_path = tmp_path / "embeddings" / "expired.npy"

    report = store.run_decay()

    assert report.expired_count == 1
    assert report.expired_ids == ["expired"]
    assert report.tier_breakdown == {1: 1, 2: 0, 3: 0}
    assert not markdown_path.exists()
    assert not embedding_path.exists()
    with pytest.raises(NoteNotFoundError):
        store.get_note("expired")


def test_tier_one_note_past_base_with_link_threshold_survives_as_extended(
    tmp_path: Path,
) -> None:
    target = make_note("target", created_at=days_ago(31))
    source_a = make_note("source-a", created_at=days_ago(1), links=["target"])
    source_b = make_note("source-b", created_at=days_ago(1), links=["target"])
    store = seed_store(tmp_path, [target, source_a, source_b])

    report = store.run_decay()

    assert report.expired_count == 0
    assert report.extended_count == 1
    assert store.get_note("target").note_id == "target"


def test_tier_one_note_past_extended_retention_with_link_threshold_expires(
    tmp_path: Path,
) -> None:
    target = make_note("target", created_at=days_ago(91))
    source_a = make_note("source-a", created_at=days_ago(1), links=["target"])
    source_b = make_note("source-b", created_at=days_ago(1), links=["target"])
    store = seed_store(tmp_path, [target, source_a, source_b])

    report = store.run_decay()

    assert report.expired_ids == ["target"]
    assert report.extended_count == 0


def test_attractor_relevance_extends_tier_one_retention_window(tmp_path: Path) -> None:
    target = make_note("target", created_at=days_ago(120), attractor_relevance=1.0)
    source_a = make_note("source-a", created_at=days_ago(1), links=["target"])
    source_b = make_note("source-b", created_at=days_ago(1), links=["target"])
    store = seed_store(tmp_path, [target, source_a, source_b])

    report = store.run_decay()

    assert report.expired_count == 0
    assert report.extended_count == 1
    assert store.get_note("target").note_id == "target"


def test_note_at_exact_retention_boundary_is_not_expired(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc)
    note = make_note("boundary", created_at=now - timedelta(days=30))
    store = seed_store(tmp_path, [note])

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[no-untyped-def]
            return now if tz is not None else now.replace(tzinfo=None)

    monkeypatch.setattr(store_module, "datetime", FixedDatetime)

    report = store.run_decay()

    assert report.expired_ids == []
    assert store.get_note("boundary").note_id == "boundary"


def test_report_expired_ids_match_deleted_set_and_index(tmp_path: Path) -> None:
    expired_a = make_note("expired-a", created_at=days_ago(31))
    expired_b = make_note("expired-b", created_at=days_ago(40))
    survivor = make_note("survivor", created_at=days_ago(1))
    store = seed_store(tmp_path, [expired_a, expired_b, survivor])

    report = store.run_decay()

    assert set(report.expired_ids) == {"expired-a", "expired-b"}
    assert {entry.note_id for entry in store.get_index()} == {"survivor"}


def test_rerunning_decay_after_sweep_is_noop(tmp_path: Path) -> None:
    store = seed_store(tmp_path, [make_note("expired", created_at=days_ago(31))])

    first = store.run_decay()
    second = store.run_decay()

    assert first.expired_ids == ["expired"]
    assert second.expired_count == 0
    assert second.expired_ids == []
    assert second.extended_count == 0


def test_expired_embedding_sidecars_removed_and_survivor_sidecars_remain(
    tmp_path: Path,
) -> None:
    expired = make_note("expired", created_at=days_ago(31))
    survivor = make_note("survivor", created_at=days_ago(1))
    store = seed_store(tmp_path, [expired, survivor], embeddings=True)

    store.run_decay()

    assert not (tmp_path / "embeddings" / "expired.npy").exists()
    assert (tmp_path / "embeddings" / "survivor.npy").exists()


def test_tier_two_note_older_than_two_cycle_windows_expires(tmp_path: Path) -> None:
    expired = make_note("expired-tier-two", tier=2, created_at=days_ago(61))
    store = seed_store(tmp_path, [expired])

    report = store.run_decay()

    assert report.expired_ids == ["expired-tier-two"]
    assert report.tier_breakdown == {1: 0, 2: 1, 3: 0}
    with pytest.raises(NoteNotFoundError):
        store.get_note("expired-tier-two")


def test_tier_two_note_inside_cycle_window_survives_without_links(tmp_path: Path) -> None:
    survivor = make_note("survivor-tier-two", tier=2, created_at=days_ago(59))
    store = seed_store(tmp_path, [survivor])

    report = store.run_decay()

    assert report.expired_ids == []
    assert store.get_note("survivor-tier-two").note_id == "survivor-tier-two"


def test_tier_two_expiry_ignores_inbound_links_and_attractor_relevance(
    tmp_path: Path,
) -> None:
    expired = make_note(
        "expired-tier-two",
        tier=2,
        created_at=days_ago(61),
        attractor_relevance=1.0,
    )
    source_a = make_note("source-a", created_at=days_ago(1), links=["expired-tier-two"])
    source_b = make_note("source-b", created_at=days_ago(1), links=["expired-tier-two"])
    store = seed_store(tmp_path, [expired, source_a, source_b])

    report = store.run_decay()

    assert report.expired_ids == ["expired-tier-two"]
    assert report.extended_count == 0


def test_tier_three_superseded_note_past_decay_deadline_expires_and_chain_literal_remains(
    tmp_path: Path,
) -> None:
    old = make_note(
        "old-personality",
        tier=3,
        created_at=days_ago(100),
        decay_deadline=days_ago(1),
    )
    new = make_note(
        "new-personality",
        tier=3,
        created_at=days_ago(1),
        supersedes="old-personality",
    )
    store = seed_store(tmp_path, [old, new])

    report = store.run_decay()

    assert report.expired_ids == ["old-personality"]
    assert report.tier_breakdown == {1: 0, 2: 0, 3: 1}
    assert store.get_note("new-personality").supersedes == "old-personality"
    assert {entry.note_id for entry in store.get_index()} == {"new-personality"}


def test_tier_three_superseded_note_before_decay_deadline_survives(tmp_path: Path) -> None:
    old = make_note(
        "old-personality",
        tier=3,
        created_at=days_ago(100),
        decay_deadline=datetime.now(timezone.utc) + timedelta(days=1),
    )
    new = make_note(
        "new-personality",
        tier=3,
        created_at=days_ago(1),
        supersedes="old-personality",
    )
    store = seed_store(tmp_path, [old, new])

    report = store.run_decay()

    assert report.expired_ids == []
    assert {entry.note_id for entry in store.get_index()} == {
        "old-personality",
        "new-personality",
    }


def test_tier_three_current_note_never_expires_without_decay_deadline(tmp_path: Path) -> None:
    current = make_note("current-personality", tier=3, created_at=days_ago(1000))
    store = seed_store(tmp_path, [current])

    report = store.run_decay()

    assert report.expired_ids == []
    assert store.get_note("current-personality").note_id == "current-personality"


def test_mixed_tier_decay_reports_union_and_breakdown(tmp_path: Path) -> None:
    tier1 = make_note("tier-one-expired", created_at=days_ago(31))
    tier2 = make_note("tier-two-expired", tier=2, created_at=days_ago(61))
    tier3 = make_note(
        "tier-three-expired",
        tier=3,
        created_at=days_ago(100),
        decay_deadline=days_ago(1),
    )
    survivor = make_note("survivor", created_at=days_ago(1))
    store = seed_store(tmp_path, [tier1, tier2, tier3, survivor])

    report = store.run_decay()

    assert set(report.expired_ids) == {
        "tier-one-expired",
        "tier-two-expired",
        "tier-three-expired",
    }
    assert report.expired_count == 3
    assert report.tier_breakdown == {1: 1, 2: 1, 3: 1}


def test_extended_count_only_counts_tier_one_extensions(tmp_path: Path) -> None:
    tier1_target = make_note("tier-one-target", created_at=days_ago(31))
    tier1_source_a = make_note("tier-one-source-a", created_at=days_ago(1), links=["tier-one-target"])
    tier1_source_b = make_note("tier-one-source-b", created_at=days_ago(1), links=["tier-one-target"])
    tier2 = make_note(
        "tier-two-expired",
        tier=2,
        created_at=days_ago(61),
        attractor_relevance=1.0,
    )
    tier2_source_a = make_note("tier-two-source-a", created_at=days_ago(1), links=["tier-two-expired"])
    tier2_source_b = make_note("tier-two-source-b", created_at=days_ago(1), links=["tier-two-expired"])
    tier3 = make_note(
        "tier-three-expired",
        tier=3,
        created_at=days_ago(100),
        decay_deadline=days_ago(1),
    )
    store = seed_store(
        tmp_path,
        [
            tier1_target,
            tier1_source_a,
            tier1_source_b,
            tier2,
            tier2_source_a,
            tier2_source_b,
            tier3,
        ],
    )

    report = store.run_decay()

    assert report.extended_count == 1
    assert set(report.expired_ids) == {"tier-two-expired", "tier-three-expired"}


def test_density_metrics_reflect_decay_sweep(tmp_path: Path) -> None:
    expired = make_note("tier-two-expired", tier=2, created_at=days_ago(61))
    survivor = make_note("tier-three-survivor", tier=3, created_at=days_ago(1000))
    store = seed_store(tmp_path, [expired, survivor])

    store.run_decay()
    metrics = store.get_density_metrics()

    assert metrics.note_count == 1
    assert metrics.tier_counts == {1: 0, 2: 0, 3: 1}
