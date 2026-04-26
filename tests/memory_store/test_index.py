from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from phosphene.memory_store import (
    InvalidTierError,
    MemoryStore,
    MemoryStoreConfig,
    NoteInput,
    NotePatch,
    VaultError,
)
from phosphene.memory_store.types import MemoryNote
from phosphene.memory_store.vault import note_path, serialize_note


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def make_note(
    note_id: str,
    tier: int,
    created_at: datetime,
    *,
    title: str | None = None,
    importance: float = 0.0,
    unresolvedness: float = 0.0,
    links: list[str] | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"Body for {note_id}",
        title=title or note_id,
        importance=importance,
        unresolvedness=unresolvedness,
        links=list(links or []),
        tags=list(tags or []),
        source=source,
        friction_target=None,
        embedding=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=created_at,
        updated_at=created_at,
        link_count=len(links or []),
        decay_deadline=None,
    )


def write_note(vault_path: Path, note: MemoryNote) -> None:
    path = note_path(vault_path, note.tier, note.note_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_note(note), encoding="utf-8")


def test_empty_vault_get_index_returns_empty_list(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    assert store.get_index() == []


def test_constructor_rebuilds_index_across_tiers_sorted_by_created_at(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    notes = [
        make_note("old", 1, now, title="Old", importance=0.1, unresolvedness=0.2, tags=["a"]),
        make_note("new", 2, now + timedelta(seconds=2), title="New", tags=["b"]),
        make_note("middle", 3, now + timedelta(seconds=1), title="Middle", tags=["c"]),
    ]
    for note in notes:
        write_note(vault_path, note)

    store = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))

    entries = store.get_index()
    assert [entry.note_id for entry in entries] == ["new", "middle", "old"]
    assert entries[0].tier == 2
    assert entries[1].title == "Middle"
    assert entries[2].importance == 0.1
    assert entries[2].unresolvedness == 0.2
    assert entries[2].tags == ["a"]


def test_get_index_filters_by_tier_and_rejects_invalid_tier(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    write_note(vault_path, make_note("tier-one", 1, now))
    write_note(vault_path, make_note("tier-two", 2, now + timedelta(seconds=1)))
    store = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))

    assert [entry.note_id for entry in store.get_index(tier=2)] == ["tier-two"]

    with pytest.raises(InvalidTierError):
        store.get_index(tier=0)
    with pytest.raises(InvalidTierError):
        store.get_index(tier=4)


def test_store_note_adds_entry_to_index_immediately(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    note_id = store.store_note(
        NoteInput(tier=1, content="Body", title="Indexed", importance=0.6, tags=["memory"])
    )

    entries = store.get_index()
    assert [entry.note_id for entry in entries] == [note_id]
    assert entries[0].title == "Indexed"
    assert entries[0].importance == 0.6
    assert entries[0].tags == ["memory"]


def test_update_note_refreshes_index_entry_fields(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(NoteInput(tier=2, content="Body", title="Original"))

    store.update_note(
        note_id,
        NotePatch(
            title="Updated",
            importance=0.8,
            unresolvedness=0.7,
            tags=["updated", "index"],
        ),
    )

    entry = store.get_index()[0]
    assert entry.note_id == note_id
    assert entry.title == "Updated"
    assert entry.importance == 0.8
    assert entry.unresolvedness == 0.7
    assert entry.tags == ["updated", "index"]


def test_duplicate_note_id_across_tiers_raises_vault_error(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    write_note(vault_path, make_note("duplicate", 1, now))
    write_note(vault_path, make_note("duplicate", 2, now + timedelta(seconds=1)))

    with pytest.raises(VaultError):
        MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))


def test_inbound_counts_update_after_store_and_update(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store.store_note(NoteInput(tier=1, content="Target", title="Target"))
    first_source_id = store.store_note(
        NoteInput(tier=1, content="Source A", title="Source A", links=[target_id])
    )

    entries = {entry.note_id: entry for entry in store.get_index()}
    assert entries[target_id].link_count == 1
    assert entries[first_source_id].link_count == 1

    store.update_note(first_source_id, NotePatch(links=[]))
    entries = {entry.note_id: entry for entry in store.get_index()}
    assert entries[target_id].link_count == 0
    assert entries[first_source_id].link_count == 0

    store.update_note(first_source_id, NotePatch(links=[target_id]))
    second_source_id = store.store_note(
        NoteInput(tier=2, content="Source B", title="Source B", links=[target_id])
    )
    entries = {entry.note_id: entry for entry in store.get_index()}
    assert entries[target_id].link_count == 2
    assert entries[first_source_id].link_count == 1
    assert entries[second_source_id].link_count == 1


def test_get_note_link_count_includes_inbound_links(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store.store_note(
        NoteInput(tier=1, content="Target", title="Target", links=["external"])
    )
    store.store_note(NoteInput(tier=1, content="Source", title="Source", links=[target_id]))

    target = store.get_note(target_id)

    assert target.link_count == 2


def test_update_note_link_removal_updates_target_get_note_link_count(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store.store_note(NoteInput(tier=1, content="Target", title="Target"))
    source_id = store.store_note(
        NoteInput(tier=1, content="Source", title="Source", links=[target_id])
    )

    assert store.get_note(target_id).link_count == 1

    updated_source = store.update_note(source_id, NotePatch(links=[]))

    assert updated_source.link_count == 0
    assert store.get_note(target_id).link_count == 0


def test_reinitializing_store_recovers_inbound_counts_from_disk(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    store = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))
    target_id = store.store_note(NoteInput(tier=1, content="Target", title="Target"))
    store.store_note(NoteInput(tier=1, content="Source", title="Source", links=[target_id]))
    store._index.inbound[target_id] = 99

    rebuilt_store = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))

    assert rebuilt_store.get_note(target_id).link_count == 1
