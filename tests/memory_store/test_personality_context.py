from datetime import timedelta
from pathlib import Path

import numpy as np

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NotePatch
from phosphene.memory_store.vault import note_path, serialize_note

EMPTY_VERSION_ID = "da39a3ee5e6b4b0d3255bfef95601890afd80709"


def make_store(tmp_path: Path, *, with_embeddings: bool = False) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if with_embeddings else None,
        )
    )


def store_note(
    store: MemoryStore,
    title: str,
    *,
    tier: int = 3,
    links: list[str] | None = None,
    embedding: np.ndarray | None = None,
) -> str:
    return store.store_note(
        NoteInput(
            tier=tier,
            content=f"{title} body",
            title=title,
            links=list(links or []),
            embedding=embedding,
        )
    )


def test_personality_context_empty_store_has_deterministic_version(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    context = store.get_personality_context()

    assert context.personality_files == []
    assert context.version_id == EMPTY_VERSION_ID


def test_personality_context_returns_all_current_tier_three_notes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    first_id = store_note(store, "first")
    second_id = store_note(store, "second")

    context = store.get_personality_context()

    assert [note.note_id for note in context.personality_files] == sorted([first_id, second_id])


def test_personality_context_excludes_superseded_tier_three_notes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store, "old")
    new_id = store_note(store, "new")
    new_note = store.get_note(new_id)
    new_note.supersedes = old_id
    note_path(store.vault_path, 3, new_id).write_text(serialize_note(new_note), encoding="utf-8")

    reloaded = MemoryStore(MemoryStoreConfig(vault_path=str(store.vault_path)))

    context = reloaded.get_personality_context()

    assert [note.note_id for note in context.personality_files] == [new_id]


def test_personality_context_excludes_tier_one_and_tier_two_notes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "tier one", tier=1)
    store_note(store, "tier two", tier=2)
    tier_three_id = store_note(store, "tier three", tier=3)

    context = store.get_personality_context()

    assert [note.note_id for note in context.personality_files] == [tier_three_id]


def test_personality_context_version_is_stable_for_identical_state(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "stable")

    first = store.get_personality_context()
    second = store.get_personality_context()

    assert second.version_id == first.version_id


def test_personality_context_version_changes_after_tier_three_store_or_update(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    first = store.get_personality_context()

    note_id = store_note(store, "new personality file")
    after_store = store.get_personality_context()
    store.update_note(note_id, NotePatch(content="updated body"))
    after_update = store.get_personality_context()

    assert after_store.version_id != first.version_id
    assert after_update.version_id != after_store.version_id


def test_personality_context_returns_embeddings_and_computed_link_counts(tmp_path: Path) -> None:
    store = make_store(tmp_path, with_embeddings=True)
    target_id = store_note(store, "target", embedding=np.array([1.0, 2.0]))
    store_note(store, "source", links=[target_id])

    context = store.get_personality_context()
    target = next(note for note in context.personality_files if note.note_id == target_id)

    assert np.array_equal(target.embedding, np.array([1.0, 2.0]))
    assert target.link_count == 1


def test_personality_context_loads_fresh_from_disk_each_call(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store_note(store, "fresh")
    first = store.get_personality_context()
    note = store.get_note(note_id)
    note.title = "fresh from disk"
    note.updated_at = note.updated_at + timedelta(seconds=5)
    note_path(store.vault_path, 3, note_id).write_text(serialize_note(note), encoding="utf-8")

    second = store.get_personality_context()

    assert second.personality_files[0].title == "fresh from disk"
    assert second.version_id != first.version_id
