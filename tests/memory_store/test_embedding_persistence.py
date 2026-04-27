from pathlib import Path

import numpy as np

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NotePatch, NoteQuery


def make_store(tmp_path: Path, *, embeddings: bool = True) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if embeddings else None,
        )
    )


def test_store_get_round_trip_preserves_embedding(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    embedding = np.array([0.1, 0.2, 0.3])

    note_id = store.store_note(NoteInput(tier=1, content="Body", title="Title", embedding=embedding))

    assert np.array_equal(store.get_note(note_id).embedding, embedding)


def test_update_note_overwrites_stored_embedding(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(
        NoteInput(tier=1, content="Body", title="Title", embedding=np.array([1.0, 0.0]))
    )
    replacement = np.array([0.0, 1.0])

    updated = store.update_note(note_id, NotePatch(embedding=replacement))

    assert np.array_equal(updated.embedding, replacement)
    assert np.array_equal(store.get_note(note_id).embedding, replacement)


def test_get_note_returns_none_when_no_embedding_was_stored(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(NoteInput(tier=1, content="Body", title="Title"))

    assert store.get_note(note_id).embedding is None


def test_query_notes_populates_embeddings_on_returned_notes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    embedded = np.array([0.4, 0.5, 0.6])
    embedded_id = store.store_note(
        NoteInput(tier=1, content="Embedded", title="Embedded", tags=["query"], embedding=embedded)
    )
    plain_id = store.store_note(NoteInput(tier=1, content="Plain", title="Plain", tags=["query"]))

    notes = {note.note_id: note for note in store.query_notes(NoteQuery(tags=["query"]))}

    assert np.array_equal(notes[embedded_id].embedding, embedded)
    assert notes[plain_id].embedding is None


def test_none_embedding_path_discards_store_and_update_embeddings(tmp_path: Path) -> None:
    store = make_store(tmp_path, embeddings=False)
    note_id = store.store_note(
        NoteInput(tier=1, content="Body", title="Title", embedding=np.array([1.0, 2.0]))
    )

    assert store.get_note(note_id).embedding is None

    updated = store.update_note(note_id, NotePatch(embedding=np.array([3.0, 4.0])))

    assert updated.embedding is None
    assert store.get_note(note_id).embedding is None


def test_reinitialized_store_loads_embedding_from_sidecar_file(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    embedding_path = tmp_path / "embeddings"
    embedding = np.array([0.7, 0.8])
    store = MemoryStore(
        MemoryStoreConfig(vault_path=str(vault_path), embedding_path=str(embedding_path))
    )
    note_id = store.store_note(NoteInput(tier=1, content="Body", title="Title", embedding=embedding))

    reloaded = MemoryStore(
        MemoryStoreConfig(vault_path=str(vault_path), embedding_path=str(embedding_path))
    )

    assert np.array_equal(reloaded.get_note(note_id).embedding, embedding)


def test_embedding_directory_is_created_lazily_on_first_store(tmp_path: Path) -> None:
    embedding_path = tmp_path / "missing-embeddings"
    store = MemoryStore(
        MemoryStoreConfig(vault_path=str(tmp_path / "vault"), embedding_path=str(embedding_path))
    )

    note_id = store.store_note(
        NoteInput(tier=1, content="Body", title="Title", embedding=np.array([0.1]))
    )

    assert embedding_path.is_dir()
    assert (embedding_path / f"{note_id}.npy").exists()
