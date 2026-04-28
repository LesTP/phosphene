from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest

from phosphene.memory_store import (
    AlreadySupersededError,
    MemoryStore,
    MemoryStoreConfig,
    NoteInput,
    NoteNotFoundError,
    TierMismatchError,
    TitleTooLongError,
)
from phosphene.memory_store.vault import parse_note


def make_store(tmp_path: Path, *, embeddings: bool = False) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if embeddings else None,
            tier3_superseded_retention_days=14,
        )
    )


def store_note(
    store: MemoryStore,
    *,
    tier: int = 3,
    title: str = "Original Personality",
    embedding: np.ndarray | None = None,
) -> str:
    return store.store_note(
        NoteInput(
            tier=tier,
            content="Original body",
            title=title,
            importance=0.8,
            unresolvedness=0.3,
            links=["linked-note"],
            tags=["voice", "style"],
            source="distillation",
            friction_target="friction-note",
            embedding=embedding,
            attractor_relevance=0.6,
            cluster_group="cluster-a",
        )
    )


def test_supersede_creates_new_version_and_keeps_old_readable(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)

    new_note = store.supersede(
        old_id,
        new_content="Updated body",
        new_title="Updated Personality",
        change_summary="Refined voice guidance.",
    )

    old_note = store.get_note(old_id)
    assert old_note.supersedes is None
    assert new_note.supersedes == old_id
    assert store.get_note(new_note.note_id).content == "Updated body"
    assert old_note.content == "Original body"


def test_supersede_stores_change_summary_only_on_new_note(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)

    new_note = store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    assert new_note.change_summary == "Changed tone."
    assert store.get_note(old_id).change_summary is None


def test_supersede_carries_forward_old_metadata(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)

    new_note = store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    assert new_note.links == ["linked-note"]
    assert new_note.tags == ["voice", "style"]
    assert new_note.importance == 0.8
    assert new_note.unresolvedness == 0.3
    assert new_note.attractor_relevance == 0.6
    assert new_note.cluster_group == "cluster-a"
    assert new_note.friction_target == "friction-note"
    assert new_note.source == "distillation"


def test_supersede_carries_forward_embedding(tmp_path: Path) -> None:
    store = make_store(tmp_path, embeddings=True)
    embedding = np.array([0.1, 0.2, 0.3])
    old_id = store_note(store, embedding=embedding)

    new_note = store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    assert np.array_equal(store.get_note(new_note.note_id).embedding, embedding)


def test_supersede_sets_old_decay_deadline_from_config(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)
    before = store.get_note(old_id).updated_at

    store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    old_note = store.get_note(old_id)
    assert old_note.decay_deadline is not None
    expected = old_note.decay_deadline - timedelta(days=14)
    assert abs((expected - before).total_seconds()) <= 2


@pytest.mark.parametrize("tier", [1, 2])
def test_supersede_rejects_non_tier_three_source_notes(tmp_path: Path, tier: int) -> None:
    store = make_store(tmp_path)
    note_id = store_note(store, tier=tier)

    with pytest.raises(TierMismatchError):
        store.supersede(note_id, "Updated body", "Updated Personality", "Changed tone.")


def test_supersede_rejects_already_superseded_source_note(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)

    store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    with pytest.raises(AlreadySupersededError):
        store.supersede(old_id, "Updated again", "Updated Personality Again", "Changed again.")


def test_supersede_rejects_missing_source_note(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(NoteNotFoundError):
        store.supersede("missing", "Updated body", "Updated Personality", "Changed tone.")


def test_supersede_rejects_too_long_title_without_writing(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)
    old_before = store.get_note(old_id)
    tier3_files_before = set((tmp_path / "vault" / "tier3").glob("*.md"))

    with pytest.raises(TitleTooLongError):
        store.supersede(old_id, "Updated body", "x" * 151, "Changed tone.")

    old_after = store.get_note(old_id)
    assert old_after.decay_deadline == old_before.decay_deadline
    assert old_after.supersedes == old_before.supersedes
    assert set((tmp_path / "vault" / "tier3").glob("*.md")) == tier3_files_before


def test_personality_context_excludes_old_and_includes_new_after_supersede(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)

    new_note = store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")

    context_ids = [note.note_id for note in store.get_personality_context().personality_files]
    assert old_id not in context_ids
    assert new_note.note_id in context_ids


def test_change_summary_survives_parse_round_trip_on_reloaded_vault(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    old_id = store_note(store)
    new_note = store.supersede(old_id, "Updated body", "Updated Personality", "Changed tone.")
    path = tmp_path / "vault" / "tier3" / f"{new_note.note_id}.md"

    parsed = parse_note(path.read_text(encoding="utf-8"))
    reloaded = MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))

    assert parsed.change_summary == "Changed tone."
    assert reloaded.get_note(new_note.note_id).change_summary == "Changed tone."
