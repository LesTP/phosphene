from pathlib import Path

import numpy as np
import pytest

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NoteNotFoundError


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


def test_get_linked_depth_one_returns_outbound_and_inbound_neighbors(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    outbound_id = store_note(store, "outbound")
    inbound_id = store_note(store, "inbound", links=[source_id])

    store.add_links(source_id, [outbound_id])

    assert [note.note_id for note in store.get_linked(source_id, depth=1)] == [
        outbound_id,
        inbound_id,
    ]


def test_get_linked_depth_two_reaches_second_degree_and_deduplicates(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    first_id = store_note(store, "first")
    inbound_id = store_note(store, "inbound", links=[source_id])
    second_id = store_note(store, "second")

    store.add_links(source_id, [first_id])
    store.add_links(first_id, [second_id])
    store.add_links(inbound_id, [second_id])

    assert [note.note_id for note in store.get_linked(source_id, depth=2)] == [
        first_id,
        inbound_id,
        second_id,
    ]


def test_get_linked_depth_three_uses_bfs_order(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    first_id = store_note(store, "first")
    second_id = store_note(store, "second")
    third_id = store_note(store, "third")

    store.add_links(source_id, [first_id])
    store.add_links(first_id, [second_id])
    store.add_links(second_id, [third_id])

    assert [note.note_id for note in store.get_linked(source_id, depth=3)] == [
        first_id,
        second_id,
        third_id,
    ]


def test_get_linked_excludes_starting_note_when_cycle_reaches_it(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    first_id = store_note(store, "first")
    second_id = store_note(store, "second")

    store.add_links(source_id, [first_id])
    store.add_links(first_id, [second_id])
    store.add_links(second_id, [source_id])

    assert [note.note_id for note in store.get_linked(source_id, depth=3)] == [
        first_id,
        second_id,
    ]


def test_get_linked_cycles_do_not_loop_forever(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    first_id = store_note(store, "first")
    second_id = store_note(store, "second")

    store.add_links(source_id, [first_id])
    store.add_links(first_id, [second_id])
    store.add_links(second_id, [first_id])

    assert [note.note_id for note in store.get_linked(source_id, depth=3)] == [
        first_id,
        second_id,
    ]


def test_get_linked_rejects_depth_outside_supported_range(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")

    with pytest.raises(ValueError):
        store.get_linked(source_id, depth=0)
    with pytest.raises(ValueError):
        store.get_linked(source_id, depth=4)


def test_get_linked_raises_for_unknown_note(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(NoteNotFoundError):
        store.get_linked("missing-note")


def test_get_linked_isolated_note_returns_empty_list(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")

    assert store.get_linked(source_id) == []


def test_get_linked_returns_notes_with_embeddings_and_computed_link_counts(tmp_path: Path) -> None:
    store = make_store(tmp_path, with_embeddings=True)
    source_id = store.store_note(
        NoteInput(tier=1, content="source body", title="source", links=[], embedding=np.array([1.0]))
    )
    target_id = store.store_note(
        NoteInput(tier=1, content="target body", title="target", links=[], embedding=np.array([2.0]))
    )
    inbound_id = store_note(store, "inbound", links=[target_id])

    store.add_links(source_id, [target_id])

    linked = store.get_linked(source_id)

    assert [note.note_id for note in linked] == [target_id]
    assert np.array_equal(linked[0].embedding, np.array([2.0]))
    assert linked[0].link_count == 2
    assert store.get_note(inbound_id).link_count == 1
