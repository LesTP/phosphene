"""Distillation engine public constructor and private state helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from threading import Lock
from typing import Any, Protocol

import numpy as np

from phosphene.distillation.errors import (
    DistillationConfigError,
    DistillationError,
    DistillationLockError,
    InsufficientDataError,
    NoPatternDataError,
)
from phosphene.distillation.types import (
    DistillationConfig,
    EvolutionResult,
    GateStatus,
    ReflectionInsight,
    TierPromotionResult,
)
from phosphene.memory_store import NoteInput, NotePatch, NoteQuery

_REQUIRED_MEMORY_STORE_METHODS = (
    "query_notes",
    "store_note",
    "update_note",
    "add_links",
    "get_personality_context",
    "supersede",
)
_METADATA_DIRECTORY = ".phosphene"
_RUN_METADATA_FILENAME = "distillation_runs.json"
_LAST_T1_TO_T2_KEY = "last_t1_to_t2_run"
_LAST_T2_TO_T3_KEY = "last_t2_to_t3_run"
_UNBOUNDED_QUERY_LIMIT = 1_000_000
_ASSERTION_CACHE_DIRECTORY = "tier2"
_REFLECTION_INSIGHT_TYPES = {
    "recurring_tension",
    "new_pattern",
    "evolution",
    "contradiction",
}


class _EmbeddingCallable(Protocol):
    def __call__(self, texts: list[str], config: object) -> Any: ...


class _ClusterCallable(Protocol):
    def __call__(
        self,
        embeddings: object,
        config: object,
        *,
        texts: list[str],
    ) -> Any: ...


class _LLMCompleteCallable(Protocol):
    def __call__(
        self,
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str: ...


@dataclass(frozen=True)
class _DistillationRunMetadata:
    last_t1_to_t2_run: datetime | None = None
    last_t2_to_t3_run: datetime | None = None


@dataclass(frozen=True)
class _PreparedTier1Note:
    note: object
    effective_importance: float
    feedback_boost: float


@dataclass(frozen=True)
class _Tier1DistillationInput:
    notes: list[_PreparedTier1Note]
    feedback_events: list[object]
    since: datetime | None


@dataclass(frozen=True)
class _RaptorClusterConfig:
    strategy: str
    raptor_summarizer: Callable[[list[str]], str]
    raptor_embedder: Callable[[list[str]], object]
    raptor_max_depth: int = 3


@dataclass(frozen=True)
class _NormalizedCluster:
    cluster_id: str
    member_indices: list[int]
    summary: str | None = None


@dataclass(frozen=True)
class _NormalizedClusterResult:
    clusters: list[_NormalizedCluster]
    noise_indices: set[int]
    tree_depth: int


@dataclass(frozen=True)
class _CoherentClusterPromotion:
    cluster: _NormalizedCluster
    coherence: float
    summary: str
    source_note_ids: list[str]
    importance: float
    unresolvedness: float
    centroid: object


@dataclass(frozen=True)
class _ClusterAssertion:
    text: str
    confidence: float


@dataclass(frozen=True)
class _AssertionCachePayload:
    cluster_group: str
    summary: str
    assertions: tuple[_ClusterAssertion, ...]


@dataclass(frozen=True)
class _CriterionFeedbackMetric:
    criterion_name: str
    feedback_count: int
    engaged_count: int
    engagement_rate: float
    mean_engagement: float


@dataclass(frozen=True)
class _Tier2EvolutionInput:
    pattern_notes: list[object]
    feedback_events: list[object]
    feedback_metrics: list[_CriterionFeedbackMetric]


@dataclass(frozen=True)
class _ReflectionAuditArtifact:
    request_messages: list[Mapping[str, str]]
    raw_response: str
    insights: list[ReflectionInsight]


class DistillationEngine:
    """Coordinate tier promotion through a Memory Store.

    Phase 1 exposes the ARCH public shell plus gate evaluation, metadata, and
    locking. Live synthesis operations are implemented in later phases.
    """

    def __init__(self, memory_store):
        _validate_memory_store(memory_store)
        self.memory_store = memory_store
        self._run_metadata_path = (
            Path(memory_store.vault_path) / _METADATA_DIRECTORY / _RUN_METADATA_FILENAME
        )
        self._consolidation_lock = Lock()

    @contextmanager
    def _acquire_consolidation_lock(self):
        acquired = self._consolidation_lock.acquire(blocking=False)
        if not acquired:
            raise DistillationLockError("another distillation run is already active")

        try:
            yield
        finally:
            self._consolidation_lock.release()

    def _is_consolidation_locked(self) -> bool:
        acquired = self._consolidation_lock.acquire(blocking=False)
        if acquired:
            self._consolidation_lock.release()
            return False
        return True

    def check_gates(self, config: DistillationConfig) -> GateStatus:
        """Report whether either distillation path is eligible to run."""
        metadata = self._read_run_metadata()
        now = datetime.now(timezone.utc)
        last_run = _latest_datetime(
            metadata.last_t1_to_t2_run,
            metadata.last_t2_to_t3_run,
        )

        time_since_last_run = _elapsed_since(last_run, now)
        time_gate = (
            time_since_last_run is None
            or time_since_last_run >= config.min_time_between_runs
        )
        lock_gate = not self._is_consolidation_locked()

        tier1_pending = len(
            self.memory_store.query_notes(
                NoteQuery(
                    tier=1,
                    since=metadata.last_t1_to_t2_run,
                    limit=_UNBOUNDED_QUERY_LIMIT,
                )
            )
        )
        tier2_notes = self.memory_store.query_notes(NoteQuery(tier=2, limit=1))
        days_since_last_t3 = _days_since(metadata.last_t2_to_t3_run, now)

        t1_volume_gate = tier1_pending >= config.min_tier1_volume
        t3_cycle_gate = (
            days_since_last_t3 is None
            or days_since_last_t3 >= config.t2_to_t3_cycle_days
        )
        t2_volume_gate = bool(tier2_notes) and t3_cycle_gate
        volume_gate = t1_volume_gate or t2_volume_gate

        t1_to_t2_ready = time_gate and lock_gate and t1_volume_gate
        t2_to_t3_ready = time_gate and lock_gate and t2_volume_gate

        return GateStatus(
            ready=t1_to_t2_ready or t2_to_t3_ready,
            time_gate=time_gate,
            volume_gate=volume_gate,
            lock_gate=lock_gate,
            t1_to_t2_ready=t1_to_t2_ready,
            t2_to_t3_ready=t2_to_t3_ready,
            time_since_last_run=time_since_last_run,
            tier1_pending=tier1_pending,
            days_since_last_t3=days_since_last_t3,
        )

    def distill_t1_to_t2(
        self,
        config: DistillationConfig,
    ) -> TierPromotionResult:
        """Promote Tier 1 notes into Tier 2 clusters.

        Phase 2 currently performs Tier 1 selection, feedback preparation,
        RAPTOR clustering, coherence gating, Tier 2 cluster note writes, and
        assertion-cache persistence.
        """
        with self._acquire_consolidation_lock():
            prepared = self._prepare_tier1_distillation_input(config)
            texts = [_note_content(item.note) for item in prepared.notes]
            embeddings = _embedding_vectors(
                _toolkit_embed(texts, config.embedding_config)
            )
            cluster_config = _build_raptor_cluster_config(config)
            cluster_result = _normalize_cluster_result(
                _toolkit_cluster(embeddings, cluster_config, texts=texts),
                note_count=len(prepared.notes),
            )

            coherent_member_indices: set[int] = set()
            coherent_promotions: list[_CoherentClusterPromotion] = []
            incoherent_cluster_count = 0
            for cluster in cluster_result.clusters:
                coherence = _mean_pairwise_similarity(
                    [_vector_at(embeddings, index) for index in cluster.member_indices]
                )
                if coherence >= config.min_cluster_coherence:
                    coherent_member_indices.update(cluster.member_indices)
                    coherent_promotions.append(
                        _build_coherent_cluster_promotion(
                            cluster,
                            prepared=prepared,
                            texts=texts,
                            embeddings=embeddings,
                            coherence=coherence,
                        )
                    )
                else:
                    incoherent_cluster_count += 1

            clustered_indices = {
                index
                for cluster in cluster_result.clusters
                for index in cluster.member_indices
            }
            noise_indices = set(cluster_result.noise_indices)
            noise_indices.update(set(range(len(prepared.notes))) - clustered_indices)
            assertion_cache_payloads = _build_assertion_cache_payloads(
                coherent_promotions,
                config,
            )
            write_result = self._write_tier2_cluster_notes(coherent_promotions)
            assertion_cache_updated = self._write_assertion_caches(
                assertion_cache_payloads
            )
            metadata = self._read_run_metadata()
            self._write_run_metadata(
                _DistillationRunMetadata(
                    last_t1_to_t2_run=datetime.now(timezone.utc),
                    last_t2_to_t3_run=metadata.last_t2_to_t3_run,
                )
            )

            return TierPromotionResult(
                new_cluster_ids=write_result["new_cluster_ids"],
                updated_cluster_ids=write_result["updated_cluster_ids"],
                promoted_count=len(coherent_member_indices),
                noise_count=len(noise_indices),
                incoherent_cluster_count=incoherent_cluster_count,
                cluster_tree_depth=cluster_result.tree_depth,
                feedback_processed=len(prepared.feedback_events),
                assertion_cache_updated=assertion_cache_updated,
            )

    def distill_t2_to_t3(
        self,
        config: DistillationConfig,
    ) -> EvolutionResult:
        """Evolve Tier 2 patterns into Tier 3 personality files.

        Phase 3 currently prepares pattern and feedback inputs under the
        distillation lock and captures reflection output as an audit artifact.
        Evolution and writeback are implemented in later Phase 3 steps.
        """
        with self._acquire_consolidation_lock():
            prepared = self._prepare_tier2_evolution_input(config)
            self._reflect_tier2_patterns(prepared, config)
        raise NotImplementedError("T2 to T3 distillation is implemented in Phase 3")

    def _read_run_metadata(self) -> _DistillationRunMetadata:
        if not self._run_metadata_path.exists():
            return _DistillationRunMetadata()

        try:
            payload = json.loads(self._run_metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return _DistillationRunMetadata()

        if not isinstance(payload, dict):
            return _DistillationRunMetadata()

        return _DistillationRunMetadata(
            last_t1_to_t2_run=_parse_metadata_datetime(payload.get(_LAST_T1_TO_T2_KEY)),
            last_t2_to_t3_run=_parse_metadata_datetime(payload.get(_LAST_T2_TO_T3_KEY)),
        )

    def _write_run_metadata(self, metadata: _DistillationRunMetadata) -> None:
        self._run_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            _LAST_T1_TO_T2_KEY: _format_metadata_datetime(metadata.last_t1_to_t2_run),
            _LAST_T2_TO_T3_KEY: _format_metadata_datetime(metadata.last_t2_to_t3_run),
        }
        temp_path = self._run_metadata_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self._run_metadata_path)

    def _prepare_tier1_distillation_input(
        self,
        config: DistillationConfig,
    ) -> _Tier1DistillationInput:
        metadata = self._read_run_metadata()
        since = metadata.last_t1_to_t2_run
        tier1_notes = self.memory_store.query_notes(
            NoteQuery(
                tier=1,
                since=since,
                limit=_UNBOUNDED_QUERY_LIMIT,
                order_by="created_at",
                descending=False,
            )
        )
        input_notes = [
            note
            for note in tier1_notes
            if getattr(note, "source", None) != "feedback"
        ]

        if len(input_notes) < config.min_tier1_volume:
            raise InsufficientDataError(
                "distill_t1_to_t2 requires at least "
                f"{config.min_tier1_volume} Tier 1 notes since the last T1 to T2 run; "
                f"found {len(input_notes)}"
            )

        feedback_events: list[object] = []
        if config.incorporate_feedback:
            feedback_events = self.memory_store.query_notes(
                NoteQuery(
                    tier=1,
                    source="feedback",
                    since=since,
                    limit=_UNBOUNDED_QUERY_LIMIT,
                    order_by="created_at",
                    descending=False,
                )
            )

        boosts = _feedback_boosts_by_note_id(feedback_events)
        prepared_notes = [
            _PreparedTier1Note(
                note=note,
                effective_importance=_clamp_probability(
                    float(getattr(note, "importance", 0.0))
                    + boosts.get(str(note.note_id), 0.0)
                ),
                feedback_boost=boosts.get(str(note.note_id), 0.0),
            )
            for note in input_notes
        ]

        return _Tier1DistillationInput(
            notes=prepared_notes,
            feedback_events=feedback_events,
            since=since,
        )

    def _prepare_tier2_evolution_input(
        self,
        config: DistillationConfig,
    ) -> _Tier2EvolutionInput:
        pattern_notes = self.memory_store.query_notes(
            NoteQuery(
                tier=2,
                limit=_UNBOUNDED_QUERY_LIMIT,
                order_by="created_at",
                descending=False,
            )
        )
        if not pattern_notes:
            raise NoPatternDataError(
                "distill_t2_to_t3 requires at least one Tier 2 pattern note"
            )

        feedback_events: list[object] = []
        if config.incorporate_feedback:
            feedback_events = self.memory_store.query_notes(
                NoteQuery(
                    tier=1,
                    source="feedback",
                    limit=_UNBOUNDED_QUERY_LIMIT,
                    order_by="created_at",
                    descending=False,
                )
            )

        return _Tier2EvolutionInput(
            pattern_notes=list(pattern_notes),
            feedback_events=feedback_events,
            feedback_metrics=_criterion_feedback_metrics(feedback_events),
        )

    def _reflect_tier2_patterns(
        self,
        prepared: _Tier2EvolutionInput,
        config: DistillationConfig,
        *,
        llm_complete_callable: _LLMCompleteCallable | None = None,
    ) -> _ReflectionAuditArtifact:
        return _build_reflection_audit_artifact(
            prepared,
            config,
            llm_complete_callable=llm_complete_callable,
        )

    def _write_tier2_cluster_notes(
        self,
        promotions: Sequence[_CoherentClusterPromotion],
    ) -> dict[str, list[str]]:
        existing_by_group = {
            str(note.cluster_group): note
            for note in self.memory_store.query_notes(
                NoteQuery(tier=2, limit=_UNBOUNDED_QUERY_LIMIT)
            )
            if getattr(note, "cluster_group", None)
        }

        new_cluster_ids: list[str] = []
        updated_cluster_ids: list[str] = []
        note_ids_by_group: dict[str, str] = {}

        for promotion in promotions:
            existing = existing_by_group.get(promotion.cluster.cluster_id)
            if existing is None:
                note_id = self.memory_store.store_note(
                    NoteInput(
                        tier=2,
                        content=promotion.summary,
                        title=_cluster_title(promotion.cluster.cluster_id, promotion.summary),
                        importance=promotion.importance,
                        unresolvedness=promotion.unresolvedness,
                        links=promotion.source_note_ids,
                        tags=["distilled-pattern"],
                        embedding=promotion.centroid,
                        attractor_relevance=promotion.coherence,
                        cluster_group=promotion.cluster.cluster_id,
                    )
                )
                new_cluster_ids.append(str(note_id))
                note_ids_by_group[promotion.cluster.cluster_id] = str(note_id)
            else:
                existing_links = [str(note_id) for note_id in getattr(existing, "links", [])]
                merged_links = _dedupe_preserving_order(
                    existing_links + promotion.source_note_ids
                )
                updated_note = self.memory_store.update_note(
                    str(existing.note_id),
                    NotePatch(
                        content=_merged_cluster_content(existing.content, promotion.summary),
                        title=_cluster_title(
                            promotion.cluster.cluster_id,
                            promotion.summary,
                            existing_title=getattr(existing, "title", None),
                        ),
                        importance=max(
                            float(getattr(existing, "importance", 0.0)),
                            promotion.importance,
                        ),
                        unresolvedness=max(
                            float(getattr(existing, "unresolvedness", 0.0)),
                            promotion.unresolvedness,
                        ),
                        links=merged_links,
                        tags=_dedupe_preserving_order(
                            [str(tag) for tag in getattr(existing, "tags", [])]
                            + ["distilled-pattern"]
                        ),
                        embedding=promotion.centroid,
                        attractor_relevance=promotion.coherence,
                    ),
                )
                updated_cluster_ids.append(str(updated_note.note_id))
                note_ids_by_group[promotion.cluster.cluster_id] = str(updated_note.note_id)

        cluster_note_ids = list(note_ids_by_group.values())
        for note_id in cluster_note_ids:
            related_ids = [related_id for related_id in cluster_note_ids if related_id != note_id]
            self.memory_store.add_links(note_id, related_ids)

        return {
            "new_cluster_ids": new_cluster_ids,
            "updated_cluster_ids": updated_cluster_ids,
        }

    def _write_assertion_caches(
        self,
        payloads: Sequence[_AssertionCachePayload],
    ) -> list[str]:
        cache_dir = Path(self.memory_store.vault_path) / _ASSERTION_CACHE_DIRECTORY
        cache_dir.mkdir(parents=True, exist_ok=True)
        for payload in payloads:
            cache_path = _assertion_cache_path(cache_dir, payload.cluster_group)
            temp_path = cache_path.with_name(f"{cache_path.name}.tmp")
            temp_path.write_text(
                json.dumps(
                    _assertion_cache_json(payload),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            temp_path.replace(cache_path)

        return [payload.cluster_group for payload in payloads]


def _build_assertion_cache_payloads(
    promotions: Sequence[_CoherentClusterPromotion],
    config: DistillationConfig,
) -> list[_AssertionCachePayload]:
    return [
        _AssertionCachePayload(
            cluster_group=promotion.cluster.cluster_id,
            summary=promotion.summary,
            assertions=_extract_cluster_assertions(
                promotion.summary,
                config,
            ),
        )
        for promotion in promotions
    ]


def _toolkit_embed(texts: list[str], config: object) -> Any:
    from toolkit.embedding import embed

    return embed(texts, config)


def _embedding_vectors(result: object) -> object:
    return getattr(result, "vectors", result)


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


def _toolkit_cluster(
    embeddings: object,
    config: object,
    *,
    texts: list[str],
) -> Any:
    from toolkit.clustering import cluster

    return cluster(embeddings, config, texts=texts)


def _build_cluster_summary_request(texts: Sequence[str]) -> list[Mapping[str, str]]:
    payload = {
        "task": "distill_tier1_cluster_summary",
        "instructions": (
            "Synthesize these Tier 1 observations into one coherent Tier 2 "
            "pattern description. Preserve concrete tensions, recurring "
            "friction, and unresolved questions. Avoid inventing context not "
            "supported by the observations. Return plain text only."
        ),
        "observations": [str(text) for text in texts],
    }
    return [
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True),
        }
    ]


def _build_assertion_cache_request(cluster_summary: str) -> list[Mapping[str, str]]:
    payload = {
        "task": "extract_distillation_cluster_assertions",
        "instructions": (
            "Extract dominant factual, causal, evaluative, or interpretive "
            "assertions supported or contested by this Tier 2 pattern summary. "
            "Return only JSON with shape "
            '{"assertions": [{"text": "...", "confidence": 0.0}]}. '
            "Use an empty assertions list when no clear claims are present. "
            "Confidence must be a number between 0.0 and 1.0."
        ),
        "cluster_summary": cluster_summary,
    }
    return [
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True),
        }
    ]


def _build_reflection_request(
    prepared: _Tier2EvolutionInput,
) -> list[Mapping[str, str]]:
    payload = {
        "task": "distill_t2_to_t3_reflection",
        "instructions": (
            "Reflect on the Tier 2 pattern layer before any personality-file "
            "changes are proposed. Synthesize recurring tensions, unresolved "
            "threads, new associative connections, contradictions, and possible "
            "evolution pressure. Do not prescribe file edits. Return only JSON "
            "with shape "
            '{"insights": [{"content": "...", "source_pattern_ids": ["..."], '
            '"insight_type": "recurring_tension|new_pattern|evolution|'
            'contradiction", "confidence": 0.0}]}. Confidence must be in '
            "[0.0, 1.0]."
        ),
        "patterns": [_pattern_note_payload(note) for note in prepared.pattern_notes],
        "feedback_metrics": [
            {
                "criterion_name": metric.criterion_name,
                "feedback_count": metric.feedback_count,
                "engaged_count": metric.engaged_count,
                "engagement_rate": metric.engagement_rate,
                "mean_engagement": metric.mean_engagement,
            }
            for metric in prepared.feedback_metrics
        ],
    }
    return [
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True),
        }
    ]


def _build_reflection_audit_artifact(
    prepared: _Tier2EvolutionInput,
    config: DistillationConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> _ReflectionAuditArtifact:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    request_messages = _build_reflection_request(prepared)
    raw_response = llm_complete_callable(
        messages=request_messages,
        config=config.llm_config,
        tier=config.reflection_tier,
    )
    return _ReflectionAuditArtifact(
        request_messages=request_messages,
        raw_response=raw_response,
        insights=_parse_reflection_insights(
            raw_response,
            valid_pattern_ids={
                str(getattr(note, "note_id"))
                for note in prepared.pattern_notes
                if getattr(note, "note_id", None) is not None
            },
        ),
    )


def _parse_reflection_insights(
    response_text: str,
    *,
    valid_pattern_ids: set[str] | None = None,
) -> list[ReflectionInsight]:
    payload = _extract_json_object(
        response_text,
        response_name="LLM reflection response",
    )
    raw_insights = payload.get("insights")
    if not isinstance(raw_insights, Sequence) or isinstance(raw_insights, str | bytes):
        raise DistillationError("LLM reflection response must contain insights list")

    insights: list[ReflectionInsight] = []
    for raw_insight in raw_insights:
        if not isinstance(raw_insight, Mapping):
            raise DistillationError("LLM reflection insight entries must be objects")

        raw_content = raw_insight.get("content", raw_insight.get("text"))
        if not isinstance(raw_content, str):
            raise DistillationError("LLM reflection insight content must be a string")
        content = raw_content.strip()
        if not content:
            raise DistillationError("LLM reflection insight content cannot be empty")

        raw_source_ids = raw_insight.get(
            "source_pattern_ids",
            raw_insight.get("pattern_ids"),
        )
        if not isinstance(raw_source_ids, Sequence) or isinstance(
            raw_source_ids, str | bytes
        ):
            raise DistillationError(
                "LLM reflection insight source_pattern_ids must be a list"
            )
        source_pattern_ids = _dedupe_preserving_order(
            [str(note_id).strip() for note_id in raw_source_ids if str(note_id).strip()]
        )
        if not source_pattern_ids:
            raise DistillationError(
                "LLM reflection insight source_pattern_ids cannot be empty"
            )
        if valid_pattern_ids is not None:
            unknown_ids = [
                note_id for note_id in source_pattern_ids if note_id not in valid_pattern_ids
            ]
            if unknown_ids:
                raise DistillationError(
                    "LLM reflection insight source_pattern_ids include unknown "
                    f"pattern ids: {', '.join(unknown_ids)}"
                )

        raw_insight_type = raw_insight.get("insight_type", raw_insight.get("type"))
        if not isinstance(raw_insight_type, str):
            raise DistillationError("LLM reflection insight_type must be a string")
        insight_type = raw_insight_type.strip()
        if insight_type not in _REFLECTION_INSIGHT_TYPES:
            raise DistillationError(
                "LLM reflection insight_type must be one of "
                f"{', '.join(sorted(_REFLECTION_INSIGHT_TYPES))}"
            )

        raw_confidence = raw_insight.get("confidence", 1.0)
        if isinstance(raw_confidence, bool) or not isinstance(
            raw_confidence, int | float
        ):
            raise DistillationError("LLM reflection confidence must be numeric")
        if raw_confidence < 0.0 or raw_confidence > 1.0:
            raise DistillationError(
                "LLM reflection confidence must be in [0.0, 1.0]"
            )

        insights.append(
            ReflectionInsight(
                content=content,
                source_pattern_ids=source_pattern_ids,
                insight_type=insight_type,
                confidence=float(raw_confidence),
            )
        )

    return insights


def _extract_cluster_assertions(
    cluster_summary: str,
    config: DistillationConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> tuple[_ClusterAssertion, ...]:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    response_text = llm_complete_callable(
        messages=_build_assertion_cache_request(cluster_summary),
        config=config.llm_config,
        tier=config.reflection_tier,
    )
    return _parse_assertion_cache_payload(response_text)


def _parse_assertion_cache_payload(response_text: str) -> tuple[_ClusterAssertion, ...]:
    payload = _extract_json_object(
        response_text,
        response_name="LLM assertion cache response",
    )
    raw_assertions = payload.get("assertions")
    if not isinstance(raw_assertions, Sequence) or isinstance(
        raw_assertions, str | bytes
    ):
        raise DistillationError(
            "LLM assertion cache response must contain assertions list"
        )

    assertions: list[_ClusterAssertion] = []
    for raw_assertion in raw_assertions:
        if not isinstance(raw_assertion, Mapping):
            raise DistillationError("LLM assertion cache entries must be objects")

        raw_text = raw_assertion.get("text", raw_assertion.get("claim"))
        if not isinstance(raw_text, str):
            raise DistillationError("LLM assertion cache text must be a string")

        text = raw_text.strip()
        if not text:
            continue

        raw_confidence = raw_assertion.get("confidence", 1.0)
        if isinstance(raw_confidence, bool) or not isinstance(
            raw_confidence, int | float
        ):
            raise DistillationError("LLM assertion cache confidence must be numeric")
        if raw_confidence < 0.0 or raw_confidence > 1.0:
            raise DistillationError(
                "LLM assertion cache confidence must be in [0.0, 1.0]"
            )

        assertions.append(
            _ClusterAssertion(text=text, confidence=float(raw_confidence))
        )

    return tuple(assertions)


def _extract_json_object(
    response_text: str,
    *,
    response_name: str,
) -> Mapping[str, object]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise DistillationError(f"{response_name} must be valid JSON") from exc

    if not isinstance(payload, Mapping):
        raise DistillationError(f"{response_name} must be a JSON object")

    return payload


def _make_raptor_summarizer(
    llm_config: object,
    tier: object,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> Callable[[list[str]], str]:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    def summarizer(texts: list[str]) -> str:
        return llm_complete_callable(
            messages=_build_cluster_summary_request(texts),
            config=llm_config,
            tier=tier,
        )

    return summarizer


def _make_raptor_embedder(
    embedding_config: object,
    *,
    embedding_callable: _EmbeddingCallable | None = None,
) -> Callable[[list[str]], object]:
    if embedding_callable is None:
        embedding_callable = _toolkit_embed

    def embedder(texts: list[str]) -> object:
        return _embedding_vectors(embedding_callable(texts, embedding_config))

    return embedder


def _build_raptor_cluster_config(config: DistillationConfig) -> object:
    summarizer = _make_raptor_summarizer(config.llm_config, config.reflection_tier)
    embedder = _make_raptor_embedder(config.embedding_config)

    if config.clustering_config is None:
        return _RaptorClusterConfig(
            strategy="RAPTOR",
            raptor_summarizer=summarizer,
            raptor_embedder=embedder,
        )

    if isinstance(config.clustering_config, dict):
        cluster_config = dict(config.clustering_config)
        cluster_config.setdefault("strategy", "RAPTOR")
        cluster_config["raptor_summarizer"] = summarizer
        cluster_config["raptor_embedder"] = embedder
        return cluster_config

    for field_name, value in (
        ("raptor_summarizer", summarizer),
        ("raptor_embedder", embedder),
    ):
        try:
            setattr(config.clustering_config, field_name, value)
        except (AttributeError, TypeError):
            pass
    return config.clustering_config


def _build_coherent_cluster_promotion(
    cluster: _NormalizedCluster,
    *,
    prepared: _Tier1DistillationInput,
    texts: Sequence[str],
    embeddings: object,
    coherence: float,
) -> _CoherentClusterPromotion:
    member_texts = [texts[index] for index in cluster.member_indices]
    summary = cluster.summary or _fallback_cluster_summary(member_texts)
    member_items = [prepared.notes[index] for index in cluster.member_indices]
    source_note_ids = [
        str(getattr(item.note, "note_id"))
        for item in member_items
        if getattr(item.note, "note_id", None)
    ]
    return _CoherentClusterPromotion(
        cluster=cluster,
        coherence=coherence,
        summary=summary,
        source_note_ids=_dedupe_preserving_order(source_note_ids),
        importance=_mean_probability(
            [item.effective_importance for item in member_items]
        ),
        unresolvedness=_mean_probability(
            [float(getattr(item.note, "unresolvedness", 0.0)) for item in member_items]
        ),
        centroid=_centroid(
            [_vector_at(embeddings, index) for index in cluster.member_indices]
        ),
    )


def _fallback_cluster_summary(texts: Sequence[str]) -> str:
    return "\n\n".join(str(text) for text in texts)


def _normalize_cluster_result(
    result: object,
    *,
    note_count: int,
) -> _NormalizedClusterResult:
    clusters_payload = _result_value(result, "clusters")
    if clusters_payload is not None:
        clusters = [
            _normalize_cluster(cluster, fallback_id=f"cluster-{index}")
            for index, cluster in enumerate(clusters_payload)
        ]
        return _NormalizedClusterResult(
            clusters=[
                cluster
                for cluster in clusters
                if _valid_member_indices(cluster.member_indices, note_count)
            ],
            noise_indices=_normalize_index_set(
                _result_value(result, "noise_indices", "noise", "outliers"),
                note_count,
            ),
            tree_depth=_normalize_tree_depth(result),
        )

    labels = _result_value(result, "labels", "assignments")
    if labels is not None:
        grouped: dict[str, list[int]] = {}
        noise_indices: set[int] = set()
        for index, label in enumerate(labels):
            if index >= note_count:
                break
            if label in (None, -1, "noise", "outlier"):
                noise_indices.add(index)
            else:
                grouped.setdefault(str(label), []).append(index)
        return _NormalizedClusterResult(
            clusters=[
                _NormalizedCluster(cluster_id=cluster_id, member_indices=indices)
                for cluster_id, indices in grouped.items()
            ],
            noise_indices=noise_indices,
            tree_depth=_normalize_tree_depth(result),
        )

    return _NormalizedClusterResult(
        clusters=[],
        noise_indices=set(range(note_count)),
        tree_depth=_normalize_tree_depth(result),
    )


def _normalize_cluster(cluster: object, *, fallback_id: str) -> _NormalizedCluster:
    member_indices = _result_value(
        cluster,
        "member_indices",
        "indices",
        "note_indices",
        "members",
    )
    return _NormalizedCluster(
        cluster_id=str(_result_value(cluster, "cluster_id", "id", default=fallback_id)),
        member_indices=[int(index) for index in member_indices or []],
        summary=_optional_string(_result_value(cluster, "summary", "text")),
    )


def _result_value(
    value: object,
    *names: str,
    default: object | None = None,
) -> object | None:
    if isinstance(value, Mapping):
        for name in names:
            if name in value:
                return value[name]
        return default

    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _normalize_index_set(value: object, note_count: int) -> set[int]:
    if value is None:
        return set()
    return {
        int(index)
        for index in value
        if isinstance(index, int) and 0 <= index < note_count
    }


def _valid_member_indices(indices: Sequence[int], note_count: int) -> bool:
    return bool(indices) and all(0 <= index < note_count for index in indices)


def _normalize_tree_depth(result: object) -> int:
    depth = _result_value(result, "tree_depth", "depth", "raptor_depth", default=1)
    try:
        return max(0, int(depth))
    except (TypeError, ValueError):
        return 0


def _optional_string(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _mean_pairwise_similarity(vectors: Sequence[object]) -> float:
    if len(vectors) < 2:
        return 1.0

    similarities: list[float] = []
    for left_index, left in enumerate(vectors):
        for right in vectors[left_index + 1 :]:
            similarities.append(_cosine_similarity(left, right))
    if not similarities:
        return 1.0
    return sum(similarities) / len(similarities)


def _cosine_similarity(left: object, right: object) -> float:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values):
        return 0.0

    left_norm = math.sqrt(sum(value * value for value in left_values))
    right_norm = math.sqrt(sum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    dot = sum(
        left_value * right_value
        for left_value, right_value in zip(left_values, right_values, strict=True)
    )
    return dot / (left_norm * right_norm)


def _vector_at(vectors: object, index: int) -> object:
    return vectors[index]


def _centroid(vectors: Sequence[object]) -> object:
    if not vectors:
        return None
    return np.asarray(vectors, dtype=float).mean(axis=0)


def _note_content(note: object) -> str:
    content = getattr(note, "content", None)
    if content is not None:
        return str(content)
    title = getattr(note, "title", None)
    if title is not None:
        return str(title)
    return str(getattr(note, "note_id", ""))


def _pattern_note_payload(note: object) -> Mapping[str, object]:
    return {
        "note_id": str(getattr(note, "note_id")),
        "cluster_group": _optional_string(getattr(note, "cluster_group", None)),
        "title": _optional_string(getattr(note, "title", None)),
        "content": _note_content(note),
        "importance": _numeric_score(getattr(note, "importance", 0.0)),
        "unresolvedness": _numeric_score(getattr(note, "unresolvedness", 0.0)),
        "tags": [str(tag) for tag in getattr(note, "tags", []) or []],
    }


def _validate_memory_store(memory_store: object) -> None:
    if memory_store is None:
        raise DistillationConfigError("memory_store is required")

    for method_name in _REQUIRED_MEMORY_STORE_METHODS:
        method = getattr(memory_store, method_name, None)
        if not isinstance(method, Callable):
            raise DistillationConfigError(f"memory_store must provide {method_name}()")

    if getattr(memory_store, "vault_path", None) is None:
        raise DistillationConfigError("memory_store must expose vault_path")


def _latest_datetime(*values: datetime | None) -> datetime | None:
    datetimes = [_ensure_aware(value) for value in values if value is not None]
    if not datetimes:
        return None
    return max(datetimes)


def _elapsed_since(value: datetime | None, now: datetime) -> timedelta | None:
    if value is None:
        return None
    return now - _ensure_aware(value)


def _days_since(value: datetime | None, now: datetime) -> int | None:
    elapsed = _elapsed_since(value, now)
    if elapsed is None:
        return None
    return elapsed.days


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_metadata_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_metadata_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat(timespec="seconds")


def _feedback_boosts_by_note_id(feedback_events: Sequence[object]) -> dict[str, float]:
    boosts: dict[str, float] = {}
    for event in feedback_events:
        boost = max(0.0, float(getattr(event, "importance", 0.0))) * 0.1
        for note_id in _feedback_referenced_note_ids(event):
            boosts[note_id] = _clamp_probability(boosts.get(note_id, 0.0) + boost)
    return boosts


def _feedback_referenced_note_ids(feedback_event: object) -> set[str]:
    note_ids = {str(note_id) for note_id in getattr(feedback_event, "links", []) if note_id}
    friction_target = getattr(feedback_event, "friction_target", None)
    if friction_target:
        note_ids.add(str(friction_target))
    return note_ids


def _criterion_feedback_metrics(
    feedback_events: Sequence[object],
) -> list[_CriterionFeedbackMetric]:
    grouped: dict[str, list[float]] = {}
    for event in feedback_events:
        engagement = _feedback_engagement_score(event)
        for criterion_name in _feedback_criterion_names(event):
            grouped.setdefault(criterion_name, []).append(engagement)

    return [
        _CriterionFeedbackMetric(
            criterion_name=criterion_name,
            feedback_count=len(scores),
            engaged_count=sum(1 for score in scores if score >= 0.5),
            engagement_rate=_clamp_probability(
                sum(1 for score in scores if score >= 0.5) / len(scores)
            ),
            mean_engagement=_mean_probability(scores),
        )
        for criterion_name, scores in sorted(grouped.items())
        if scores
    ]


def _feedback_engagement_score(feedback_event: object) -> float:
    return _clamp_probability(
        max(
            _numeric_score(getattr(feedback_event, "importance", 0.0)),
            _numeric_score(getattr(feedback_event, "unresolvedness", 0.0)),
        )
    )


def _numeric_score(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _feedback_criterion_names(feedback_event: object) -> list[str]:
    names: list[str] = []
    for tag in getattr(feedback_event, "tags", []) or []:
        tag_text = str(tag).strip()
        for separator in (":", "="):
            prefix = f"criterion{separator}"
            if tag_text.startswith(prefix):
                name = _normalize_criterion_name(tag_text[len(prefix) :])
                if name is not None:
                    names.append(name)

    if getattr(feedback_event, "friction_target", None):
        names.append("friction")

    return _dedupe_preserving_order(names)


def _normalize_criterion_name(value: str) -> str | None:
    normalized = value.strip().lower().replace(" ", "_")
    if not normalized:
        return None
    return normalized


def _clamp_probability(value: float) -> float:
    return min(1.0, max(0.0, value))


def _mean_probability(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return _clamp_probability(sum(float(value) for value in values) / len(values))


def _dedupe_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _cluster_title(
    cluster_group: str,
    summary: str,
    *,
    existing_title: str | None = None,
) -> str:
    if existing_title:
        return existing_title
    first_line = next((line.strip() for line in summary.splitlines() if line.strip()), "")
    title = first_line or f"Distilled pattern {cluster_group}"
    if len(title) > 140:
        title = title[:137].rstrip() + "..."
    return title


def _merged_cluster_content(existing_content: str, new_summary: str) -> str:
    if not existing_content:
        return new_summary
    if new_summary in existing_content:
        return existing_content
    return f"{existing_content.rstrip()}\n\n---\n\n{new_summary}"


def _assertion_cache_path(cache_dir: Path, cluster_group: str) -> Path:
    cluster_group = cluster_group.strip()
    if not cluster_group:
        raise DistillationError("cluster_group is required for assertion cache")
    if "/" in cluster_group or "\\" in cluster_group:
        raise DistillationError(
            f"cluster_group cannot contain path separators: {cluster_group!r}"
        )
    return cache_dir / f"{cluster_group}.json"


def _assertion_cache_json(payload: _AssertionCachePayload) -> Mapping[str, object]:
    return {
        "cluster_group": payload.cluster_group,
        "cluster_summary": payload.summary,
        "assertions": [
            {
                "text": assertion.text,
                "confidence": assertion.confidence,
            }
            for assertion in payload.assertions
        ],
    }
