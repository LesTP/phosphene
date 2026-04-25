from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import phosphene.memory_store.store as store_module
from phosphene.memory_store import (
    InvalidScoreError,
    InvalidTierError,
    MemoryStore,
    MemoryStoreConfig,
    NoteInput,
    TitleTooLongError,
    VaultError,
)
from phosphene.memory_store.vault import parse_note


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def test_constructor_creates_vault_and_tier_directories(tmp_path: Path) -> None:
    vault_path = tmp_path / "vault"

    MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))

    assert vault_path.is_dir()
    assert (vault_path / "tier1").is_dir()
    assert (vault_path / "tier2").is_dir()
    assert (vault_path / "tier3").is_dir()


def test_constructor_raises_vault_error_for_existing_file(tmp_path: Path) -> None:
    vault_path = tmp_path / "not-a-directory"
    vault_path.write_text("file", encoding="utf-8")

    with pytest.raises(VaultError):
        MemoryStore(MemoryStoreConfig(vault_path=str(vault_path)))


@pytest.mark.parametrize("tier", [1, 2, 3])
def test_store_note_writes_note_to_expected_tier_path(tmp_path: Path, tier: int) -> None:
    store = make_store(tmp_path)

    note_id = store.store_note(
        NoteInput(
            tier=tier,
            content="Body",
            title=f"Tier {tier} Note",
            importance=0.7,
            unresolvedness=0.4,
            links=["related-note"],
            tags=["memory"],
            source="ingestion",
            friction_target="friction-note",
            attractor_relevance=0.8,
            cluster_group="cluster-a",
        )
    )

    path = tmp_path / "vault" / f"tier{tier}" / f"{note_id}.md"
    assert path.exists()
    assert note_id == path.stem

    parsed = parse_note(path.read_text(encoding="utf-8"))
    assert parsed.note_id == note_id
    assert parsed.tier == tier
    assert parsed.content == "Body"
    assert parsed.title == f"Tier {tier} Note"
    assert parsed.importance == 0.7
    assert parsed.unresolvedness == 0.4
    assert parsed.links == ["related-note"]
    assert parsed.tags == ["memory"]
    assert parsed.source == "ingestion"
    assert parsed.friction_target == "friction-note"
    assert parsed.attractor_relevance == 0.8
    assert parsed.cluster_group == "cluster-a"
    assert parsed.supersedes is None
    assert parsed.created_at == parsed.updated_at
    assert parsed.link_count == 1
    assert parsed.decay_deadline is None


@pytest.mark.parametrize("tier", [0, 4])
def test_store_note_rejects_invalid_tier(tmp_path: Path, tier: int) -> None:
    store = make_store(tmp_path)

    with pytest.raises(InvalidTierError):
        store.store_note(NoteInput(tier=tier, content="Body", title="Title"))


def test_store_note_rejects_title_longer_than_150_chars(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(TitleTooLongError):
        store.store_note(NoteInput(tier=1, content="Body", title="x" * 151))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("importance", -0.1),
        ("importance", 1.1),
        ("unresolvedness", -0.1),
        ("unresolvedness", 1.1),
    ],
)
def test_store_note_rejects_scores_outside_range(
    tmp_path: Path, field_name: str, value: float
) -> None:
    store = make_store(tmp_path)
    kwargs = {field_name: value}

    with pytest.raises(InvalidScoreError):
        store.store_note(NoteInput(tier=1, content="Body", title="Title", **kwargs))


def test_store_note_accepts_validation_boundaries(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    note_id = store.store_note(
        NoteInput(
            tier=1,
            content="Body",
            title="x" * 150,
            importance=0.0,
            unresolvedness=1.0,
        )
    )

    assert (tmp_path / "vault" / "tier1" / f"{note_id}.md").exists()


def test_store_note_generates_distinct_ids_for_same_title_in_same_second(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = datetime(2026, 1, 2, 3, 4, 5, 100, tzinfo=timezone.utc)
    timestamps = iter([start, start + timedelta(microseconds=1)])

    class FrozenDateTime:
        @staticmethod
        def now(tz: timezone) -> datetime:
            return next(timestamps).astimezone(tz)

    monkeypatch.setattr(store_module, "datetime", FrozenDateTime)
    store = make_store(tmp_path)

    first_id = store.store_note(NoteInput(tier=1, content="First", title="Repeated"))
    second_id = store.store_note(NoteInput(tier=1, content="Second", title="Repeated"))

    assert first_id != second_id
    assert first_id.rsplit("-", 2)[1] == second_id.rsplit("-", 2)[1]
