from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json

import pytest

from phosphene.distillation import DistillationConfig, DistillationEngine
from phosphene.distillation.engine import _DistillationRunMetadata
from phosphene.distillation.errors import DistillationLockError, InsufficientDataError


@dataclass
class PrepNote:
    note_id: str
    content: str = ""
    importance: float = 0.0
    unresolvedness: float = 0.0
    source: str | None = None
    links: list[str] = field(default_factory=list)
    friction_target: str | None = None
    tags: list[str] = field(default_factory=list)
    cluster_group: str | None = None
    title: str = ""


class PrepMemoryStore:
    def __init__(self, vault_path, notes: list[PrepNote]) -> None:
        self.vault_path = vault_path
        self.notes = notes
        self.queries = []
        self.write_calls: list[str] = []

    def query_notes(self, query):
        self.queries.append(query)
        if query.tier == 2:
            notes = []
        else:
            notes = [
                note
                for note in self.notes
                if (query.tier is None or query.tier == 1)
                and (query.source is None or note.source == query.source)
            ]
        return notes[: query.limit]

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        self.write_calls.append("store_note")
        return "stored-cluster"

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("update_note")
        raise AssertionError("preparation tests should not update Tier 2 notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("add_links")

    def get_personality_context(self) -> object:
        self.write_calls.append("get_personality_context")
        raise AssertionError("preparation must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("supersede")
        raise AssertionError("preparation must not supersede notes")


def test_distill_t1_to_t2_guard_queries_since_metadata_and_prepares_feedback_boosts(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_embed",
        lambda texts, _config: [[1.0, 0.0] for _text in texts],
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_cluster",
        lambda _embeddings, _config, *, texts: {
            "clusters": [{"id": "cluster-a", "member_indices": list(range(len(texts)))}],
            "tree_depth": 2,
        },
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: json.dumps({"assertions": []}),
    )
    store = PrepMemoryStore(
        tmp_path / "vault",
        [
            PrepNote("note-a", content="first", importance=0.4),
            PrepNote("note-b", content="second", importance=0.96),
            PrepNote("feedback-1", importance=0.7, source="feedback", links=["note-a"]),
            PrepNote(
                "feedback-2",
                importance=0.8,
                source="feedback",
                friction_target="note-b",
            ),
        ],
    )
    engine = DistillationEngine(store)
    last_run = (datetime.now(timezone.utc) - timedelta(days=2)).replace(microsecond=0)
    engine._write_run_metadata(_DistillationRunMetadata(last_t1_to_t2_run=last_run))

    result = engine.distill_t1_to_t2(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=2,
        )
    )

    prepared = engine._prepare_tier1_distillation_input(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=2,
        )
    )

    assert [query.tier for query in store.queries[:2]] == [1, 1]
    assert store.queries[0].source is None
    assert store.queries[0].since == last_run
    assert store.queries[1].source == "feedback"
    assert store.queries[1].since == last_run
    assert [item.note.note_id for item in prepared.notes] == ["note-a", "note-b"]
    assert [item.feedback_boost for item in prepared.notes] == pytest.approx([0.07, 0.08])
    assert [item.effective_importance for item in prepared.notes] == pytest.approx([0.47, 1.0])
    assert [event.note_id for event in prepared.feedback_events] == ["feedback-1", "feedback-2"]
    assert result.promoted_count == 2
    assert result.noise_count == 0
    assert result.incoherent_cluster_count == 0
    assert result.cluster_tree_depth == 2
    assert result.feedback_processed == 2
    assert store.write_calls == ["store_note", "add_links"]
    assert engine._is_consolidation_locked() is False


def test_distill_t1_to_t2_raises_insufficient_data_before_feedback_or_writes(tmp_path) -> None:
    store = PrepMemoryStore(
        tmp_path / "vault",
        [
            PrepNote("note-a", importance=0.4),
            PrepNote("feedback-1", importance=0.7, source="feedback", links=["note-a"]),
        ],
    )
    engine = DistillationEngine(store)

    with pytest.raises(InsufficientDataError, match="requires at least 2 Tier 1 notes"):
        engine.distill_t1_to_t2(
            DistillationConfig(
                llm_config=object(),
                embedding_config=object(),
                min_tier1_volume=2,
            )
        )

    assert len(store.queries) == 1
    assert store.write_calls == []
    assert engine._is_consolidation_locked() is False


def test_distill_t1_to_t2_respects_disabled_feedback_preparation(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_embed",
        lambda texts, _config: [[1.0, 0.0] for _text in texts],
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_cluster",
        lambda _embeddings, _config, *, texts: {
            "clusters": [{"id": "cluster-a", "member_indices": list(range(len(texts)))}],
        },
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: json.dumps({"assertions": []}),
    )
    store = PrepMemoryStore(
        tmp_path / "vault",
        [
            PrepNote("note-a", importance=0.4),
            PrepNote("note-b", importance=0.5),
            PrepNote("feedback-1", importance=0.9, source="feedback", links=["note-a"]),
        ],
    )
    engine = DistillationEngine(store)

    result = engine.distill_t1_to_t2(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=2,
            incorporate_feedback=False,
        )
    )

    assert len(store.queries) == 2
    assert store.queries[0].source is None
    assert store.queries[1].tier == 2
    assert result.feedback_processed == 0
    assert store.write_calls == ["store_note", "add_links"]


def test_distill_t1_to_t2_lock_rejects_concurrent_run_before_queries(tmp_path) -> None:
    store = PrepMemoryStore(
        tmp_path / "vault",
        [PrepNote("note-a"), PrepNote("note-b")],
    )
    engine = DistillationEngine(store)

    with engine._acquire_consolidation_lock():
        with pytest.raises(DistillationLockError, match="already active"):
            engine.distill_t1_to_t2(
                DistillationConfig(
                    llm_config=object(),
                    embedding_config=object(),
                    min_tier1_volume=2,
                )
            )

    assert store.queries == []
    assert store.write_calls == []
