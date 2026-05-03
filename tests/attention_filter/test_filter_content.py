import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pytest

from phosphene.attention_filter import (
    AttentionFilter,
    AttentionFilterConfig,
    ContentItem,
    FilterCriterion,
    ScoringConfig,
)
from phosphene.attention_filter.filter import _evaluate_items
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
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    friction_target: str | None = None
    cluster_group: str | None = None


class FakeMemoryStore:
    def __init__(
        self,
        metrics: DensityMetrics,
        results_by_call: list[list[tuple[FakeNote, float]]] | None = None,
    ) -> None:
        self.metrics = metrics
        self.results_by_call = results_by_call or []
        self.density_calls = 0
        self.search_calls: list[tuple[np.ndarray, int]] = []
        self.write_calls = 0

    def get_density_metrics(self) -> DensityMetrics:
        self.density_calls += 1
        return self.metrics

    def search_by_embedding(
        self, embedding: np.ndarray, *, limit: int
    ) -> list[tuple[FakeNote, float]]:
        self.search_calls.append((embedding, limit))
        return self.results_by_call[len(self.search_calls) - 1]

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


def metrics(
    *,
    note_count: int = 50,
    cluster_count: int = 3,
    mean_link_degree: float = 3.75,
) -> DensityMetrics:
    return DensityMetrics(
        note_count=note_count,
        tier_counts={1: note_count, 2: 0, 3: 0},
        mean_link_degree=mean_link_degree,
        cluster_count=cluster_count,
        unresolved_count=2,
        max_unresolvedness=0.8,
    )


def test_filter_content_empty_batch_returns_density_snapshot_and_blend_weights() -> None:
    density = metrics()
    store = FakeMemoryStore(density)
    config = make_config(scoring=ScoringConfig(phase2_max_weight=0.8))

    result = AttentionFilter(store).filter_content([], config)

    assert store.density_calls == 1
    assert result.accepted == []
    assert result.rejected_count == 0
    assert result.total_count == 0
    assert result.prompt_weight == 0.6
    assert result.structure_weight == 0.4
    assert result.density_snapshot is density


def make_item(content: str) -> ContentItem:
    return ContentItem(
        content=content,
        source="rss",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        url="https://example.test/item",
        linked_urls=["https://example.test/linked"],
    )


