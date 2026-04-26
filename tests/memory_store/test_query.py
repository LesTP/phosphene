from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from phosphene.memory_store import (
    InvalidTierError,
    MemoryStore,
    MemoryStoreConfig,
    NoteQuery,
)
from phosphene.memory_store.types import MemoryNote
from phosphene.memory_store.vault import note_path, serialize_note


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def make_seeded_store(tmp_path: Path) -> tuple[MemoryStore, dict[str, str]]:
    vault_path = tmp_path / "vault"
    start = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    ids = {"alpha": "alpha", "beta": "beta", "gamma": "gamma"}
    notes = [
        make_note(
            ids["alpha"],
            tier=1,
            created_at=start,
            title="Alpha",
            importance=0.2,
            unresolvedness=0.8,
            tags=["memory", "rough"],
            source="ingestion",
        ),
        make_note(
            ids["beta"],
            tier=2,
            created_at=start + timedelta(seconds=1),
            title="Beta",
            importance=0.7,
            unresolvedness=0.3,
            links=[ids["gamma"]],
            tags=["pattern"],
            source="distillation",
        ),
        make_note(
            ids["gamma"],
            tier=3,
            created_at=start + timedelta(seconds=2),
            title="Gamma",
            importance=0.9,
            unresolvedness=0.6,
            tags=["memory", "personality"],
            source="seeding",
        ),
    ]
    for note in notes:
        write_note(vault_path, note)
    return MemoryStore(MemoryStoreConfig(vault_path=str(vault_path))), ids


def make_note(
    note_id: str,
    *,
    tier: int,
    created_at: datetime,
    title: str,
    importance: float,
    unresolvedness: float,
    links: list[str] | None = None,
    tags: list[str] | None = None,
    source: str | None = None,
) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"{title} body",
        title=title,
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


def note_titles(notes: list) -> list[str]:
    return [note.title for note in notes]


def test_query_filters_by_tier(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(tier=2))

    assert note_titles(notes) == ["Beta"]


def test_query_filters_by_min_importance(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(min_importance=0.7, order_by="importance"))

    assert note_titles(notes) == ["Gamma", "Beta"]


def test_query_filters_by_min_unresolvedness(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(min_unresolvedness=0.7))

    assert note_titles(notes) == ["Alpha"]


def test_query_filters_by_any_tag(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(tags=["personality", "missing"]))

    assert note_titles(notes) == ["Gamma"]


def test_query_filters_by_source(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(source="distillation"))

    assert note_titles(notes) == ["Beta"]


def test_query_filters_by_since_and_until(tmp_path: Path) -> None:
    store, ids = make_seeded_store(tmp_path)
    alpha = store.get_note(ids["alpha"])
    beta = store.get_note(ids["beta"])
    gamma = store.get_note(ids["gamma"])

    since_notes = store.query_notes(NoteQuery(since=beta.created_at, order_by="created_at"))
    until_notes = store.query_notes(NoteQuery(until=beta.created_at, order_by="created_at"))

    assert note_titles(since_notes) == ["Gamma", "Beta"]
    assert note_titles(until_notes) == ["Beta", "Alpha"]
    assert alpha.created_at <= beta.created_at <= gamma.created_at


def test_query_combines_filters(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(
        NoteQuery(
            min_importance=0.5,
            min_unresolvedness=0.5,
            tags=["memory"],
            source="seeding",
        )
    )

    assert note_titles(notes) == ["Gamma"]


@pytest.mark.parametrize("order_by", ["created_at", "importance", "unresolvedness", "link_count"])
def test_query_orders_descending_and_ascending(tmp_path: Path, order_by: str) -> None:
    store, _ = make_seeded_store(tmp_path)

    descending = store.query_notes(NoteQuery(order_by=order_by, descending=True))
    ascending = store.query_notes(NoteQuery(order_by=order_by, descending=False))

    assert [getattr(note, order_by) for note in descending] == sorted(
        [getattr(note, order_by) for note in descending],
        reverse=True,
    )
    assert [getattr(note, order_by) for note in ascending] == sorted(
        [getattr(note, order_by) for note in ascending],
    )


def test_query_limit_truncates_results(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(order_by="importance", limit=2))

    assert note_titles(notes) == ["Gamma", "Beta"]


def test_query_rejects_invalid_tier(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(InvalidTierError):
        store.query_notes(NoteQuery(tier=4))


def test_query_rejects_invalid_order_by(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(ValueError):
        store.query_notes(NoteQuery(order_by="title"))


def test_query_empty_result_set_returns_empty_list(tmp_path: Path) -> None:
    store, _ = make_seeded_store(tmp_path)

    assert store.query_notes(NoteQuery(tags=["absent"])) == []


def test_query_returns_notes_with_inbound_augmented_link_count(tmp_path: Path) -> None:
    store, ids = make_seeded_store(tmp_path)

    notes = store.query_notes(NoteQuery(tags=["personality"]))

    assert notes[0].note_id == ids["gamma"]
    assert notes[0].link_count == 1
