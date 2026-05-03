from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import pytest

from phosphene.attention_filter import AttentionFilterConfig, ContentItem, ScoringConfig
from phosphene.attention_filter.filter import (
    _compute_memory_structural_evaluation,
    _prepare_retrieval_contexts,
)


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
    def __init__(self, results: list[tuple[FakeNote, float]]) -> None:
        self.results = results
        self.search_calls = 0

    def search_by_embedding(
        self, _embedding: np.ndarray, *, limit: int
    ) -> list[tuple[FakeNote, float]]:
        self.search_calls += 1
        return self.results[:limit]


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def make_context(
    results: list[tuple[FakeNote, float]],
    config: AttentionFilterConfig,
):
    def fake_embed(_texts: list[str], _config: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[np.array([1.0, 0.0])])

    return _prepare_retrieval_contexts(
        FakeMemoryStore(results),
        [
            ContentItem(
                content="incoming",
                source="rss",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            )
        ],
        config,
        embedding_callable=fake_embed,
    )[0]


def test_memory_structural_scores_use_retrieved_candidate_metadata() -> None:
    config = make_config(similarity_candidates=4)
    context = make_context(
        [
            (FakeNote("note-a", unresolvedness=0.5), 0.9),
            (FakeNote("note-b", unresolvedness=0.2), 0.7),
            (FakeNote("note-c", unresolvedness=0.9), 0.1),
        ],
        config,
    )

    evaluation = _compute_memory_structural_evaluation(context, config)

    assert evaluation.scores["link_density"] == pytest.approx(0.5)
    assert evaluation.scores["unresolvedness_affinity"] == pytest.approx(0.68)
    assert evaluation.structure_score == pytest.approx(0.59)
    assert evaluation.friction_target is None


def test_memory_structural_connections_require_similarity_above_threshold() -> None:
    config = make_config(
        scoring=ScoringConfig(link_density_sim_threshold=0.7),
        similarity_candidates=3,
    )
    context = make_context(
        [
            (FakeNote("above", unresolvedness=0.0), 0.71),
            (FakeNote("at-threshold", unresolvedness=0.0), 0.7),
            (FakeNote("below", unresolvedness=0.0), 0.69),
        ],
        config,
    )

    evaluation = _compute_memory_structural_evaluation(context, config)

    assert evaluation.connections == ("above",)
    assert evaluation.scores["link_density"] == pytest.approx(1 / 3)


def test_memory_structural_scores_are_zero_without_candidates() -> None:
    config = make_config()
    context = make_context([], config)

    evaluation = _compute_memory_structural_evaluation(context, config)

    assert evaluation.connections == ()
    assert evaluation.scores == {
        "link_density": 0.0,
        "unresolvedness_affinity": 0.0,
    }
    assert evaluation.structure_score == 0.0
    assert evaluation.friction_target is None