def test_filter_content_non_empty_scores_prompt_and_generates_accepted_fragments(
    monkeypatch,
) -> None:
    import phosphene.attention_filter.filter as filter_module

    density = metrics()
    embeddings = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
    embedding_calls: list[tuple[list[str], object]] = []
    embedding_config = object()
    llm_config = object()
    llm_tier = object()
    assertion_tier = object()
    llm_calls: list[dict[str, object]] = []
    store = FakeMemoryStore(
        density,
        [
            [
                (
                    FakeNote(
                        "note-a",
                        unresolvedness=0.5,
                        cluster_group="cluster-a",
                    ),
                    0.9,
                )
            ],
            [
                (
                    FakeNote(
                        "note-b",
                        unresolvedness=0.25,
                        cluster_group="cluster-b",
                    ),
                    0.8,
                )
            ],
        ],
    )

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        embedding_calls.append((texts, config))
        return EmbeddingResult(vectors=[embeddings[len(embedding_calls) - 1]])

    def fake_complete(**kwargs: object) -> str:
        llm_calls.append(dict(kwargs))
        payload = json.loads(kwargs["messages"][0]["content"])
        task = payload["task"]
        if task == "score_attention_filter_prompt_criteria":
            return '{"scores": {"precision_surplus": 0.9}}'
        if task == "extract_attention_filter_incoming_assertions":
            return '{"assertions": [{"text": "incoming claim", "confidence": 0.8}]}'
        return json.dumps(
            {
                "annotation": (
                    f"Annotation for {payload['content_item']['content']}."
                )
            }
        )

    monkeypatch.setattr(filter_module, "_toolkit_embed", fake_embed)
    monkeypatch.setattr(filter_module, "_toolkit_complete", fake_complete)

    result = AttentionFilter(store).filter_content(
        [make_item("first"), make_item("second")],
        make_config(
            embedding_config=embedding_config,
            llm_config=llm_config,
            llm_tier=llm_tier,
            assertion_extraction_tier=assertion_tier,
            similarity_candidates=5,
            acceptance_threshold=0.0,
            auto_accept_sources=["rss"],
        ),
    )

    assert store.density_calls == 1
    assert embedding_calls == [(["first"], embedding_config), (["second"], embedding_config)]
    assert [limit for _, limit in store.search_calls] == [5, 5]
    assert np.array_equal(store.search_calls[0][0], embeddings[0])
    assert np.array_equal(store.search_calls[1][0], embeddings[1])
    assert len(llm_calls) == 6
    assert [call["config"] for call in llm_calls] == [llm_config] * 6
    assert [call["tier"] for call in llm_calls] == [
        llm_tier,
        assertion_tier,
        llm_tier,
        assertion_tier,
        llm_tier,
        llm_tier,
    ]
    payloads = [
        json.loads(call["messages"][0]["content"]) for call in llm_calls
    ]
    assert [payload["task"] for payload in payloads] == [
        "score_attention_filter_prompt_criteria",
        "extract_attention_filter_incoming_assertions",
        "score_attention_filter_prompt_criteria",
        "extract_attention_filter_incoming_assertions",
        "generate_attention_filter_annotation",
        "generate_attention_filter_annotation",
    ]
    assert [payload["content_item"]["content"] for payload in payloads] == [
        "first",
        "first",
        "second",
        "second",
        "first",
        "second",
    ]
    assert payloads[0]["similar_notes"][0]["note_id"] == "note-a"
    assert payloads[0]["similar_notes"][0]["metadata"]["cluster_group"] == "cluster-a"
    assert payloads[2]["similar_notes"][0]["note_id"] == "note-b"
    assert payloads[2]["similar_notes"][0]["metadata"]["cluster_group"] == "cluster-b"
    assert payloads[1]["content_item"]["linked_urls"] == ["https://example.test/linked"]
    assert payloads[3]["content_item"]["url"] == "https://example.test/item"
    assert store.write_calls == 0
    assert len(result.accepted) == 2
    assert [fragment.content for fragment in result.accepted] == ["first", "second"]
    assert [fragment.annotation for fragment in result.accepted] == [
        "Annotation for first.",
        "Annotation for second.",
    ]
    assert [fragment.source for fragment in result.accepted] == ["rss", "rss"]
    assert [fragment.linked_urls for fragment in result.accepted] == [
        ["https://example.test/linked"],
        ["https://example.test/linked"],
    ]
    assert result.accepted[0].connections == ["note-a"]
    assert result.accepted[1].connections == ["note-b"]
    assert np.array_equal(result.accepted[0].embedding, embeddings[0])
    assert np.array_equal(result.accepted[1].embedding, embeddings[1])
    assert result.rejected_count == 0
    assert result.total_count == 2
    assert result.prompt_weight == 0.65
    assert result.structure_weight == 0.35
    assert result.density_snapshot is density


