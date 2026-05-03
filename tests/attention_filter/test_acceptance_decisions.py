from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np

from phosphene.attention_filter import AttentionFilter, AttentionFilterConfig, ContentItem
from phosphene.attention_filter.filter import (
    _FrictionPreparation,
    _GeneratedAnnotation,
    _IncomingAssertion,
    _ItemEvaluation,
    _ItemRetrievalContext,
    _MemoryStructuralEvaluation,
    _SimilarNoteContext,
    _accepted_evaluations,
    _assemble_annotated_fragment,
    _assemble_annotated_fragments,
    _decide_batch_retention,
    _decide_retention,
    _rejected_count,
)
from phosphene.memory_store import DensityMetrics


@dataclass
class EmbeddingResult:
    vectors: list[np.ndarray]


@dataclass
class FakeNote:
    note_id: str
    unresolvedness: float
    tier: int = 1
    title: str = "title"
    importance: float = 0.0
    link_count: int = 0
    tags: list[str] | None = None
    source: str | None = None
    friction_target: str | None = None
    cluster_group: str | None = None

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


class FakeMemoryStore:
    def __init__(self, metrics: DensityMetrics) -> None:
        self.metrics = metrics
        self.write_calls = 0

    def get_density_metrics(self) -> DensityMetrics:
        return self.metrics

    def search_by_embedding(
        self, _embedding: np.ndarray, *, limit: int
    ) -> list[tuple[FakeNote, float]]:
        return [(FakeNote("note-a", unresolvedness=0.5), 0.9)][:limit]

    def store_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def update_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def make_item(source: str = "rss") -> ContentItem:
    return ContentItem(
        content="incoming content",
        source=source,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        url="https://example.test/incoming",
        linked_urls=["https://example.test/linked"],
    )


def make_evaluation(
    *,
    composite_score: float,
    source: str = "rss",
    prompt_scores: dict[str, float] | None = None,
    structure_scores: dict[str, float] | None = None,
) -> _ItemEvaluation:
    similar_note = _SimilarNoteContext(
        note_id="note-a",
        similarity=0.9,
        unresolvedness=0.5,
        metadata={
            "tier": 1,
            "title": "title",
            "importance": 0.0,
            "link_count": 0,
            "tags": [],
            "source": None,
            "friction_target": None,
            "cluster_group": None,
        },
    )
    retrieval = _ItemRetrievalContext(
        item=make_item(source),
        embedding=np.array([1.0, 0.0]),
        similar_notes=(similar_note,),
    )
    structural = _MemoryStructuralEvaluation(
        scores=structure_scores or {},
        structure_score=0.4,
        connections=("note-a",),
        friction_target="note-a",
    )
    return _ItemEvaluation(
        retrieval=retrieval,
        structural=structural,
        prompt_scores=prompt_scores or {},
        prompt_score=0.6,
        incoming_assertions=(_IncomingAssertion("claim", 0.8),),
        friction_preparation=_FrictionPreparation(
            incoming_assertions=(_IncomingAssertion("claim", 0.8),),
            cached_clusters=(),
        ),
        composite_score=composite_score,
        prompt_weight=0.7,
        structure_weight=0.3,
    )


def metrics() -> DensityMetrics:
    return DensityMetrics(
        note_count=50,
        tier_counts={1: 50, 2: 0, 3: 0},
        mean_link_degree=3.0,
        cluster_count=3,
        unresolved_count=1,
        max_unresolvedness=0.5,
    )


def test_threshold_accepts_exact_edge_and_rejects_below() -> None:
    config = make_config(acceptance_threshold=0.3)

    edge = _decide_retention(
        make_evaluation(
            composite_score=0.3,
            prompt_scores={"precision_surplus": 0.5},
        ),
        config,
    )
    below = _decide_retention(
        make_evaluation(
            composite_score=0.299,
            prompt_scores={"precision_surplus": 0.5},
        ),
        config,
    )

    assert edge.accepted is True
    assert edge.auto_accepted is False
    assert edge.retention_criteria == ("precision_surplus",)
    assert below.accepted is False
    assert below.retention_criteria == ()


def test_auto_accept_source_bypasses_low_score_threshold() -> None:
    decision = _decide_retention(
        make_evaluation(
            composite_score=0.0,
            source="human_share",
            prompt_scores={"precision_surplus": 0.2},
        ),
        make_config(
            acceptance_threshold=1.0,
            auto_accept_sources=["human_share"],
        ),
    )

    assert decision.accepted is True
    assert decision.auto_accepted is True
    assert decision.retention_criteria == ("precision_surplus",)


