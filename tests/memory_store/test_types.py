from datetime import datetime, timezone

import numpy as np

from phosphene.memory_store import (
    DecayReport,
    DensityMetrics,
    IndexEntry,
    MemoryNote,
    MemoryStoreConfig,
    NoteInput,
    NotePatch,
    NoteQuery,
    PersonalityContext,
)


def sample_memory_note() -> MemoryNote:
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    return MemoryNote(
        note_id="note-1",
        tier=1,
        content="Body",
        title="Title",
        importance=0.7,
        unresolvedness=0.4,
        links=["note-2"],
        tags=["memory"],
        source="ingestion",
        friction_target="note-3",
        embedding=None,
        attractor_relevance=0.8,
        cluster_group="cluster-a",
        supersedes=None,
        created_at=now,
        updated_at=now,
        link_count=1,
        decay_deadline=None,
    )


def test_memory_store_config_defaults() -> None:
    config = MemoryStoreConfig(vault_path="/tmp/vault")

    assert config.embedding_path is None
    assert config.tier1_base_retention_days == 30
    assert config.tier1_extended_retention_days == 90
    assert config.tier3_superseded_retention_days == 90
    assert config.link_density_threshold == 2


def test_note_input_defaults() -> None:
    note = NoteInput(tier=1, content="Body", title="Title")

    assert note.importance == 0.0
    assert note.unresolvedness == 0.0
    assert note.links == []
    assert note.tags == []
    assert note.source is None
    assert note.friction_target is None
    assert note.embedding is None
    assert note.attractor_relevance is None
    assert note.cluster_group is None


def test_note_input_accepts_full_optional_field_set() -> None:
    embedding = np.array([0.1, 0.2, 0.3])
    note = NoteInput(
        tier=1,
        content="Luhmann's Zettelkasten produced surprise.",
        title="Zettelkasten: network density -> surprise",
        importance=0.7,
        unresolvedness=0.4,
        links=["note-042"],
        tags=["memory-architecture", "emergence"],
        source="ingestion",
        friction_target="note-038",
        embedding=embedding,
        attractor_relevance=0.9,
        cluster_group="cluster-a",
    )

    assert note.links == ["note-042"]
    assert note.tags == ["memory-architecture", "emergence"]
    assert note.source == "ingestion"
    assert note.friction_target == "note-038"
    assert note.embedding is embedding
    assert note.attractor_relevance == 0.9
    assert note.cluster_group == "cluster-a"


def test_memory_note_instantiates() -> None:
    note = sample_memory_note()

    assert note.note_id == "note-1"
    assert note.decay_deadline is None


def test_index_entry_instantiates() -> None:
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    entry = IndexEntry(
        note_id="note-1",
        tier=1,
        title="Title",
        importance=0.7,
        unresolvedness=0.4,
        link_count=2,
        tags=["memory"],
        created_at=created_at,
    )

    assert entry.created_at is created_at


def test_density_metrics_instantiates() -> None:
    metrics = DensityMetrics(
        note_count=3,
        tier_counts={1: 1, 2: 1, 3: 1},
        mean_link_degree=1.5,
        cluster_count=1,
        unresolved_count=2,
        max_unresolvedness=0.9,
    )

    assert metrics.tier_counts == {1: 1, 2: 1, 3: 1}


def test_personality_context_instantiates() -> None:
    note = sample_memory_note()
    context = PersonalityContext(personality_files=[note], version_id="snapshot-1")

    assert context.personality_files == [note]
    assert context.version_id == "snapshot-1"


def test_note_query_defaults() -> None:
    query = NoteQuery()

    assert query.tier is None
    assert query.min_importance is None
    assert query.min_unresolvedness is None
    assert query.tags is None
    assert query.source is None
    assert query.since is None
    assert query.until is None
    assert query.limit == 50
    assert query.order_by == "created_at"
    assert query.descending is True


def test_note_patch_defaults() -> None:
    patch = NotePatch()

    assert patch.content is None
    assert patch.title is None
    assert patch.importance is None
    assert patch.unresolvedness is None
    assert patch.links is None
    assert patch.tags is None
    assert patch.embedding is None
    assert patch.attractor_relevance is None


def test_decay_report_instantiates() -> None:
    report = DecayReport(
        expired_count=2,
        expired_ids=["note-1", "note-2"],
        extended_count=1,
        tier_breakdown={1: 2},
    )

    assert report.expired_count == 2
    assert report.expired_ids == ["note-1", "note-2"]