def test_filter_content_regression_mixed_batch_with_auto_accept_and_rejects(
    monkeypatch,
) -> None:
    import phosphene.attention_filter.filter as filter_module

    density = metrics()
    embeddings = [
        np.array([1.0, 0.0]),
        np.array([0.0, 1.0]),
        np.array([1.0, 1.0]),
    ]
    embedding_config = object()
    llm_config = object()
    llm_tier = object()
    assertion_tier = object()
    llm_calls: list[dict[str, object]] = []
    store = FakeMemoryStore(
        density,
        [
            [(FakeNote("accepted-note", unresolvedness=0.2), 0.9)],
            [(FakeNote("rejected-note", unresolvedness=0.0), 0.1)],
            [(FakeNote("human-note", unresolvedness=0.4), 0.2)],
        ],
    )

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        assert config is embedding_config
        return EmbeddingResult(vectors=[embeddings[len(store.search_calls)]])

    def fake_complete(**kwargs: object) -> str:
        llm_calls.append(dict(kwargs))
        payload = json.loads(kwargs["messages"][0]["content"])
        content = payload["content_item"]["content"]
        task = payload["task"]
        if task == "score_attention_filter_prompt_criteria":
            scores = {
                "accepted": 0.9,
                "rejected": 0.1,
                "human": 0.0,
            }
            return json.dumps({"scores": {"precision_surplus": scores[content]}})
        if task == "extract_attention_filter_incoming_assertions":
            return json.dumps(
                {"assertions": [{"text": f"{content} claim", "confidence": 0.6}]}
            )
        return json.dumps({"annotation": f"Annotation for {content}."})

    monkeypatch.setattr(filter_module, "_toolkit_embed", fake_embed)
    monkeypatch.setattr(filter_module, "_toolkit_complete", fake_complete)

    result = AttentionFilter(store).filter_content(
        [
            make_item("accepted"),
            make_item("rejected"),
            ContentItem(
                content="human",
                source="human_share",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            ),
        ],
        make_config(
            embedding_config=embedding_config,
            llm_config=llm_config,
            llm_tier=llm_tier,
            assertion_extraction_tier=assertion_tier,
            similarity_candidates=5,
            acceptance_threshold=0.5,
            auto_accept_sources=["human_share"],
        ),
    )

    payloads = [
        json.loads(call["messages"][0]["content"]) for call in llm_calls
    ]
    assert [payload["task"] for payload in payloads] == [
        "score_attention_filter_prompt_criteria",
        "extract_attention_filter_incoming_assertions",
        "score_attention_filter_prompt_criteria",
        "extract_attention_filter_incoming_assertions",
        "score_attention_filter_prompt_criteria",
        "extract_attention_filter_incoming_assertions",
        "generate_attention_filter_annotation",
        "generate_attention_filter_annotation",
    ]
    assert [payload["content_item"]["content"] for payload in payloads] == [
        "accepted",
        "accepted",
        "rejected",
        "rejected",
        "human",
        "human",
        "accepted",
        "human",
    ]
    assert [call["config"] for call in llm_calls] == [llm_config] * 8
    assert [call["tier"] for call in llm_calls] == [
        llm_tier,
        assertion_tier,
        llm_tier,
        assertion_tier,
        llm_tier,
        assertion_tier,
        llm_tier,
        llm_tier,
    ]
    assert [limit for _, limit in store.search_calls] == [5, 5, 5]
    assert np.array_equal(store.search_calls[0][0], embeddings[0])
    assert np.array_equal(store.search_calls[1][0], embeddings[1])
    assert np.array_equal(store.search_calls[2][0], embeddings[2])
    assert store.write_calls == 0

    assert result.total_count == 3
    assert result.rejected_count == 1
    assert [fragment.content for fragment in result.accepted] == ["accepted", "human"]
    assert [fragment.annotation for fragment in result.accepted] == [
        "Annotation for accepted.",
        "Annotation for human.",
    ]
    assert result.accepted[0].importance_score == pytest.approx(0.6515)
    assert result.accepted[0].prompt_score == pytest.approx(0.9)
    assert result.accepted[0].structure_score == pytest.approx(0.19)
    assert result.accepted[0].retention_criteria == [
        "precision_surplus",
        "link_density",
        "unresolvedness_affinity",
    ]
    assert result.accepted[0].connections == ["accepted-note"]
    assert result.accepted[1].source == "human_share"
    assert result.accepted[1].importance_score == pytest.approx(0.014)
    assert result.accepted[1].retention_criteria == ["unresolvedness_affinity"]
    assert result.prompt_weight == 0.65
    assert result.structure_weight == 0.35
    assert result.density_snapshot is density


