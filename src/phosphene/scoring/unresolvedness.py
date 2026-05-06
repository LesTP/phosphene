"""Composite unresolvedness scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from phosphene.memory_store import DensityMetrics, MemoryNote


@dataclass(frozen=True)
class UnresolvednessWeights:
    rising_links: float = 1.0
    reappearance: float = 1.0
    conflicting_alignments: float = 1.0
    survival: float = 1.0


SimilarNote = MemoryNote | tuple[MemoryNote, float]


def compute_unresolvedness(
    note: MemoryNote,
    density_metrics: DensityMetrics,
    similar_notes: Sequence[SimilarNote],
    *,
    weights: UnresolvednessWeights | None = None,
    tier1_base_retention_days: int = 30,
    now: datetime | None = None,
) -> float:
    """Compute a side-effect-free unresolvedness composite in [0.0, 1.0]."""

    del density_metrics
    effective_weights = weights or UnresolvednessWeights()
    components = {
        "rising_links": _rising_links_without_promotion(note),
        "reappearance": _reappearance_signal(similar_notes),
        "conflicting_alignments": _conflicting_alignments(note, similar_notes),
        "survival": _survival_signal(
            note,
            tier1_base_retention_days=tier1_base_retention_days,
            now=now,
        ),
    }
    weighted_sum = (
        components["rising_links"] * max(0.0, effective_weights.rising_links)
        + components["reappearance"] * max(0.0, effective_weights.reappearance)
        + components["conflicting_alignments"]
        * max(0.0, effective_weights.conflicting_alignments)
        + components["survival"] * max(0.0, effective_weights.survival)
    )
    total_weight = (
        max(0.0, effective_weights.rising_links)
        + max(0.0, effective_weights.reappearance)
        + max(0.0, effective_weights.conflicting_alignments)
        + max(0.0, effective_weights.survival)
    )
    if total_weight == 0.0:
        return 0.0
    return _clamp(weighted_sum / total_weight)


def _rising_links_without_promotion(note: MemoryNote) -> float:
    if note.tier != 1:
        return 0.0
    return _clamp(note.link_count / 5.0)


def _reappearance_signal(similar_notes: Sequence[SimilarNote]) -> float:
    unresolved_reappearances = 0
    for similar_note in similar_notes:
        note, similarity = _split_similar_note(similar_note)
        if similarity > 0.7 and note.unresolvedness > 0.3:
            unresolved_reappearances += 1
    return _clamp(unresolved_reappearances / 3.0)


def _conflicting_alignments(
    note: MemoryNote, similar_notes: Sequence[SimilarNote]
) -> float:
    notes_by_id = {
        candidate.note_id: candidate
        for candidate, _similarity in (
            _split_similar_note(similar_note) for similar_note in similar_notes
        )
    }
    connected_notes = [
        connected
        for connected_id, connected in notes_by_id.items()
        if connected_id in note.links or note.note_id in connected.links
    ]

    conflict_count = 0
    for index, left in enumerate(connected_notes):
        for right in connected_notes[index + 1 :]:
            if (
                left.friction_target == right.note_id
                and right.friction_target == left.note_id
            ):
                conflict_count += 1
    return _clamp(conflict_count / 3.0)


def _survival_signal(
    note: MemoryNote, *, tier1_base_retention_days: int, now: datetime | None
) -> float:
    if note.tier != 1 or tier1_base_retention_days <= 0:
        return 0.0
    reference_time = now or datetime.now(tz=note.created_at.tzinfo or timezone.utc)
    created_at = note.created_at
    if created_at.tzinfo is None and reference_time.tzinfo is not None:
        reference_time = reference_time.replace(tzinfo=None)
    days_since_creation = max(0.0, (reference_time - created_at).total_seconds() / 86400)
    return _clamp(days_since_creation / tier1_base_retention_days)


def _split_similar_note(similar_note: SimilarNote) -> tuple[MemoryNote, float]:
    if isinstance(similar_note, tuple):
        note, similarity = similar_note
        return note, float(similarity)
    return similar_note, 1.0


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
