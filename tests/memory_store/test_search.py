from pathlib import Path

import numpy as np
import pytest

from phosphene.memory_store import (
    DimensionMismatchError,
    InvalidTierError,
    MemoryStore,
    MemoryStoreConfig,
    NoteInput,
)


def make_store(tmp_path: Path, *, embeddings: bool = True) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if embeddings else None,
        )
    )


def store_note(
    store: MemoryStore,
    title: str,
    embedding: np.ndarray | None,
    *,
    tier: int = 1,
    links: list[str] | None = None,
) -> str:
    return store.store_note(
        NoteInput(
            tier=tier,
            content=f"{title} body",
            title=title,
            embedding=embedding,
            links=list(links or []),
        )
    )


def result_titles(results: list[tuple]) -> list[str]:
    return [note.title for note, _ in results]


def test_search_by_embedding_ranks_by_cosine_similarity(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "close", np.array([1.0, 0.1]))
    store_note(store, "middle", np.array([0.6, 0.8]))
    store_note(store, "far", np.array([0.0, 1.0]))

    results = store.search_by_embedding(np.array([1.0, 0.0]))

    assert result_titles(results) == ["close", "middle", "far"]
    assert results[0][1] > results[1][1] > results[2][1]


def test_search_by_embedding_filters_by_tier(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "tier one", np.array([1.0, 0.0]), tier=1)
    store_note(store, "tier two", np.array([0.9, 0.1]), tier=2)

    results = store.search_by_embedding(np.array([1.0, 0.0]), tier=2)

    assert result_titles(results) == ["tier two"]


def test_search_by_embedding_limit_truncates_results(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    for idx in range(5):
        store_note(store, f"note {idx}", np.array([1.0, float(idx)]))

    results = store.search_by_embedding(np.array([1.0, 0.0]), limit=2)

    assert len(results) == 2


def test_search_by_embedding_skips_notes_without_embeddings(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    embedded_id = store_note(store, "embedded", np.array([1.0, 0.0]))
    store_note(store, "plain", None)

    results = store.search_by_embedding(np.array([1.0, 0.0]))

    assert [note.note_id for note, _ in results] == [embedded_id]
    assert np.array_equal(results[0][0].embedding, np.array([1.0, 0.0]))


def test_search_by_embedding_raises_for_dimension_mismatch(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "two dimensions", np.array([1.0, 0.0]))

    with pytest.raises(DimensionMismatchError):
        store.search_by_embedding(np.array([1.0, 0.0, 0.0]))


def test_search_by_embedding_returns_empty_when_embedding_path_is_none(tmp_path: Path) -> None:
    store = make_store(tmp_path, embeddings=False)
    store_note(store, "discarded", np.array([1.0, 0.0]))

    assert store.search_by_embedding(np.array([1.0, 0.0])) == []


def test_search_by_embedding_returns_empty_when_no_notes_have_embeddings(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "plain one", None)
    store_note(store, "plain two", None)

    assert store.search_by_embedding(np.array([1.0, 0.0])) == []


def test_search_by_embedding_rejects_invalid_tier(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(InvalidTierError):
        store.search_by_embedding(np.array([1.0, 0.0]), tier=4)


def test_search_by_embedding_skips_zero_norm_vectors(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "zero", np.array([0.0, 0.0]))
    store_note(store, "nonzero", np.array([1.0, 0.0]))

    assert result_titles(store.search_by_embedding(np.array([1.0, 0.0]))) == ["nonzero"]
    assert store.search_by_embedding(np.array([0.0, 0.0])) == []


def test_search_by_embedding_returns_inbound_augmented_link_count(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store_note(store, "target", np.array([1.0, 0.0]))
    store_note(store, "source", np.array([0.0, 1.0]), links=[target_id])

    results = store.search_by_embedding(np.array([1.0, 0.0]), limit=1)

    assert results[0][0].note_id == target_id
    assert results[0][0].link_count == 1