def test_filter_content_prompt_only_mode_skips_assertion_extraction(
    monkeypatch,
) -> None:
    import phosphene.attention_filter.filter as filter_module

    density = metrics(note_count=2, cluster_count=0, mean_link_degree=0.0)
    embedding = np.array([1.0, 0.0])
    store = FakeMemoryStore(
        density,
        [[(FakeNote("note-a", unresolvedness=0.5), 0.9)]],
    )
    llm_calls: list[dict[str, object]] = []

    def fake_embed(_texts: list[str], _config: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[embedding])

    def fake_complete(**kwargs: object) -> str:
        llm_calls.append(dict(kwargs))
        payload = json.loads(kwargs["messages"][0]["content"])
        if payload["task"] == "score_attention_filter_prompt_criteria":
            return '{"scores": {"precision_surplus": 0.9}}'
        if payload["task"] == "extract_attention_filter_incoming_assertions":
            raise AssertionError("Phase 2 assertion extraction should be gated")
        return '{"annotation": "Prompt-only annotation."}'

    monkeypatch.setattr(filter_module, "_toolkit_embed", fake_embed)
    monkeypatch.setattr(filter_module, "_toolkit_complete", fake_complete)

    result = AttentionFilter(store).filter_content(
        [make_item("prompt-only")],
        make_config(acceptance_threshold=0.0),
    )

    payloads = [
        json.loads(call["messages"][0]["content"]) for call in llm_calls
    ]
    assert [payload["task"] for payload in payloads] == [
        "score_attention_filter_prompt_criteria",
        "generate_attention_filter_annotation",
    ]
    assert result.prompt_weight == 1.0
    assert result.structure_weight == 0.0
    assert len(result.accepted) == 1
    assert result.accepted[0].annotation == "Prompt-only annotation."


def test_private_item_evaluation_preserves_retrieval_and_blends_prompt_scores() -> None:
    embedding = np.array([1.0, 0.0])
    embedding_config = object()
    llm_config = object()
    llm_calls = 0
    store = FakeMemoryStore(
        metrics(),
        [[(FakeNote("note-a", unresolvedness=0.5), 0.9)]],
    )

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        assert texts == ["incoming"]
        assert config is embedding_config
        return EmbeddingResult(vectors=[embedding])

    def fake_complete(**kwargs: object) -> str:
        nonlocal llm_calls
        llm_calls += 1
        assert kwargs["config"] is llm_config
        task = json.loads(kwargs["messages"][0]["content"])["task"]
        if task == "score_attention_filter_prompt_criteria":
            return '{"scores": {"precision_surplus": 0.8, "custom": 0.2}}'
        return '{"assertions": [{"text": "incoming claim", "confidence": 0.7}]}'

    config = make_config(
        embedding_config=embedding_config,
        llm_config=llm_config,
        prompt_criteria=[
            FilterCriterion("precision_surplus", "Precision", weight=2.0),
            FilterCriterion("custom", "Custom", weight=1.0),
        ],
        scoring=ScoringConfig(
            precision_surplus_weight=2.0,
            link_density_weight=1.0,
            unresolvedness_affinity_weight=1.0,
        ),
        similarity_candidates=2,
    )

    evaluations = _evaluate_items(
        store,
        [make_item("incoming")],
        config,
        prompt_weight=0.6,
        structure_weight=0.4,
        embedding_callable=fake_embed,
        llm_complete_callable=fake_complete,
    )

    assert llm_calls == 2
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.retrieval.note_ids == ["note-a"]
    assert evaluation.structural.connections == ("note-a",)
    assert evaluation.prompt_scores == {"precision_surplus": 0.8, "custom": 0.2}
    assert [assertion.text for assertion in evaluation.incoming_assertions] == [
        "incoming claim"
    ]
    assert evaluation.incoming_assertions[0].confidence == pytest.approx(0.7)
    assert evaluation.friction_preparation.incoming_assertions is (
        evaluation.incoming_assertions
    )
    assert evaluation.friction_preparation.cached_clusters == ()
    assert evaluation.prompt_score == pytest.approx((0.8 * 4.0 + 0.2) / 5.0)
    assert evaluation.structural.structure_score == pytest.approx((0.5 + 0.45) / 2.0)
    assert evaluation.composite_score == pytest.approx(
        evaluation.prompt_score * 0.6
        + evaluation.structural.structure_score * 0.4
    )
