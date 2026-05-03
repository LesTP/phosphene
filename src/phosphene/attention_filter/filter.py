"""Attention Filter entry point."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any, Protocol

from phosphene.memory_store import DensityMetrics

from phosphene.attention_filter.types import (
    AttentionFilterConfig,
    ContentItem,
    FilterResult,
    ScoringConfig,
)

PHASE2_SCORE_WEIGHTS: tuple[tuple[str, str], ...] = (
    ("liminality", "liminality_weight"),
    ("friction", "friction_weight"),
    ("unexpected_connection", "unexpected_connection_weight"),
    ("structural_insight", "structural_insight_weight"),
    ("link_density", "link_density_weight"),
    ("cluster_novelty", "cluster_novelty_weight"),
    ("unresolvedness_affinity", "unresolvedness_affinity_weight"),
)


class _EmbeddingCallable(Protocol):
    def __call__(self, texts: list[str], config: object) -> Any: ...


def _toolkit_embed(texts: list[str], config: object) -> Any:
    from toolkit.embedding import embed

    return embed(texts, config)


def _embed_content(
    content: str,
    config: AttentionFilterConfig,
    *,
    embedding_callable: _EmbeddingCallable = _toolkit_embed,
) -> object:
    """Embed one content item through the toolkit boundary."""

    result = embedding_callable([content], config.embedding_config)
    return result.vectors[0]


def _clamp_probability(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _normalized_similarities(similarities: Sequence[float]) -> list[float]:
    return [_clamp_probability(similarity) for similarity in similarities]


def phase2_is_active(metrics: DensityMetrics, config: AttentionFilterConfig) -> bool:
    """Return whether memory density has crossed the Phase 2 triple gate."""

    density_activation_threshold = config.density_crossover * 0.5
    return (
        metrics.note_count >= config.scoring.note_count_threshold
        and metrics.cluster_count >= config.scoring.cluster_count_threshold
        and metrics.mean_link_degree >= density_activation_threshold
    )


def compute_blend_weights(
    metrics: DensityMetrics, config: AttentionFilterConfig
) -> tuple[float, float]:
    """Compute prompt and structure weights from current memory density."""

    if not phase2_is_active(metrics, config):
        return 1.0, 0.0

    ramp_start = config.density_crossover * 0.5
    ramp_end = config.density_crossover * 2.0
    ramp_progress = (metrics.mean_link_degree - ramp_start) / (ramp_end - ramp_start)
    capped_progress = min(max(ramp_progress, 0.0), 1.0)
    structure_weight = capped_progress * config.scoring.phase2_max_weight
    prompt_weight = 1.0 - structure_weight
    return prompt_weight, structure_weight


def score_liminality(
    text_sims_to_centroids: Sequence[float], gap_factor_exponent: float = 2.0
) -> float:
    """Score whether text sits between at least two existing clusters."""

    similarities = sorted(_normalized_similarities(text_sims_to_centroids), reverse=True)
    if len(similarities) < 2:
        return 0.0

    max_sim = similarities[0]
    second_sim = similarities[1]
    if max_sim == 0.0:
        gap_factor = 0.0
    else:
        gap_factor = ((max_sim - second_sim) / max_sim) ** max(gap_factor_exponent, 0.0)

    return _clamp_probability(1.0 - (max_sim * gap_factor))


def score_friction(topical_sim: float, assertion_alignment: float) -> float:
    """Score topical similarity multiplied by assertion misalignment."""

    return _clamp_probability(
        _clamp_probability(topical_sim) * (1.0 - _clamp_probability(assertion_alignment))
    )


def _pairwise_cluster_similarity(
    cluster_pairwise_sims: Mapping[tuple[int, int], float] | Sequence[Sequence[float]],
    left_index: int,
    right_index: int,
) -> float:
    if isinstance(cluster_pairwise_sims, Mapping):
        value = cluster_pairwise_sims.get((left_index, right_index))
        if value is None:
            value = cluster_pairwise_sims.get((right_index, left_index), 0.0)
        return _clamp_probability(value)

    if left_index >= len(cluster_pairwise_sims):
        return 0.0

    row = cluster_pairwise_sims[left_index]
    if right_index >= len(row):
        return 0.0

    return _clamp_probability(row[right_index])


def score_unexpected_connection(
    text_sims_to_centroids: Sequence[float],
    cluster_pairwise_sims: Mapping[tuple[int, int], float] | Sequence[Sequence[float]],
) -> float:
    """Score the strongest bridge between two mutually distant clusters."""

    similarities = _normalized_similarities(text_sims_to_centroids)
    if len(similarities) < 2:
        return 0.0

    best_score = 0.0
    for left_index, right_index in combinations(range(len(similarities)), 2):
        bridge_strength = min(similarities[left_index], similarities[right_index])
        cluster_distance = 1.0 - _pairwise_cluster_similarity(
            cluster_pairwise_sims, left_index, right_index
        )
        best_score = max(best_score, bridge_strength * cluster_distance)

    return _clamp_probability(best_score)


def score_structural_insight(text_sim_to_meta_cluster: float) -> float:
    """Pass through similarity to the meta-cluster of Tier 2 summaries."""

    return _clamp_probability(text_sim_to_meta_cluster)


def score_link_density(
    note_similarities: Sequence[float],
    threshold: float,
    similarity_candidates: int | None = None,
) -> float:
    """Score how many candidate notes clear the configured similarity threshold."""

    candidate_count = (
        similarity_candidates if similarity_candidates is not None else len(note_similarities)
    )
    if candidate_count <= 0:
        return 0.0

    connected_count = sum(1 for similarity in note_similarities if similarity > threshold)
    return _clamp_probability(connected_count / candidate_count)


def score_cluster_novelty(text_sims_to_centroids: Sequence[float]) -> float:
    """Score distance from all known cluster centroids."""

    similarities = _normalized_similarities(text_sims_to_centroids)
    if not similarities:
        return 1.0

    return _clamp_probability(1.0 - max(similarities))


def score_unresolvedness_affinity(
    note_similarities: Sequence[float], note_unresolvedness_scores: Sequence[float]
) -> float:
    """Score similarity-weighted engagement with unresolved notes."""

    weighted_sum = sum(
        _clamp_probability(similarity) * _clamp_probability(unresolvedness)
        for similarity, unresolvedness in zip(note_similarities, note_unresolvedness_scores)
    )
    return _clamp_probability(weighted_sum)


def compute_phase2_composite(
    scores: Mapping[str, float], scoring_config: ScoringConfig
) -> float:
    """Compute weighted average across available Phase 2 geometric scores."""

    weighted_sum = 0.0
    total_weight = 0.0
    for score_name, weight_field in PHASE2_SCORE_WEIGHTS:
        if score_name not in scores:
            continue

        weight = getattr(scoring_config, weight_field)
        if weight == 0.0:
            continue

        weighted_sum += _clamp_probability(scores[score_name]) * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return _clamp_probability(weighted_sum / total_weight)


class AttentionFilter:
    """Personality-driven content selector.

    Full scoring and annotation behavior is implemented in later Attention
    Filter phases; this scaffold establishes the ARCH-defined constructor.
    """

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def filter_content(
        self, items: list[ContentItem], config: AttentionFilterConfig
    ) -> FilterResult:
        density_snapshot = self.memory_store.get_density_metrics()
        prompt_weight, structure_weight = compute_blend_weights(density_snapshot, config)

        if not items:
            return FilterResult(
                accepted=[],
                rejected_count=0,
                total_count=0,
                prompt_weight=prompt_weight,
                structure_weight=structure_weight,
                density_snapshot=density_snapshot,
            )

        raise NotImplementedError(
            "AttentionFilter.filter_content for non-empty batches is implemented in a later phase"
        )
