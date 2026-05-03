from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np

from phosphene.attention_filter import AttentionFilterConfig, ContentItem
from phosphene.attention_filter.filter import _prepare_retrieval_contexts


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
    def __init__(self, results_by_call: list[list[tuple[FakeNote, float]]]) -> None:
        self.results_by_call = results_by_call
        self.search_calls: list[tuple[np.ndarray, int]] = []
        self.write_calls = 0

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


def make_item(content: str) -> ContentItem:
    return ContentItem(
        content=content,
        source="rss",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_retrieval_context_embeds_and_searches_once_per_item_with_limit() -> None:
    embeddings = [np.array([1.0, 0.0]), np.array([0.0, 1.0])]
    embedding_calls: list[tuple[list[str], object]] = []
    embedding_config = object()
    store = FakeMemoryStore([[], []])

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        embedding_calls.append((texts, config))
        return EmbeddingResult(vectors=[embeddings[len(embedding_calls) - 1]])

    items = [make_item("first"), make_item("second")]
    contexts = _prepare_retrieval_contexts(
        store,
        items,
        make_config(embedding_config=embedding_config, similarity_candidates=7),
        embedding_callable=fake_embed,
    )

    assert embedding_calls == [(["first"], embedding_config), (["second"], embedding_config)]
    assert [limit for _, limit in store.search_calls] == [7, 7]
    assert np.array_equal(store.search_calls[0][0], embeddings[0])
    assert np.array_equal(store.search_calls[1][0], embeddings[1])
    assert np.array_equal(contexts[0].embedding, embeddings[0])
    assert np.array_equal(contexts[1].embedding, embeddings[1])
    assert store.write_calls == 0


def test_retrieval_context_preserves_note_ids_scores_and_metadata_order() -> None:
    embedding = np.array([0.5, 0.5])
    notes = [
        (
            FakeNote(
                note_id="note-b",
                unresolvedness=0.7,
                tier=2,
                title="Second",
                importance=0.4,
                link_count=3,
                tags=["cluster"],
                source="corpus",
                friction_target="note-a",
                cluster_group="group-1",
            ),
            0.82,
        ),
        (
            FakeNote(
                note_id="note-a",
                unresolvedness=0.2,
                title="First",
                tags=["precision"],
            ),
            0.61,
        ),
    ]
    store = FakeMemoryStore([notes])

    def fake_embed(_texts: list[str], _config: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[embedding])

    context = _prepare_retrieval_contexts(
        store,
        [make_item("incoming")],
        make_config(),
        embedding_callable=fake_embed,
    )[0]

    assert context.note_ids == ["note-b", "note-a"]
    assert context.similarities == [0.82, 0.61]
    assert context.unresolvedness_scores == [0.7, 0.2]
    assert context.similar_notes[0].metadata == {
        "tier": 2,
        "title": "Second",
        "importance": 0.4,
        "link_count": 3,
        "tags": ["cluster"],
        "source": "corpus",
        "friction_target": "note-a",
        "cluster_group": "group-1",
    }


def test_retrieval_context_allows_zero_candidates() -> None:
    embedding = np.array([0.1, 0.2])
    store = FakeMemoryStore([[]])

    def fake_embed(_texts: list[str], _config: object) -> EmbeddingResult:
        return EmbeddingResult(vectors=[embedding])

    context = _prepare_retrieval_contexts(
        store,
        [make_item("incoming")],
        make_config(),
        embedding_callable=fake_embed,
    )[0]

    assert context.similar_notes == ()
    assert context.note_ids == []
    assert context.similarities == []
    assert context.unresolvedness_scores == []
