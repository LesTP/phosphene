from pathlib import Path

import pytest

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NoteNotFoundError


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def store_note(
    store: MemoryStore,
    title: str,
    *,
    links: list[str] | None = None,
) -> str:
    return store.store_note(
        NoteInput(
            tier=1,
            content=f"{title} body",
            title=title,
            links=list(links or []),
        )
    )


def test_add_links_adds_new_outbound_links(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    first_id = store_note(store, "first")
    second_id = store_note(store, "second")

    store.add_links(source_id, [first_id, second_id])

    assert store.get_note(source_id).links == [first_id, second_id]


def test_add_links_deduplicates_targets_and_existing_links(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    existing_id = store_note(store, "existing")
    new_id = store_note(store, "new")
    source_id = store_note(store, "source", links=[existing_id])

    store.add_links(source_id, [existing_id, new_id, new_id])

    assert store.get_note(source_id).links == [existing_id, new_id]


def test_add_links_updates_source_and_target_link_counts(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_one_id = store_note(store, "target one")
    target_two_id = store_note(store, "target two")
    source_id = store_note(store, "source")
    store_note(store, "inbound source", links=[source_id])

    store.add_links(source_id, [target_one_id, target_two_id])

    assert store.get_note(source_id).link_count == 3
    assert store.get_note(target_one_id).link_count == 1
    assert store.get_note(target_two_id).link_count == 1


def test_add_links_raises_when_source_is_unknown_without_writes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store_note(store, "target")
    before = store.get_note(target_id)

    with pytest.raises(NoteNotFoundError):
        store.add_links("missing-source", [target_id])

    after = store.get_note(target_id)
    assert after.links == before.links
    assert after.updated_at == before.updated_at
    assert after.link_count == before.link_count


def test_add_links_raises_when_any_target_is_unknown_without_writes(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    target_id = store_note(store, "target")
    before = store.get_note(source_id)

    with pytest.raises(NoteNotFoundError):
        store.add_links(source_id, [target_id, "missing-target"])

    after = store.get_note(source_id)
    assert after.links == before.links
    assert after.updated_at == before.updated_at


def test_add_links_empty_targets_is_noop(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    before = store.get_note(source_id)

    store.add_links(source_id, [])

    after = store.get_note(source_id)
    assert after.links == before.links
    assert after.updated_at == before.updated_at


def test_add_links_drops_self_links(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store_note(store, "target")
    source_id = store_note(store, "source")

    store.add_links(source_id, [source_id, target_id])

    assert store.get_note(source_id).links == [target_id]


def test_add_links_survives_store_restart(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"
    store = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))
    source_id = store_note(store, "source")
    target_id = store_note(store, "target")

    store.add_links(source_id, [target_id])

    reloaded = MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))
    assert reloaded.get_note(source_id).links == [target_id]
    assert reloaded.get_note(target_id).link_count == 1
