from pathlib import Path

import numpy as np

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput
from tools.network_diagnostics import compute_report, format_report, main


def make_store(tmp_path: Path, *, embeddings: bool = True) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "embeddings") if embeddings else None,
        )
    )


def store_note(
    store: MemoryStore,
    title: str,
    *,
    tier: int = 1,
    embedding: np.ndarray | None = None,
    cluster_group: str | None = None,
    links: list[str] | None = None,
    unresolvedness: float = 0.0,
) -> str:
    return store.store_note(
        NoteInput(
            tier=tier,
            content=f"{title} body",
            title=title,
            embedding=embedding,
            cluster_group=cluster_group,
            links=list(links or []),
            unresolvedness=unresolvedness,
        )
    )


def test_empty_vault_report_does_not_crash(tmp_path: Path, capsys) -> None:
    vault_path = tmp_path / "empty-vault"

    assert main(["--vault-path", str(vault_path)]) == 0

    output = capsys.readouterr().out
    assert "Phosphene Network Diagnostics" in output
    assert "Total notes: 0" in output
    assert "N/A - requires Generator output logs" in output


def test_populated_vault_computes_core_metrics(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    cluster_a = store_note(
        store,
        "cluster a",
        tier=2,
        embedding=np.array([1.0, 0.0]),
        cluster_group="a",
        unresolvedness=0.1,
    )
    cluster_b = store_note(
        store,
        "cluster b",
        tier=2,
        embedding=np.array([0.0, 1.0]),
        cluster_group="b",
        unresolvedness=0.5,
    )
    store_note(
        store,
        "near a",
        embedding=np.array([0.9, 0.1]),
        links=[cluster_a],
        unresolvedness=0.7,
    )
    store_note(
        store,
        "outlier",
        embedding=np.array([-1.0, -1.0]),
        links=[cluster_b],
        unresolvedness=1.0,
    )
    store_note(
        store,
        "bridge",
        embedding=np.array([0.8, 0.8]),
        unresolvedness=0.3,
    )

    report = compute_report(store)

    assert report.total_notes == 5
    assert report.cluster_diversity.cluster_count == 2
    assert report.cluster_diversity.mean_inter_cluster_distance == 1.0
    assert report.outlier_ratio.count == 1
    assert report.outlier_ratio.total == 3
    assert report.bridge_node_density.count == 1
    assert report.unresolvedness_histogram == [1, 1, 1, 1, 1]
    assert "Outlier ratio" in format_report(report)


def test_orphaned_link_detection_counts_missing_targets(tmp_path: Path) -> None:
    store = make_store(tmp_path, embeddings=False)
    store_note(store, "valid target")
    store_note(store, "damaged", links=["valid-target-mismatch", "missing-note"])

    report = compute_report(store)

    assert report.compression_damage.count == 2
    assert report.compression_damage.total == 2
    assert report.compression_damage.fraction == 1.0


def test_louvain_divergence_reports_nonzero_when_links_cross_raptor_clusters(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    cluster_a_ids = [
        store_note(
            store,
            f"a {idx}",
            tier=2,
            embedding=np.array([1.0, float(idx) / 100.0]),
            cluster_group="a",
        )
        for idx in range(6)
    ]
    cluster_b_ids = [
        store_note(
            store,
            f"b {idx}",
            tier=2,
            embedding=np.array([float(idx) / 100.0, 1.0]),
            cluster_group="b",
        )
        for idx in range(6)
    ]

    all_ids = cluster_a_ids + cluster_b_ids
    for left, right in zip(all_ids, all_ids[1:]):
        store.add_links(left, [right])

    report = compute_report(store)

    assert report.raptor_louvain_divergence.fraction is not None
    assert report.raptor_louvain_divergence.differing_count > 0
    assert report.raptor_louvain_divergence.compared_count == 12


def test_louvain_divergence_below_threshold_reports_na(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    first_id = store_note(
        store,
        "first",
        tier=2,
        embedding=np.array([1.0, 0.0]),
        cluster_group="a",
    )
    second_id = store_note(
        store,
        "second",
        tier=2,
        embedding=np.array([0.0, 1.0]),
        cluster_group="b",
    )
    store.add_links(first_id, [second_id])

    report = compute_report(store)

    assert report.raptor_louvain_divergence.reason == "N/A - insufficient link density"
