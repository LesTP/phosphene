from pathlib import Path

import pytest

from phosphene.memory_store import (
    InvalidScoreError,
    MemoryStore,
    MemoryStoreConfig,
    NoteInput,
    NoteNotFoundError,
    NotePatch,
    TitleTooLongError,
)
from phosphene.memory_store.vault import parse_note


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def test_store_get_round_trip_matches_input_fields(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_input = NoteInput(
        tier=2,
        content="Body",
        title="Original",
        importance=0.6,
        unresolvedness=0.3,
        links=["note-a", "note-b"],
        tags=["memory", "crud"],
        source="ingestion",
        friction_target="note-c",
        attractor_relevance=0.7,
        cluster_group="cluster-a",
    )

    note_id = store.store_note(note_input)
    note = store.get_note(note_id)

    assert note.note_id == note_id
    assert note.tier == note_input.tier
    assert note.content == note_input.content
    assert note.title == note_input.title
    assert note.importance == note_input.importance
    assert note.unresolvedness == note_input.unresolvedness
    assert note.links == note_input.links
    assert note.tags == note_input.tags
    assert note.source == note_input.source
    assert note.friction_target == note_input.friction_target
    assert note.attractor_relevance == note_input.attractor_relevance
    assert note.cluster_group == note_input.cluster_group
    assert note.link_count == 2
    assert note.decay_deadline is None


def test_update_applies_patch_fields_and_preserves_unpatched_fields(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(
        NoteInput(
            tier=1,
            content="Original body",
            title="Original title",
            importance=0.2,
            unresolvedness=0.4,
            links=["old-link"],
            tags=["old-tag"],
            source="ingestion",
            friction_target="friction",
        )
    )
    original = store.get_note(note_id)

    updated = store.update_note(
        note_id,
        NotePatch(
            content="Updated body",
            title="Updated title",
            importance=0.9,
            unresolvedness=0.1,
            links=["new-link-1", "new-link-2"],
            tags=["new-tag"],
            attractor_relevance=0.8,
        ),
    )

    assert updated.note_id == note_id
    assert updated.tier == 1
    assert updated.content == "Updated body"
    assert updated.title == "Updated title"
    assert updated.importance == 0.9
    assert updated.unresolvedness == 0.1
    assert updated.links == ["new-link-1", "new-link-2"]
    assert updated.tags == ["new-tag"]
    assert updated.source == "ingestion"
    assert updated.friction_target == "friction"
    assert updated.attractor_relevance == 0.8
    assert updated.link_count == 2
    assert updated.created_at == original.created_at
    assert updated.updated_at > original.updated_at

    path = tmp_path / "vault" / "tier1" / f"{note_id}.md"
    parsed = parse_note(path.read_text(encoding="utf-8"))
    assert parsed == updated


@pytest.mark.parametrize(
    ("patch", "expected_content", "expected_title", "expected_importance", "expected_unresolvedness"),
    [
        (NotePatch(content="Changed"), "Changed", "Title", 0.2, 0.4),
        (NotePatch(title="Changed"), "Body", "Changed", 0.2, 0.4),
        (NotePatch(importance=0.8), "Body", "Title", 0.8, 0.4),
        (NotePatch(unresolvedness=0.1), "Body", "Title", 0.2, 0.1),
    ],
)
def test_update_applies_each_scalar_patch_field_independently(
    tmp_path: Path,
    patch: NotePatch,
    expected_content: str,
    expected_title: str,
    expected_importance: float,
    expected_unresolvedness: float,
) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(
        NoteInput(
            tier=3,
            content="Body",
            title="Title",
            importance=0.2,
            unresolvedness=0.4,
            links=["link"],
            tags=["tag"],
        )
    )

    updated = store.update_note(note_id, patch)

    assert updated.content == expected_content
    assert updated.title == expected_title
    assert updated.importance == expected_importance
    assert updated.unresolvedness == expected_unresolvedness
    assert updated.links == ["link"]
    assert updated.tags == ["tag"]


def test_update_replaces_links_and_tags_with_empty_lists(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(
        NoteInput(tier=1, content="Body", title="Title", links=["link"], tags=["tag"])
    )

    updated = store.update_note(note_id, NotePatch(links=[], tags=[]))

    assert updated.links == []
    assert updated.tags == []
    assert updated.link_count == 0


def test_empty_patch_only_refreshes_updated_at(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(NoteInput(tier=1, content="Body", title="Title"))
    original = store.get_note(note_id)

    updated = store.update_note(note_id, NotePatch())

    assert updated.content == original.content
    assert updated.title == original.title
    assert updated.importance == original.importance
    assert updated.unresolvedness == original.unresolvedness
    assert updated.links == original.links
    assert updated.tags == original.tags
    assert updated.updated_at > original.updated_at


def test_get_and_update_raise_for_missing_note(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(NoteNotFoundError):
        store.get_note("missing")

    with pytest.raises(NoteNotFoundError):
        store.update_note("missing", NotePatch(content="Body"))


@pytest.mark.parametrize(
    "patch",
    [
        NotePatch(title="x" * 151),
        NotePatch(importance=-0.1),
        NotePatch(importance=1.1),
        NotePatch(unresolvedness=-0.1),
        NotePatch(unresolvedness=1.1),
    ],
)
def test_update_rejects_invalid_patch_values(tmp_path: Path, patch: NotePatch) -> None:
    store = make_store(tmp_path)
    note_id = store.store_note(NoteInput(tier=1, content="Body", title="Title"))

    expected_error = TitleTooLongError if patch.title is not None else InvalidScoreError
    with pytest.raises(expected_error):
        store.update_note(note_id, patch)
