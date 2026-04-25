from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from phosphene.memory_store.types import MemoryNote
from phosphene.memory_store.vault import (
    generate_note_id,
    note_path,
    parse_note,
    serialize_note,
)


def make_note(**overrides: object) -> MemoryNote:
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    values = {
        "note_id": "complex-note-20260102030405-abcd",
        "tier": 2,
        "content": "Line 1\n---\n[[literal-link]]: value\nunicode: cafe",
        "title": "Complex Note",
        "importance": 0.75,
        "unresolvedness": 0.25,
        "links": ["note-1", "note-2"],
        "tags": ["memory", "yaml:test"],
        "source": "seeding",
        "friction_target": "note-3",
        "embedding": None,
        "attractor_relevance": 0.8,
        "cluster_group": "cluster-a",
        "supersedes": "old-note",
        "created_at": created_at,
        "updated_at": created_at + timedelta(seconds=10),
        "link_count": 2,
        "decay_deadline": created_at + timedelta(days=30),
    }
    values.update(overrides)
    return MemoryNote(**values)


def test_generate_note_id_uses_documented_format() -> None:
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    note_id = generate_note_id("A Title! With Punctuation & Spaces", created_at)

    assert re.fullmatch(r"a-title-with-punctuation-spaces-20260102030405-[0-9a-f]{4}", note_id)


def test_generate_note_id_is_stable_for_same_inputs() -> None:
    created_at = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)

    assert generate_note_id("Same Title", created_at) == generate_note_id("Same Title", created_at)


def test_generate_note_id_truncates_slug_to_sixty_chars_or_less() -> None:
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    note_id = generate_note_id("word " * 30, created_at)
    slug = note_id.removesuffix("-20260102030405-" + note_id[-4:])

    assert len(slug) <= 60


def test_generate_note_id_is_collision_free_for_distinct_created_times() -> None:
    start = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    ids = {
        generate_note_id("Repeated Title", start + timedelta(microseconds=offset))
        for offset in range(100)
    }

    assert len(ids) == 100


def test_note_path_uses_tier_subdirectory() -> None:
    assert note_path(Path("/vault"), 2, "note-1") == Path("/vault") / "tier2" / "note-1.md"


def test_round_trip_fully_populated_note() -> None:
    note = make_note()

    parsed = parse_note(serialize_note(note))

    assert parsed == note


def test_round_trip_minimally_populated_note() -> None:
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    note = make_note(
        note_id="minimal-20260102030405-abcd",
        tier=1,
        content="Body",
        title="Minimal",
        importance=0.0,
        unresolvedness=0.0,
        links=[],
        tags=[],
        source=None,
        friction_target=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=created_at,
        updated_at=created_at,
        link_count=0,
        decay_deadline=None,
    )

    parsed = parse_note(serialize_note(note))

    assert parsed == note


def test_embedding_is_not_stored_in_markdown() -> None:
    note = make_note(embedding=object())

    serialized = serialize_note(note)
    parsed = parse_note(serialized)

    assert "embedding" not in serialized
    assert parsed.embedding is None


def test_special_characters_in_content_survive_round_trip() -> None:
    content = "\n".join(
        [
            "first line",
            "---",
            "key: value",
            "- list item",
            "[[wikilink]] stays literal",
            "unicode snowman: \u2603",
        ]
    )
    note = make_note(content=content)

    assert parse_note(serialize_note(note)).content == content
