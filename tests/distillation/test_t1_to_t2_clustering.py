from dataclasses import dataclass

from phosphene.distillation import DistillationConfig, DistillationEngine


@dataclass
class ClusterNote:
    note_id: str
    content: str
    source: str | None = None
    importance: float = 0.0


class ClusterMemoryStore:
    def __init__(self, vault_path, notes: list[ClusterNote]) -> None:
        self.vault_path = vault_path
        self.notes = notes
        self.queries = []
        self.write_calls: list[str] = []

    def query_notes(self, query):
        self.queries.append(query)
        notes = [
            note
            for note in self.notes
            if (query.tier is None or query.tier == 1)
            and (query.source is None or note.source == query.source)
        ]
        return notes[: query.limit]

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        self.write_calls.append("store_note")
        raise AssertionError("clustering step must not write Tier 2 notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("update_note")
        raise AssertionError("clustering step must not update Tier 2 notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("add_links")
        raise AssertionError("clustering step must not link Tier 2 notes")

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
                {"id": "coherent", "member_indices": [0, 1]},
                {"id": "incoherent", "member_indices": [2, 3]},
            ],
            "noise_indices": [4],
            "tree_depth": 3,
        }

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_embed", fake_embed)
    monkeypatch.setattr("phosphene.distillation.engine._toolkit_cluster", fake_cluster)

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
    assert result.new_cluster_ids == []
    assert result.updated_cluster_ids == []
    assert result.promoted_count == 2
    assert result.noise_count == 1
    assert result.incoherent_cluster_count == 1
    assert result.cluster_tree_depth == 3
    assert result.feedback_processed == 0
    assert result.assertion_cache_updated == []
    assert store.write_calls == []
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