def test_zero_score_non_bypass_item_is_rejected_without_criteria() -> None:
    decision = _decide_retention(
        make_evaluation(
            composite_score=0.0,
            prompt_scores={"precision_surplus": 0.0},
            structure_scores={"link_density": 0.0},
        ),
        make_config(acceptance_threshold=0.01),
    )

    assert decision.accepted is False
    assert decision.retention_criteria == ()


def test_retention_criteria_are_attributed_from_prompt_and_structure_maps() -> None:
    decision = _decide_retention(
        make_evaluation(
            composite_score=0.8,
            prompt_scores={
                "precision_surplus": 0.7,
                "custom": 0.0,
                "link_density": 0.2,
            },
            structure_scores={
                "link_density": 0.6,
                "unresolvedness_affinity": 0.4,
            },
        ),
        make_config(acceptance_threshold=0.8),
    )

    assert decision.retention_criteria == (
        "link_density",
        "precision_surplus",
        "unresolvedness_affinity",
    )


def test_batch_decisions_report_accepted_evaluations_and_rejected_count() -> None:
    accepted = make_evaluation(composite_score=0.6)
    rejected = make_evaluation(composite_score=0.2)
    auto_accepted = make_evaluation(composite_score=0.0, source="human_share")

    decisions = _decide_batch_retention(
        (accepted, rejected, auto_accepted),
        make_config(acceptance_threshold=0.5, auto_accept_sources=["human_share"]),
    )

    assert _accepted_evaluations(decisions) == (accepted, auto_accepted)
    assert _rejected_count(decisions) == 1


def test_annotated_fragment_assembly_maps_public_contract_fields() -> None:
    evaluation = make_evaluation(
        composite_score=0.72,
        prompt_scores={"precision_surplus": 0.6},
        structure_scores={"link_density": 0.5, "unresolvedness_affinity": 0.35},
    )

    fragment = _assemble_annotated_fragment(
        _GeneratedAnnotation(evaluation, "Retained for precise friction."),
        ("precision_surplus", "link_density", "unresolvedness_affinity"),
    )

    assert fragment.content == "incoming content"
    assert fragment.annotation == "Retained for precise friction."
    assert fragment.importance_score == 0.72
    assert fragment.unresolvedness == 0.35
    assert fragment.retention_criteria == [
        "precision_surplus",
        "link_density",
        "unresolvedness_affinity",
    ]
    assert fragment.prompt_score == 0.6
    assert fragment.structure_score == 0.4
    assert fragment.friction_target == "note-a"
    assert fragment.connections == ["note-a"]
    assert fragment.source == "rss"
    assert fragment.timestamp == datetime(2026, 1, 1, tzinfo=UTC)
    assert fragment.url == "https://example.test/incoming"
    assert fragment.linked_urls == ["https://example.test/linked"]
    assert np.array_equal(fragment.embedding, np.array([1.0, 0.0]))


def test_batch_assembly_uses_accepted_decision_retention_criteria() -> None:
    accepted = make_evaluation(
        composite_score=0.6,
        prompt_scores={"precision_surplus": 0.5},
    )
    rejected = make_evaluation(
        composite_score=0.2,
        prompt_scores={"precision_surplus": 0.5},
    )
    decisions = _decide_batch_retention(
        (accepted, rejected),
        make_config(acceptance_threshold=0.5),
    )

    fragments = _assemble_annotated_fragments(
        (_GeneratedAnnotation(accepted, "Accepted annotation."),),
        decisions,
    )

    assert len(fragments) == 1
    assert fragments[0].annotation == "Accepted annotation."
    assert fragments[0].retention_criteria == ["precision_surplus"]


def test_filter_content_reports_rejected_count_without_memory_writes(monkeypatch) -> None:
    import phosphene.attention_filter.filter as filter_module

    store = FakeMemoryStore(metrics())

    def fake_embed(texts: list[str], _config: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[np.array([float(len(texts[0])), 0.0])])

    def fake_complete(**kwargs: object) -> str:
        task = __import__("json").loads(kwargs["messages"][0]["content"])["task"]
        if task == "score_attention_filter_prompt_criteria":
            return '{"scores": {"precision_surplus": 0.0}}'
        if task == "extract_attention_filter_incoming_assertions":
            return '{"assertions": []}'
        return '{"annotation": "Auto accepted source annotation."}'

    monkeypatch.setattr(filter_module, "_toolkit_embed", fake_embed)
    monkeypatch.setattr(filter_module, "_toolkit_complete", fake_complete)

    result = AttentionFilter(store).filter_content(
        [make_item("rss"), make_item("human_share")],
        make_config(
            acceptance_threshold=0.5,
            auto_accept_sources=["human_share"],
        ),
    )

    assert len(result.accepted) == 1
    assert result.accepted[0].source == "human_share"
    assert result.accepted[0].annotation == "Auto accepted source annotation."
    assert result.rejected_count == 1
    assert result.total_count == 2
    assert store.write_calls == 0
