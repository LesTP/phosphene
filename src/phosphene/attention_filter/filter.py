"""Attention Filter entry point."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _SimilarNoteContext:
    note_id: str
    similarity: float
    unresolvedness: float
    metadata: Mapping[str, object]


@dataclass(frozen=True)
class _ItemRetrievalContext:
    item: ContentItem
    embedding: object
    similar_notes: tuple[_SimilarNoteContext, ...]

    @property
    def note_ids(self) -> list[str]:
        return [note.note_id for note in self.similar_notes]

    @property
    def similarities(self) -> list[float]:
        return [note.similarity for note in self.similar_notes]

    @property
    def unresolvedness_scores(self) -> list[float]:
        return [note.unresolvedness for note in self.similar_notes]


@dataclass(frozen=True)
class _MemoryStructuralEvaluation:
    scores: Mapping[str, float]
    structure_score: float
    connections: tuple[str, ...]
    friction_target: str | None


@dataclass(frozen=True)
class _ItemEvaluation:
    retrieval: _ItemRetrievalContext
    structural: _MemoryStructuralEvaluation
    prompt_weight: float
    structure_weight: float


def _toolkit_embed(texts: list[str], config: object) -> Any:
    from toolkit.embedding import embed

    return embed(texts, config)


def _embed_content(
    content: str,
    config: AttentionFilterConfig,
    *,
    embedding_callable: _EmbeddingCallable | None = None,
) -> object:
    """Embed one content item through the toolkit boundary."""

    if embedding_callable is None:
        embedding_callable = _toolkit_embed

    result = embedding_callable([content], config.embedding_config)
    return result.vectors[0]


def _normalize_similar_note(note: object, similarity: float) -> _SimilarNoteContext:
    return _SimilarNoteContext(
        note_id=str(getattr(note, "note_id")),
        similarity=float(similarity),
        unresolvedness=float(getattr(note, "unresolvedness")),
        metadata={
            "tier": getattr(note, "tier"),
            "title": getattr(note, "title"),
            "importance": getattr(note, "importance"),
            "link_count": getattr(note, "link_count"),
            "tags": list(getattr(note, "tags")),
            "source": getattr(note, "source"),
            "friction_target": getattr(note, "friction_target"),
            "cluster_group": getattr(note, "cluster_group"),
        },
    )


def _retrieve_similar_notes(
    memory_store: object, embedding: object, config: AttentionFilterConfig
) -> tuple[_SimilarNoteContext, ...]:
    results = memory_store.search_by_embedding(
        embedding,
        limit=config.similarity_candidates,
    )
    return tuple(
        _normalize_similar_note(note, similarity) for note, similarity in results
    )


def _prepare_retrieval_contexts(
    memory_store: object,
    items: Sequence[ContentItem],
    config: AttentionFilterConfig,
    *,
    embedding_callable: _EmbeddingCallable | None = None,
) -> list[_ItemRetrievalContext]:
    contexts: list[_ItemRetrievalContext] = []
    for item in items:
        embedding = _embed_content(
            item.content,
            config,
            embedding_callable=embedding_callable,
        )
        similar_notes = _retrieve_similar_notes(memory_store, embedding, config)
        contexts.append(
            _ItemRetrievalContext(
                item=item,
                embedding=embedding,
                similar_notes=similar_notes,
            )
        )

    return contexts


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


def _compute_memory_structural_evaluation(
    context: _ItemRetrievalContext, config: AttentionFilterConfig
) -> _MemoryStructuralEvaluation:
    """Compute pre-cache structural signals from Memory Store retrieval context."""

    threshold = config.scoring.link_density_sim_threshold
    connections = tuple(
        note.note_id for note in context.similar_notes if note.similarity > threshold
    )
    scores = {
        "link_density": score_link_density(
            context.similarities,
            threshold=threshold,
            similarity_candidates=config.similarity_candidates,
        ),
        "unresolvedness_affinity": score_unresolvedness_affinity(
            context.similarities,
            context.unresolvedness_scores,
        ),
    }

    weighted_sum = (
        scores["link_density"] * config.scoring.link_density_weight
        + scores["unresolvedness_affinity"]
        * config.scoring.unresolvedness_affinity_weight
    )
    total_weight = (
        config.scoring.link_density_weight
        + config.scoring.unresolvedness_affinity_weight
    )
    structure_score = (
        _clamp_probability(weighted_sum / total_weight)
        if total_weight > 0.0
        else 0.0
    )

    return _MemoryStructuralEvaluation(
        scores=scores,
        structure_score=structure_score,
        connections=connections,
        friction_target=None,
    )


def _evaluate_items_non_llm(
    memory_store: object,
    items: Sequence[ContentItem],
    config: AttentionFilterConfig,
    *,
    prompt_weight: float,
    structure_weight: float,
    embedding_callable: _EmbeddingCallable | None = None,
) -> list[_ItemEvaluation]:
    """Prepare deterministic per-item context before LLM scoring exists."""

    retrieval_contexts = _prepare_retrieval_contexts(
        memory_store,
        items,
        config,
        embedding_callable=embedding_callable,
    )
    return [
        _ItemEvaluation(
            retrieval=context,
            structural=_compute_memory_structural_evaluation(context, config),
            prompt_weight=prompt_weight,
            structure_weight=structure_weight,
        )
        for context in retrieval_contexts
    ]


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

        _evaluate_items_non_llm(
            self.memory_store,
            items,
            config,
            prompt_weight=prompt_weight,
            structure_weight=structure_weight,
        )
        return FilterResult(
            accepted=[],
            rejected_count=0,
            total_count=len(items),
            prompt_weight=prompt_weight,
            structure_weight=structure_weight,
            density_snapshot=density_snapshot,
        )
