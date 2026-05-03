"""Attention Filter entry point."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Protocol

from phosphene.attention_filter.errors import InvalidScoreError
from phosphene.memory_store import DensityMetrics

from phosphene.attention_filter.types import (
    AttentionFilterConfig,
    ContentItem,
    FilterCriterion,
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


class _LLMCompleteCallable(Protocol):
    def __call__(
        self,
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str: ...


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
class _IncomingAssertion:
    text: str
    confidence: float


@dataclass(frozen=True)
class _ItemEvaluation:
    retrieval: _ItemRetrievalContext
    structural: _MemoryStructuralEvaluation
    prompt_scores: Mapping[str, float]
    prompt_score: float
    incoming_assertions: tuple[_IncomingAssertion, ...]
    composite_score: float
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


def _toolkit_complete(
    *,
    messages: list[Mapping[str, str]],
    config: object,
    tier: object,
) -> str:
    from toolkit.llm_client import Message, complete

    toolkit_messages = [
        Message(role=message["role"], content=message["content"]) for message in messages
    ]
    response = complete(messages=toolkit_messages, config=config, tier=tier)
    return str(response.content)


def _normalize_similar_note(note: object, similarity: float) -> _SimilarNoteContext:
    metadata = {
        "tier": getattr(note, "tier"),
        "title": getattr(note, "title"),
        "importance": getattr(note, "importance"),
        "link_count": getattr(note, "link_count"),
        "tags": list(getattr(note, "tags")),
        "source": getattr(note, "source"),
        "friction_target": getattr(note, "friction_target"),
        "cluster_group": getattr(note, "cluster_group"),
    }
    if hasattr(note, "content"):
        metadata["content"] = getattr(note, "content")

    return _SimilarNoteContext(
        note_id=str(getattr(note, "note_id")),
        similarity=float(similarity),
        unresolvedness=float(getattr(note, "unresolvedness")),
        metadata=metadata,
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


def _build_prompt_scoring_request(
    context: _ItemRetrievalContext,
    criteria: Sequence[FilterCriterion],
) -> list[Mapping[str, str]]:
    """Build the Phase 1 criterion-scoring request for toolkit/llm_client."""

    payload = {
        "task": "score_attention_filter_prompt_criteria",
        "instructions": (
            "Score each criterion for the incoming content. Return only JSON "
            'with shape {"scores": {"criterion_name": 0.0}}. Scores must be '
            "numbers between 0.0 and 1.0."
        ),
        "criteria": [
            {
                "name": criterion.name,
                "description": criterion.description,
                "weight": criterion.weight,
            }
            for criterion in criteria
        ],
        "content_item": {
            "content": context.item.content,
            "source": context.item.source,
            "timestamp": context.item.timestamp.isoformat(),
            "url": context.item.url,
            "linked_urls": list(context.item.linked_urls),
        },
        "similar_notes": [
            {
                "note_id": note.note_id,
                "similarity": note.similarity,
                "unresolvedness": note.unresolvedness,
                "metadata": dict(note.metadata),
            }
            for note in context.similar_notes
        ],
    }
    return [
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True),
        }
    ]


def _extract_json_object(
    response_text: str,
    *,
    response_name: str = "LLM prompt scoring response",
) -> Mapping[str, object]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise InvalidScoreError(f"{response_name} must be valid JSON") from exc

    if not isinstance(payload, Mapping):
        raise InvalidScoreError(f"{response_name} must be a JSON object")

    return payload


def _parse_prompt_score_payload(
    response_text: str,
    criteria: Sequence[FilterCriterion],
) -> dict[str, float]:
    payload = _extract_json_object(response_text)
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, Mapping):
        raise InvalidScoreError("LLM prompt scoring response must contain scores object")

    scores: dict[str, float] = {}
    for criterion in criteria:
        if criterion.name not in raw_scores:
            raise InvalidScoreError(
                f"LLM prompt scoring response missing {criterion.name!r}"
            )

        raw_score = raw_scores[criterion.name]
        if isinstance(raw_score, bool) or not isinstance(raw_score, int | float):
            raise InvalidScoreError(
                f"LLM prompt score for {criterion.name!r} must be numeric"
            )
        if raw_score < 0.0 or raw_score > 1.0:
            raise InvalidScoreError(
                f"LLM prompt score for {criterion.name!r} must be in [0.0, 1.0]"
            )

        scores[criterion.name] = float(raw_score)

    return scores


def _score_prompt_criteria(
    context: _ItemRetrievalContext,
    config: AttentionFilterConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> Mapping[str, float]:
    """Score configured Phase 1 prompt criteria through the toolkit LLM boundary."""

    if not config.prompt_criteria:
        return {}

    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    messages = _build_prompt_scoring_request(context, config.prompt_criteria)
    response_text = llm_complete_callable(
        messages=messages,
        config=config.llm_config,
        tier=config.llm_tier,
    )
    return _parse_prompt_score_payload(response_text, config.prompt_criteria)


def _build_assertion_extraction_request(
    context: _ItemRetrievalContext,
) -> list[Mapping[str, str]]:
    """Build the incoming assertion-extraction request for toolkit/llm_client."""

    payload = {
        "task": "extract_attention_filter_incoming_assertions",
        "instructions": (
            "Extract explicit factual, causal, evaluative, or interpretive "
            "claims made by the incoming content. Return only JSON with shape "
            '{"assertions": [{"text": "...", "confidence": 0.0}]}. '
            "Use an empty assertions list when no clear claims are present. "
            "Confidence must be a number between 0.0 and 1.0."
        ),
        "content_item": {
            "content": context.item.content,
            "source": context.item.source,
            "timestamp": context.item.timestamp.isoformat(),
            "url": context.item.url,
            "linked_urls": list(context.item.linked_urls),
        },
    }
    return [
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True),
        }
    ]


def _parse_assertion_extraction_payload(
    response_text: str,
) -> tuple[_IncomingAssertion, ...]:
    payload = _extract_json_object(
        response_text,
        response_name="LLM assertion extraction response",
    )
    raw_assertions = payload.get("assertions")
    if not isinstance(raw_assertions, Sequence) or isinstance(
        raw_assertions, str | bytes
    ):
        raise InvalidScoreError(
            "LLM assertion extraction response must contain assertions list"
        )

    assertions: list[_IncomingAssertion] = []
    for raw_assertion in raw_assertions:
        if not isinstance(raw_assertion, Mapping):
            raise InvalidScoreError("LLM assertion entries must be objects")

        raw_text = raw_assertion.get("text", raw_assertion.get("claim"))
        if not isinstance(raw_text, str):
            raise InvalidScoreError("LLM assertion text must be a string")

        text = raw_text.strip()
        if not text:
            continue

        raw_confidence = raw_assertion.get("confidence", 1.0)
        if isinstance(raw_confidence, bool) or not isinstance(
            raw_confidence, int | float
        ):
            raise InvalidScoreError("LLM assertion confidence must be numeric")
        if raw_confidence < 0.0 or raw_confidence > 1.0:
            raise InvalidScoreError(
                "LLM assertion confidence must be in [0.0, 1.0]"
            )

        assertions.append(
            _IncomingAssertion(text=text, confidence=float(raw_confidence))
        )

    return tuple(assertions)


def _extract_incoming_assertions(
    context: _ItemRetrievalContext,
    config: AttentionFilterConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> tuple[_IncomingAssertion, ...]:
    """Extract incoming claims through the toolkit LLM boundary for friction."""

    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    messages = _build_assertion_extraction_request(context)
    response_text = llm_complete_callable(
        messages=messages,
        config=config.llm_config,
        tier=config.assertion_extraction_tier,
    )
    return _parse_assertion_extraction_payload(response_text)


def _prompt_criterion_weight(
    criterion: FilterCriterion, scoring_config: ScoringConfig
) -> float:
    weight = criterion.weight
    if criterion.name == "precision_surplus":
        weight *= scoring_config.precision_surplus_weight
    return weight


def compute_prompt_composite(
    scores: Mapping[str, float],
    criteria: Sequence[FilterCriterion],
    scoring_config: ScoringConfig,
) -> float:
    """Compute weighted average across configured Phase 1 prompt criteria."""

    weighted_sum = 0.0
    total_weight = 0.0
    for criterion in criteria:
        if criterion.name not in scores:
            continue

        weight = _prompt_criterion_weight(criterion, scoring_config)
        if weight == 0.0:
            continue

        weighted_sum += _clamp_probability(scores[criterion.name]) * weight
        total_weight += weight

    if total_weight == 0.0:
        return 0.0

    return _clamp_probability(weighted_sum / total_weight)


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


def _evaluate_items(
    memory_store: object,
    items: Sequence[ContentItem],
    config: AttentionFilterConfig,
    *,
    prompt_weight: float,
    structure_weight: float,
    embedding_callable: _EmbeddingCallable | None = None,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> list[_ItemEvaluation]:
    """Prepare private per-item scoring context for later annotation phases."""

    retrieval_contexts = _prepare_retrieval_contexts(
        memory_store,
        items,
        config,
        embedding_callable=embedding_callable,
    )
    evaluations: list[_ItemEvaluation] = []
    for context in retrieval_contexts:
        structural = _compute_memory_structural_evaluation(context, config)
        prompt_scores = _score_prompt_criteria(
            context,
            config,
            llm_complete_callable=llm_complete_callable,
        )
        prompt_score = compute_prompt_composite(
            prompt_scores,
            config.prompt_criteria,
            config.scoring,
        )
        incoming_assertions = _extract_incoming_assertions(
            context,
            config,
            llm_complete_callable=llm_complete_callable,
        )
        composite_score = _clamp_probability(
            prompt_score * prompt_weight
            + structural.structure_score * structure_weight
        )
        evaluations.append(
            _ItemEvaluation(
                retrieval=context,
                structural=structural,
                prompt_scores=prompt_scores,
                prompt_score=prompt_score,
                incoming_assertions=incoming_assertions,
                composite_score=composite_score,
                prompt_weight=prompt_weight,
                structure_weight=structure_weight,
            )
        )

    return evaluations


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

        _evaluate_items(
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
