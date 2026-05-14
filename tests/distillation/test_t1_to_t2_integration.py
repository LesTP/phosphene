from dataclasses import dataclass, field
from datetime import datetime, timezone
import json

import pytest

from phosphene.distillation import DistillationConfig, DistillationEngine
from phosphene.distillation.engine import _DistillationRunMetadata
from phosphene.distillation.errors import NoPatternDataError
from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput


@dataclass
class IntegrationNote:
    note_id: str
    content: str
    source: str | None = None
    importance: float = 0.0
    unresolvedness: float = 0.0
    links: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    cluster_group: str | None = None
    title: str = ""


class IntegrationMemoryStore:
    def __init__(
        self,
        vault_path,
        notes: list[IntegrationNote],
        tier2_notes: list[IntegrationNote] | None = None,
    ) -> None:
        self.vault_path = vault_path
        self.notes = notes
        self.tier2_notes = tier2_notes or []
        self.queries = []
        self.stored_notes = []
        self.updated_notes = []
        self.link_calls: list[tuple[str, list[str]]] = []

    def query_notes(self, query):
        self.queries.append(query)
        source_notes = self.tier2_notes if query.tier == 2 else self.notes
        notes = [
            note
            for note in source_notes
            if query.source is None or note.source == query.source
        ]
        return notes[: query.limit]

    def store_note(self, note: object) -> str:
        note_id = f"stored-{len(self.stored_notes) + 1}"
        self.stored_notes.append(note)
        return note_id

    def update_note(self, note_id: str, patch: object) -> object:
        self.updated_notes.append((note_id, patch))
        return IntegrationNote(
            note_id=note_id,
            content=getattr(patch, "content", ""),
            cluster_group="existing",
        )

    def add_links(self, source_id: str, target_ids: list[str]) -> None:
        self.link_calls.append((source_id, target_ids))

    def get_personality_context(self) -> object:
        raise AssertionError("T1 to T2 integration must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("T1 to T2 integration must not supersede notes")


def test_distill_t1_to_t2_end_to_end_updates_metadata_on_success(
    tmp_path,
    monkeypatch,
) -> None:
    embed_calls: list[tuple[list[str], object]] = []
    cluster_calls: list[dict[str, object]] = []
    complete_calls: list[dict[str, object]] = []

    def fake_embed(texts: list[str], config: object):
        embed_calls.append((texts, config))
        return [[1.0, 0.0], [0.98, 0.2], [0.0, 1.0]]

    def fake_cluster(embeddings: object, config: object, *, texts: list[str]):
        cluster_calls.append(
            {"embeddings": embeddings, "config": config, "texts": texts}
        )
        return {
            "clusters": [
                {
                    "id": "alpha",
                    "member_indices": [0, 1],
                    "summary": "Alpha pattern",
                }
            ],
            "noise_indices": [2],
            "tree_depth": 2,
        }

    def fake_complete(**kwargs: object) -> str:
        complete_calls.append(dict(kwargs))
        return json.dumps(
            {"assertions": [{"text": "Alpha repeats", "confidence": 0.9}]}
        )

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_embed", fake_embed)
    monkeypatch.setattr("phosphene.distillation.engine._toolkit_cluster", fake_cluster)
    monkeypatch.setattr("phosphene.distillation.engine._toolkit_complete", fake_complete)

    store = IntegrationMemoryStore(
        tmp_path / "vault",
        [
            IntegrationNote("note-a", "alpha one", importance=0.5),
            IntegrationNote("note-b", "alpha two", importance=0.7),
            IntegrationNote("note-c", "noise", importance=0.2),
        ],
    )
    engine = DistillationEngine(store)
    prior_t3_run = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    engine._write_run_metadata(
        _DistillationRunMetadata(last_t2_to_t3_run=prior_t3_run)
    )
    before = datetime.now(timezone.utc)

    result = engine.distill_t1_to_t2(
        DistillationConfig(
            llm_config="llm-config",
            embedding_config="embedding-config",
            min_tier1_volume=3,
            min_cluster_coherence=0.4,
            incorporate_feedback=False,
        )
    )
    after = datetime.now(timezone.utc)
    metadata = engine._read_run_metadata()

    assert result.new_cluster_ids == ["stored-1"]
    assert result.updated_cluster_ids == []
    assert result.promoted_count == 2
    assert result.noise_count == 1
    assert result.cluster_tree_depth == 2
    assert result.assertion_cache_updated == ["alpha"]
    assert embed_calls == [
        (["alpha one", "alpha two", "noise"], "embedding-config")
    ]
    assert cluster_calls[0]["texts"] == ["alpha one", "alpha two", "noise"]
    assert complete_calls[0]["config"] == "llm-config"
    assert len(store.stored_notes) == 1
    assert store.stored_notes[0].links == ["note-a", "note-b"]
    assert store.link_calls == [("stored-1", [])]
    assert metadata.last_t1_to_t2_run is not None
    assert before.replace(microsecond=0) <= metadata.last_t1_to_t2_run <= after
    assert metadata.last_t2_to_t3_run == prior_t3_run
    assert json.loads((tmp_path / "vault" / "tier2" / "alpha.json").read_text()) == {
        "assertions": [{"confidence": 0.9, "text": "Alpha repeats"}],
        "cluster_group": "alpha",
        "cluster_summary": "Alpha pattern",
    }
    assert engine._is_consolidation_locked() is False


def test_distill_t1_to_t2_toolkit_error_propagates_without_metadata_update(
    tmp_path,
    monkeypatch,
) -> None:
    class FakeEmbeddingError(RuntimeError):
        pass

    def fail_embed(_texts: list[str], _config: object) -> object:
        raise FakeEmbeddingError("embedding unavailable")

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_embed", fail_embed)
    store = IntegrationMemoryStore(
        tmp_path / "vault",
        [
            IntegrationNote("note-a", "alpha one"),
            IntegrationNote("note-b", "alpha two"),
        ],
    )
    engine = DistillationEngine(store)
    prior_t3_run = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    engine._write_run_metadata(
        _DistillationRunMetadata(last_t2_to_t3_run=prior_t3_run)
    )

    with pytest.raises(FakeEmbeddingError, match="embedding unavailable"):
        engine.distill_t1_to_t2(
            DistillationConfig(
                llm_config=object(),
                embedding_config=object(),
                min_tier1_volume=2,
                incorporate_feedback=False,
            )
        )

    assert engine._read_run_metadata() == _DistillationRunMetadata(
        last_t1_to_t2_run=None,
        last_t2_to_t3_run=prior_t3_run,
    )
    assert store.stored_notes == []
    assert store.updated_notes == []
    assert store.link_calls == []
    assert engine._is_consolidation_locked() is False


def test_distill_t2_to_t3_requires_pattern_data(tmp_path) -> None:
    engine = DistillationEngine(IntegrationMemoryStore(tmp_path / "vault", []))

    with pytest.raises(
        NoPatternDataError,
        match="requires at least one Tier 2 pattern note",
    ):
        engine.distill_t2_to_t3(
            DistillationConfig(llm_config=object(), embedding_config=object())
        )

    assert engine._read_run_metadata() == _DistillationRunMetadata()
    assert engine._is_consolidation_locked() is False


def test_distill_t2_to_t3_bootstrap_then_normal_evolution_with_real_store(
    tmp_path,
    monkeypatch,
) -> None:
    store = MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))
    for index in range(60):
        store.store_note(
            NoteInput(
                tier=2,
                title=f"Pattern {index:02d}",
                content=f"Pattern content {index:02d}",
                importance=(index % 10) / 10,
                unresolvedness=(index % 7) / 7,
                tags=["distilled-pattern"],
                cluster_group=f"cluster-{index:02d}",
            )
        )

    assert store.get_personality_context().personality_files == []

    tasks: list[str] = []
    reflection_batch_sizes: list[int] = []
    bootstrap_calls = 0
    evolution_calls = 0

    def fake_complete(**kwargs: object) -> str:
        nonlocal bootstrap_calls, evolution_calls
        payload = json.loads(kwargs["messages"][0]["content"])  # type: ignore[index]
        task = payload["task"]
        tasks.append(task)
        if task == "distill_t2_to_t3_reflection":
            pattern_ids = [pattern["note_id"] for pattern in payload["patterns"]]
            reflection_batch_sizes.append(len(pattern_ids))
            return json.dumps(
                {
                    "insights": [
                        {
                            "content": f"Insight from {pattern_ids[0]}",
                            "source_pattern_ids": [pattern_ids[0]],
                            "insight_type": "new_pattern",
                            "confidence": 0.8,
                        }
                    ]
                }
            )
        if task == "distill_t2_to_t3_bootstrap":
            bootstrap_calls += 1
            return json.dumps(
                {
                    "personality_files": [
                        {
                            "title": "Core orientation",
                            "content": "Specific orientation from the corpus.",
                            "change_summary": "Initial orientation.",
                        },
                        {
                            "title": "Recurring tensions",
                            "content": "Specific tension from the corpus.",
                            "change_summary": "Initial tension.",
                        },
                        {
                            "title": "Aesthetic preferences",
                            "content": "Specific preference from the corpus.",
                            "change_summary": "Initial preference.",
                        },
                    ]
                }
            )
        if task == "distill_t2_to_t3_evolution":
            evolution_calls += 1
            return json.dumps(
                {
                    "personality_proposals": [
                        {"note_id": file_payload["note_id"], "action": "unchanged"}
                        for file_payload in payload["personality_files"]
                    ],
                    "criteria_adjustments": [],
                }
            )
        raise AssertionError(f"unexpected task: {task}")

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_complete", fake_complete)

    engine = DistillationEngine(store)
    first_result = engine.distill_t2_to_t3(
        DistillationConfig(
            llm_config="llm-config",
            embedding_config="embedding-config",
            t2_reflection_batch_size=30,
            incorporate_feedback=False,
        )
    )
    first_context = store.get_personality_context()

    assert reflection_batch_sizes == [30, 30]
    assert bootstrap_calls == 1
    assert evolution_calls == 0
    assert [note.title for note in first_context.personality_files] == [
        "Aesthetic preferences",
        "Core orientation",
        "Recurring tensions",
    ]
    assert {note.tier for note in first_context.personality_files} == {3}
    assert len(first_result.superseded) == 3
    assert first_result.unchanged_ids == []
    assert all(
        note.note_id in {record.new_note_id for record in first_result.superseded}
        for note in first_context.personality_files
    )

    reflection_batch_sizes.clear()
    second_result = engine.distill_t2_to_t3(
        DistillationConfig(
            llm_config="llm-config",
            embedding_config="embedding-config",
            t2_reflection_batch_size=30,
            incorporate_feedback=False,
        )
    )

    assert reflection_batch_sizes == [30, 30]
    assert bootstrap_calls == 1
    assert evolution_calls == 1
    assert tasks[-1] == "distill_t2_to_t3_evolution"
    assert sorted(second_result.unchanged_ids) == sorted(
        note.note_id for note in first_context.personality_files
    )
    assert second_result.superseded == []
    assert [
        sorted(tag for tag in note.tags if tag.startswith("version_count:"))
        for note in store.get_personality_context().personality_files
    ] == [["version_count:2"], ["version_count:2"], ["version_count:2"]]
