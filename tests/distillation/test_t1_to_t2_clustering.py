from dataclasses import dataclass, field
import json

import pytest

from phosphene.distillation import DistillationConfig, DistillationEngine
from phosphene.distillation.errors import DistillationError


@dataclass
class ClusterNote:
    note_id: str
    content: str
    source: str | None = None
    importance: float = 0.0
    unresolvedness: float = 0.0
    links: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    cluster_group: str | None = None
    title: str = ""


class ClusterMemoryStore:
    def __init__(
        self,
        vault_path,
        notes: list[ClusterNote],
        tier2_notes: list[ClusterNote] | None = None,
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
        return ClusterNote(
            note_id=note_id,
            content=getattr(patch, "content", ""),
            cluster_group="existing",
        )

    def add_links(self, source_id: str, target_ids: list[str]) -> None:
        self.link_calls.append((source_id, target_ids))

    def get_personality_context(self) -> object:
        raise AssertionError("T1 to T2 clustering must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("T1 to T2 clustering must not supersede notes")


def test_distill_t1_to_t2_embeds_clusters_and_splits_by_coherence(
    tmp_path,
    monkeypatch,
) -> None:
    embed_calls: list[tuple[list[str], object]] = []
    cluster_calls: list[dict[str, object]] = []

    def fake_embed(texts: list[str], config: object):
        embed_calls.append((texts, config))
        return expected_embeddings

    expected_embeddings = [
        [1.0, 0.0],
        [0.96, 0.28],
        [1.0, 0.0],
        [-1.0, 0.0],
        [0.0, 1.0],
    ]

    def fake_cluster(embeddings: object, config: object, *, texts: list[str]):
        cluster_calls.append(
            {
                "embeddings": embeddings,
                "config": config,
                "texts": texts,
            }
        )
        return {
            "clusters": [
                {
                    "id": "coherent",
                    "member_indices": [0, 1],
                    "summary": "Coherent alpha pattern",
                },
                {
                    "id": "incoherent",
                    "member_indices": [2, 3],
                    "summary": "Incoherent split pattern",
                },
            ],
            "noise_indices": [4],
            "tree_depth": 3,
        }

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_embed", fake_embed)
    monkeypatch.setattr("phosphene.distillation.engine._toolkit_cluster", fake_cluster)
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: json.dumps(
            {"assertions": [{"text": "Alpha coheres", "confidence": 0.8}]}
        ),
    )

    store = ClusterMemoryStore(
        tmp_path / "vault",
        [
            ClusterNote("note-a", "alpha one"),
            ClusterNote("note-b", "alpha two"),
            ClusterNote("note-c", "split one"),
            ClusterNote("note-d", "split two"),
            ClusterNote("note-e", "unclustered"),
        ],
    )
    engine = DistillationEngine(store)

    result = engine.distill_t1_to_t2(
        DistillationConfig(
            llm_config="llm",
            embedding_config="embedding",
            min_tier1_volume=5,
            min_cluster_coherence=0.4,
            incorporate_feedback=False,
        )
    )

    assert embed_calls == [
        (
            ["alpha one", "alpha two", "split one", "split two", "unclustered"],
            "embedding",
        )
    ]
    assert cluster_calls[0]["embeddings"] == expected_embeddings
    assert cluster_calls[0]["texts"] == [
        "alpha one",
        "alpha two",
        "split one",
        "split two",
        "unclustered",
    ]
    cluster_config = cluster_calls[0]["config"]
    assert getattr(cluster_config, "strategy") == "RAPTOR"
    assert callable(getattr(cluster_config, "raptor_summarizer"))
    assert callable(getattr(cluster_config, "raptor_embedder"))
    assert result.new_cluster_ids == ["stored-1"]
    assert result.updated_cluster_ids == []
    assert result.promoted_count == 2
    assert result.noise_count == 1
    assert result.incoherent_cluster_count == 1
    assert result.cluster_tree_depth == 3
    assert result.feedback_processed == 0
    assert result.assertion_cache_updated == ["coherent"]
    assert json.loads((tmp_path / "vault" / "tier2" / "coherent.json").read_text()) == {
        "assertions": [{"confidence": 0.8, "text": "Alpha coheres"}],
        "cluster_group": "coherent",
        "cluster_summary": "Coherent alpha pattern",
    }
    assert len(store.stored_notes) == 1
    stored_note = store.stored_notes[0]
    assert stored_note.tier == 2
    assert stored_note.content == "Coherent alpha pattern"
    assert stored_note.cluster_group == "coherent"
    assert stored_note.links == ["note-a", "note-b"]
    assert stored_note.tags == ["distilled-pattern"]
    assert store.updated_notes == []
    assert store.link_calls == [("stored-1", [])]
    assert engine._is_consolidation_locked() is False


def test_distill_t1_to_t2_treats_unassigned_labels_as_noise(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_embed",
        lambda texts, _config: [[1.0, 0.0] for _text in texts],
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_cluster",
        lambda _embeddings, _config, *, texts: {"labels": [0, 0, -1]},
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: json.dumps({"assertions": []}),
    )
    store = ClusterMemoryStore(
        tmp_path / "vault",
        [
            ClusterNote("note-a", "alpha one"),
            ClusterNote("note-b", "alpha two"),
            ClusterNote("note-c", "noise"),
        ],
    )
    engine = DistillationEngine(store)

    result = engine.distill_t1_to_t2(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=3,
            incorporate_feedback=False,
        )
    )

    assert result.promoted_count == 2
    assert result.noise_count == 1
    assert result.incoherent_cluster_count == 0
    assert result.new_cluster_ids == ["stored-1"]
    assert result.assertion_cache_updated == ["0"]


