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


def test_filter_content_non_empty_scores_prompt_without_annotations(
    monkeypatch,
) -> None:
    import phosphene.attention_filter.filter as filter_module

    density = metrics()
    embeddings = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
    embedding_calls: list[tuple[list[str], object]] = []
    embedding_config = object()
    store = FakeMemoryStore(
        density,
        [
            [(FakeNote("note-a", unresolvedness=0.5), 0.9)],
            [(FakeNote("note-b", unresolvedness=0.25), 0.8)],
        ],
    )

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        embedding_calls.append((texts, config))
        return EmbeddingResult(vectors=[embeddings[len(embedding_calls) - 1]])

    def fake_complete(**_kwargs: object) -> str:
        return '{"scores": {"precision_surplus": 0.9}}'

    monkeypatch.setattr(filter_module, "_toolkit_embed", fake_embed)
    monkeypatch.setattr(filter_module, "_toolkit_complete", fake_complete)

    result = AttentionFilter(store).filter_content(
        [make_item("first"), make_item("second")],
        make_config(embedding_config=embedding_config, similarity_candidates=5),
    )

    assert store.density_calls == 1
    assert embedding_calls == [(["first"], embedding_config), (["second"], embedding_config)]
    assert [limit for _, limit in store.search_calls] == [5, 5]
    assert np.array_equal(store.search_calls[0][0], embeddings[0])
    assert np.array_equal(store.search_calls[1][0], embeddings[1])
    assert store.write_calls == 0
    assert result.accepted == []
    assert result.rejected_count == 0
    assert result.total_count == 2
    assert result.prompt_weight == 0.65
    assert result.structure_weight == 0.35
    assert result.density_snapshot is density


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
        return '{"scores": {"precision_surplus": 0.8, "custom": 0.2}}'

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

    assert llm_calls == 1
    assert len(evaluations) == 1
    evaluation = evaluations[0]
    assert evaluation.retrieval.note_ids == ["note-a"]
    assert evaluation.structural.connections == ("note-a",)
    assert evaluation.prompt_scores == {"precision_surplus": 0.8, "custom": 0.2}
    assert evaluation.prompt_score == pytest.approx((0.8 * 4.0 + 0.2) / 5.0)
    assert evaluation.structural.structure_score == pytest.approx((0.5 + 0.45) / 2.0)
    assert evaluation.composite_score == pytest.approx(
        evaluation.prompt_score * 0.6
        + evaluation.structural.structure_score * 0.4
    )
