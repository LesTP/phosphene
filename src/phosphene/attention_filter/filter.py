"""Attention Filter entry point."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Protocol

from phosphene.attention_filter.errors import InvalidScoreError
from phosphene.memory_store import DensityMetrics

from phosphene.attention_filter.types import (
    AnnotatedFragment,
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
class _CachedClusterReference:
    cluster_group: str
    note_ids: tuple[str, ...]
    max_similarity: float
    assertion_cache_path: str


@dataclass(frozen=True)
class _FrictionPreparation:
    incoming_assertions: tuple[_IncomingAssertion, ...]
    cached_clusters: tuple[_CachedClusterReference, ...]


@dataclass(frozen=True)
class _ItemEvaluation:
    retrieval: _ItemRetrievalContext
    structural: _MemoryStructuralEvaluation
    prompt_scores: Mapping[str, float]
    prompt_score: float
    incoming_assertions: tuple[_IncomingAssertion, ...]
    friction_preparation: _FrictionPreparation
    composite_score: float
    prompt_weight: float
    structure_weight: float


@dataclass(frozen=True)
class _GeneratedAnnotation:
    evaluation: _ItemEvaluation
    annotation: str


@dataclass(frozen=True)
class _RetentionDecision:
    evaluation: _ItemEvaluation
    accepted: bool
    auto_accepted: bool
    retention_criteria: tuple[str, ...]


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


def _build_annotation_generation_request(
    evaluation: _ItemEvaluation,
) -> list[Mapping[str, str]]:
    """Build the accepted-candidate annotation request for toolkit/llm_client."""

    context = evaluation.retrieval
    payload = {
        "task": "generate_attention_filter_annotation",
        "instructions": (
            "Write a short annotation explaining why this accepted content was "
            "retained. Mention the strongest criteria, relevant friction, and "
            "connections when present. Return only JSON with shape "
            '{"annotation": "..."}; the annotation must be a non-empty string.'
        ),
        "content_item": {
            "content": context.item.content,
            "source": context.item.source,
            "timestamp": context.item.timestamp.isoformat(),
            "url": context.item.url,
            "linked_urls": list(context.item.linked_urls),
        },
        "scores": {
            "composite": evaluation.composite_score,
            "prompt": evaluation.prompt_score,
            "structure": evaluation.structural.structure_score,
            "prompt_weight": evaluation.prompt_weight,
            "structure_weight": evaluation.structure_weight,
            "prompt_criteria": dict(evaluation.prompt_scores),
            "structure_criteria": dict(evaluation.structural.scores),
        },
        "friction": {
            "target": evaluation.structural.friction_target,
            "incoming_assertions": [
                {
                    "text": assertion.text,
                    "confidence": assertion.confidence,
                }
                for assertion in evaluation.incoming_assertions
            ],
            "cached_clusters": [
                {
                    "cluster_group": cluster.cluster_group,
                    "note_ids": list(cluster.note_ids),
                    "max_similarity": cluster.max_similarity,
                    "assertion_cache_path": cluster.assertion_cache_path,
                }
                for cluster in evaluation.friction_preparation.cached_clusters
            ],
        },
        "connections": list(evaluation.structural.connections),
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


def _normalize_annotation_text(text: str) -> str:
    return " ".join(text.split())


def _parse_annotation_generation_payload(response_text: str) -> str:
    payload = _extract_json_object(
        response_text,
        response_name="LLM annotation generation response",
    )
    raw_annotation = payload.get("annotation")
    if not isinstance(raw_annotation, str):
        raise InvalidScoreError(
            "LLM annotation generation response must contain annotation string"
        )

    annotation = _normalize_annotation_text(raw_annotation)
    if not annotation:
        raise InvalidScoreError("LLM annotation must be non-empty")

    return annotation


def _generate_annotation(
    evaluation: _ItemEvaluation,
    config: AttentionFilterConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> str:
    """Generate one accepted candidate annotation through the toolkit LLM boundary."""

    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    messages = _build_annotation_generation_request(evaluation)
    response_text = llm_complete_callable(
        messages=messages,
        config=config.llm_config,
        tier=config.llm_tier,
    )
    return _parse_annotation_generation_payload(response_text)


def _generate_annotations(
    evaluations: Sequence[_ItemEvaluation],
    config: AttentionFilterConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> tuple[_GeneratedAnnotation, ...]:
    """Generate annotations for already-accepted private evaluations."""

    return tuple(
        _GeneratedAnnotation(
            evaluation=evaluation,
            annotation=_generate_annotation(
                evaluation,
                config,
                llm_complete_callable=llm_complete_callable,
            ),
        )
        for evaluation in evaluations
    )


def _active_score_names(scores: Mapping[str, float]) -> tuple[str, ...]:
    return tuple(
        name
        for name, score in sorted(scores.items())
        if _clamp_probability(score) > 0.0
    )


def _retention_criteria_for_evaluation(
    evaluation: _ItemEvaluation,
) -> tuple[str, ...]:
    """Return deterministic criteria with non-zero prompt or structural scores."""

    criteria: list[str] = []
    seen: set[str] = set()
    for score_map in (evaluation.prompt_scores, evaluation.structural.scores):
        for name in _active_score_names(score_map):
            if name not in seen:
                criteria.append(name)
                seen.add(name)

    return tuple(criteria)


def _decide_retention(
    evaluation: _ItemEvaluation, config: AttentionFilterConfig
) -> _RetentionDecision:
    """Apply threshold and source bypass rules to one evaluated item."""

    auto_accepted = evaluation.retrieval.item.source in config.auto_accept_sources
    accepted = (
        auto_accepted
        or evaluation.composite_score >= config.acceptance_threshold
    )
    retention_criteria = (
        _retention_criteria_for_evaluation(evaluation) if accepted else ()
    )
    return _RetentionDecision(
        evaluation=evaluation,
        accepted=accepted,
        auto_accepted=auto_accepted,
        retention_criteria=retention_criteria,
    )


def _decide_batch_retention(
    evaluations: Sequence[_ItemEvaluation],
    config: AttentionFilterConfig,
) -> tuple[_RetentionDecision, ...]:
    """Apply deterministic acceptance decisions to a scored batch."""

    return tuple(_decide_retention(evaluation, config) for evaluation in evaluations)


def _accepted_evaluations(
    decisions: Sequence[_RetentionDecision],
) -> tuple[_ItemEvaluation, ...]:
    return tuple(decision.evaluation for decision in decisions if decision.accepted)


def _below_threshold_decisions(
    decisions: Sequence[_RetentionDecision],
) -> tuple[_RetentionDecision, ...]:
    return tuple(decision for decision in decisions if not decision.accepted)


def _wild_card_count(below_threshold_count: int, wild_card_ratio: float) -> int:
    if wild_card_ratio <= 0.0 or below_threshold_count <= 0:
        return 0

    return min(below_threshold_count, int(below_threshold_count * wild_card_ratio))


def _select_wild_card_decisions(
    below_threshold_decisions: Sequence[_RetentionDecision],
    config: AttentionFilterConfig,
) -> tuple[_RetentionDecision, ...]:
    count = _wild_card_count(
        len(below_threshold_decisions),
        config.wild_card_ratio,
    )
    if count == 0:
        return ()

    sampled_ids = {
        id(decision)
        for decision in random.sample(tuple(below_threshold_decisions), count)
    }
    return tuple(
        decision
        for decision in below_threshold_decisions
        if id(decision) in sampled_ids
    )


def _near_miss_decisions(
    below_threshold_decisions: Sequence[_RetentionDecision],
    wild_card_decisions: Sequence[_RetentionDecision],
    config: AttentionFilterConfig,
) -> tuple[_RetentionDecision, ...]:
    if config.near_miss_margin <= 0.0:
        return ()

    wild_card_ids = {id(decision) for decision in wild_card_decisions}
    lower_bound = config.acceptance_threshold - config.near_miss_margin
    return tuple(
        decision
        for decision in below_threshold_decisions
        if id(decision) not in wild_card_ids
        and decision.evaluation.composite_score >= lower_bound
    )


def _rejected_count(
    decisions: Sequence[_RetentionDecision],
    wild_card_decisions: Sequence[_RetentionDecision] = (),
    near_miss_decisions: Sequence[_RetentionDecision] = (),
) -> int:
    excluded_ids = {
        *(id(decision) for decision in wild_card_decisions),
        *(id(decision) for decision in near_miss_decisions),
    }
    return sum(
        1
        for decision in decisions
        if not decision.accepted and id(decision) not in excluded_ids
    )


def _retention_criteria_for_generated_annotation(
    generated: _GeneratedAnnotation,
    decisions: Sequence[_RetentionDecision],
) -> tuple[str, ...]:
    for decision in decisions:
        if decision.evaluation is generated.evaluation:
            return decision.retention_criteria

    raise InvalidScoreError("Generated annotation has no retention decision")


def _assemble_annotated_fragment(
    generated: _GeneratedAnnotation,
    retention_criteria: Sequence[str],
) -> AnnotatedFragment:
    """Map one accepted private evaluation into the public fragment contract."""

    evaluation = generated.evaluation
    item = evaluation.retrieval.item
    return AnnotatedFragment(
        content=item.content,
        annotation=generated.annotation,
        importance_score=evaluation.composite_score,
        unresolvedness=_clamp_probability(
            evaluation.structural.scores.get("unresolvedness_affinity", 0.0)
        ),
        retention_criteria=list(retention_criteria),
        prompt_score=evaluation.prompt_score,
        structure_score=evaluation.structural.structure_score,
        friction_target=evaluation.structural.friction_target,
        connections=list(evaluation.structural.connections),
        source=item.source,
        timestamp=item.timestamp,
        url=item.url,
        linked_urls=list(item.linked_urls),
        embedding=evaluation.retrieval.embedding,
    )


def _assemble_annotated_fragments(
    generated_annotations: Sequence[_GeneratedAnnotation],
    decisions: Sequence[_RetentionDecision],
) -> list[AnnotatedFragment]:
    """Assemble consumer-ready fragments for accepted decisions only."""

    return [
        _assemble_annotated_fragment(
            generated,
            _retention_criteria_for_generated_annotation(generated, decisions),
        )
        for generated in generated_annotations
    ]


def _assemble_wild_card_fragments(
    generated_annotations: Sequence[_GeneratedAnnotation],
) -> list[AnnotatedFragment]:
    return [
        _assemble_annotated_fragment(generated, ("wild_card",))
        for generated in generated_annotations
    ]


def _assemble_near_miss_fragments(
    generated_annotations: Sequence[_GeneratedAnnotation],
) -> list[AnnotatedFragment]:
    return [
        _assemble_annotated_fragment(
            generated,
            _retention_criteria_for_evaluation(generated.evaluation),
        )
        for generated in generated_annotations
    ]


def _assertion_cache_path(cluster_group: str) -> str:
    return f"tier2/{cluster_group}.json"


def _prepare_friction_from_assertions(
    context: _ItemRetrievalContext,
    incoming_assertions: Sequence[_IncomingAssertion],
) -> _FrictionPreparation:
    """Pair incoming claims with retrieved clusters that have assertion caches."""

    cluster_notes: dict[str, list[_SimilarNoteContext]] = {}
    for note in context.similar_notes:
        raw_cluster_group = note.metadata.get("cluster_group")
        if not isinstance(raw_cluster_group, str):
            continue

        cluster_group = raw_cluster_group.strip()
        if not cluster_group:
            continue

        cluster_notes.setdefault(cluster_group, []).append(note)

    cached_clusters = tuple(
        _CachedClusterReference(
            cluster_group=cluster_group,
            note_ids=tuple(note.note_id for note in notes),
            max_similarity=max(_clamp_probability(note.similarity) for note in notes),
            assertion_cache_path=_assertion_cache_path(cluster_group),
        )
        for cluster_group, notes in sorted(cluster_notes.items())
    )
    return _FrictionPreparation(
        incoming_assertions=tuple(incoming_assertions),
        cached_clusters=cached_clusters,
    )


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
    phase2_active: bool | None = None,
    embedding_callable: _EmbeddingCallable | None = None,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> list[_ItemEvaluation]:
    """Prepare private per-item scoring context for later annotation phases."""

    if phase2_active is None:
        phase2_active = structure_weight > 0.0

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
        if phase2_active:
            incoming_assertions = _extract_incoming_assertions(
                context,
                config,
                llm_complete_callable=llm_complete_callable,
            )
            friction_preparation = _prepare_friction_from_assertions(
                context,
                incoming_assertions,
            )
        else:
            incoming_assertions = ()
            friction_preparation = _FrictionPreparation(
                incoming_assertions=(),
                cached_clusters=(),
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
                friction_preparation=friction_preparation,
                composite_score=composite_score,
                prompt_weight=prompt_weight,
                structure_weight=structure_weight,
            )
        )

    return evaluations


class AttentionFilter:
    """Personality-driven content selector and annotator."""

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def filter_content(
        self, items: list[ContentItem], config: AttentionFilterConfig
    ) -> FilterResult:
        density_snapshot = self.memory_store.get_density_metrics()
        phase2_active = phase2_is_active(density_snapshot, config)
        prompt_weight, structure_weight = compute_blend_weights(density_snapshot, config)

        if not items:
            return FilterResult(
                accepted=[],
                near_misses=[],
                wild_cards=[],
                rejected_count=0,
                total_count=0,
                prompt_weight=prompt_weight,
                structure_weight=structure_weight,
                density_snapshot=density_snapshot,
            )

        evaluations = _evaluate_items(
            self.memory_store,
            items,
            config,
            prompt_weight=prompt_weight,
            structure_weight=structure_weight,
            phase2_active=phase2_active,
        )
        decisions = _decide_batch_retention(evaluations, config)
        below_threshold_decisions = _below_threshold_decisions(decisions)
        wild_card_decisions = _select_wild_card_decisions(
            below_threshold_decisions,
            config,
        )
        near_miss_decisions = _near_miss_decisions(
            below_threshold_decisions,
            wild_card_decisions,
            config,
        )
        accepted_evaluations = _accepted_evaluations(decisions)
        generated_annotations = _generate_annotations(accepted_evaluations, config)
        wild_card_annotations = _generate_annotations(
            tuple(decision.evaluation for decision in wild_card_decisions),
            config,
        )
        near_miss_annotations = _generate_annotations(
            tuple(decision.evaluation for decision in near_miss_decisions),
            config,
        )
        accepted_fragments = _assemble_annotated_fragments(
            generated_annotations,
            decisions,
        )
        return FilterResult(
            accepted=accepted_fragments,
            near_misses=_assemble_near_miss_fragments(near_miss_annotations),
            wild_cards=_assemble_wild_card_fragments(wild_card_annotations),
            rejected_count=_rejected_count(
                decisions,
                wild_card_decisions,
                near_miss_decisions,
            ),
            total_count=len(items),
            prompt_weight=prompt_weight,
            structure_weight=structure_weight,
            density_snapshot=density_snapshot,
        )