def test_distill_t1_to_t2_updates_existing_cluster_and_links_related_clusters(
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
            "clusters": [
                {"id": "existing", "member_indices": [0], "summary": "Updated pattern"},
                {"id": "new", "member_indices": [1], "summary": "New pattern"},
            ],
        },
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: json.dumps({"assertions": []}),
    )
    store = ClusterMemoryStore(
        tmp_path / "vault",
        [
            ClusterNote("note-a", "alpha one"),
            ClusterNote("note-b", "alpha two"),
        ],
        tier2_notes=[
            ClusterNote(
                "tier2-existing",
                "Existing pattern",
                links=["prior-note"],
                tags=["prior"],
                cluster_group="existing",
                title="Existing title",
            )
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

    assert result.new_cluster_ids == ["stored-1"]
    assert result.updated_cluster_ids == ["tier2-existing"]
    assert result.assertion_cache_updated == ["existing", "new"]
    assert store.updated_notes[0][0] == "tier2-existing"
    patch = store.updated_notes[0][1]
    assert patch.title == "Existing title"
    assert patch.links == ["prior-note", "note-a"]
    assert patch.tags == ["prior", "distilled-pattern"]
    assert "Updated pattern" in patch.content
    assert store.link_calls == [
        ("tier2-existing", ["stored-1"]),
        ("stored-1", ["tier2-existing"]),
    ]


def test_distill_t1_to_t2_malformed_assertion_cache_payload_fails_atomically(
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
            "clusters": [
                {"id": "first", "member_indices": [0], "summary": "First pattern"},
                {"id": "second", "member_indices": [1], "summary": "Second pattern"},
            ],
        },
    )
    responses = iter(
        [
            json.dumps({"assertions": [{"text": "First claim", "confidence": 0.9}]}),
            "{not-json",
        ]
    )
    monkeypatch.setattr(
        "phosphene.distillation.engine._toolkit_complete",
        lambda **_kwargs: next(responses),
    )
    store = ClusterMemoryStore(
        tmp_path / "vault",
        [
            ClusterNote("note-a", "alpha one"),
            ClusterNote("note-b", "alpha two"),
        ],
    )
    engine = DistillationEngine(store)

    with pytest.raises(DistillationError, match="must be valid JSON"):
        engine.distill_t1_to_t2(
            DistillationConfig(
                llm_config=object(),
                embedding_config=object(),
                min_tier1_volume=2,
                incorporate_feedback=False,
            )
        )

    assert not (tmp_path / "vault" / "tier2" / "first.json").exists()
    assert not (tmp_path / "vault" / "tier2" / "second.json").exists()
    assert engine._is_consolidation_locked() is False
