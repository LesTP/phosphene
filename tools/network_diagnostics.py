"""Standalone Memory Store network diagnostics.

This script is intentionally outside the phosphene package. It reads Memory
Store through the public API and prints operator-facing health metrics.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy import ndarray

from phosphene.memory_store import MemoryNote, MemoryStore, MemoryStoreConfig


OUTLIER_SIMILARITY_THRESHOLD = 0.3
BRIDGE_SIMILARITY_THRESHOLD = 0.4
DISTANT_CLUSTER_SIMILARITY_THRESHOLD = 0.5
LOUVAIN_MIN_LINKED_NOTES = 10


@dataclass(frozen=True)
class ClusterDiversity:
    cluster_count: int
    mean_inter_cluster_distance: float | None


@dataclass(frozen=True)
class RatioMetric:
    count: int
    total: int
    fraction: float | None


@dataclass(frozen=True)
class LouvainDivergence:
    fraction: float | None
    differing_count: int
    compared_count: int
    reason: str | None = None


@dataclass(frozen=True)
class DiagnosticsReport:
    total_notes: int
    tier_counts: dict[int, int]
    mean_link_degree: float
    density_cluster_count: int
    unresolved_count: int
    max_unresolvedness: float
    cluster_diversity: ClusterDiversity
    outlier_ratio: RatioMetric
    bridge_node_density: RatioMetric
    unresolvedness_histogram: list[int]
    compression_damage: RatioMetric
    raptor_louvain_divergence: LouvainDivergence


def compute_report(store: MemoryStore) -> DiagnosticsReport:
    """Compute all diagnostics from a Memory Store snapshot."""
    notes = _load_all_notes(store)
    density = store.get_density_metrics()
    centroids = _cluster_centroids(notes)

    return DiagnosticsReport(
        total_notes=density.note_count,
        tier_counts=dict(density.tier_counts),
        mean_link_degree=density.mean_link_degree,
        density_cluster_count=density.cluster_count,
        unresolved_count=density.unresolved_count,
        max_unresolvedness=density.max_unresolvedness,
        cluster_diversity=_cluster_diversity(centroids),
        outlier_ratio=_outlier_ratio(notes, centroids),
        bridge_node_density=_bridge_node_density(notes, centroids),
        unresolvedness_histogram=_unresolvedness_histogram(notes),
        compression_damage=_compression_damage(notes),
        raptor_louvain_divergence=_raptor_louvain_divergence(notes),
    )


def format_report(report: DiagnosticsReport) -> str:
    """Format diagnostics as a human-readable report."""
    lines = [
        "Phosphene Network Diagnostics",
        "==============================",
        "",
        "Note/tier summary",
        f"- Total notes: {report.total_notes}",
        (
            "- Tier counts: "
            f"T1={report.tier_counts.get(1, 0)}, "
            f"T2={report.tier_counts.get(2, 0)}, "
            f"T3={report.tier_counts.get(3, 0)}"
        ),
        f"- Mean link degree: {report.mean_link_degree:.3f}",
        f"- Density cluster count: {report.density_cluster_count}",
        f"- Unresolved notes (>0.5): {report.unresolved_count}",
        f"- Max unresolvedness: {report.max_unresolvedness:.3f}",
        "",
        "Cluster diversity",
        f"- Clusters with embeddings: {report.cluster_diversity.cluster_count}",
        (
            "- Mean inter-cluster distance: "
            f"{_format_optional_float(report.cluster_diversity.mean_inter_cluster_distance)}"
        ),
        "",
        "Outlier ratio",
        (
            f"- Count: {report.outlier_ratio.count}/{report.outlier_ratio.total} "
            f"({_format_optional_float(report.outlier_ratio.fraction)})"
        ),
        "",
        "Bridge-node density",
        (
            f"- Count: {report.bridge_node_density.count}/{report.bridge_node_density.total} "
            f"({_format_optional_float(report.bridge_node_density.fraction)})"
        ),
        "",
        "Unresolvedness distribution",
        f"- [0.0, 0.2): {report.unresolvedness_histogram[0]}",
        f"- [0.2, 0.4): {report.unresolvedness_histogram[1]}",
        f"- [0.4, 0.6): {report.unresolvedness_histogram[2]}",
        f"- [0.6, 0.8): {report.unresolvedness_histogram[3]}",
        f"- [0.8, 1.0]: {report.unresolvedness_histogram[4]}",
        "",
        "Compression damage",
        (
            f"- Orphaned links: {report.compression_damage.count}/"
            f"{report.compression_damage.total} "
            f"({_format_optional_float(report.compression_damage.fraction)})"
        ),
        "",
        "RAPTOR-Louvain divergence",
        f"- {_format_louvain(report.raptor_louvain_divergence)}",
        "",
        "Mirror index",
        "- N/A - requires Generator output logs",
        "",
        "Free-play value ratio",
        "- N/A - requires Generator output logs",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Memory Store network diagnostics.")
    parser.add_argument("--vault-path", required=True, help="Path to the Memory Store vault.")
    parser.add_argument(
        "--embedding-path",
        default=None,
        help="Path to Memory Store sidecar embeddings. Defaults to no embedding storage.",
    )
    args = parser.parse_args(argv)

    store = MemoryStore(
        MemoryStoreConfig(
            vault_path=args.vault_path,
            embedding_path=args.embedding_path,
        )
    )
    print(format_report(compute_report(store)))
    return 0


def _load_all_notes(store: MemoryStore) -> list[MemoryNote]:
    return [store.get_note(entry.note_id) for entry in store.get_index()]


def _cluster_centroids(notes: Iterable[MemoryNote]) -> dict[str, ndarray]:
    grouped: dict[str, list[ndarray]] = defaultdict(list)
    for note in notes:
        if note.tier == 2 and note.cluster_group and note.embedding is not None:
            grouped[note.cluster_group].append(note.embedding)
    return {
        cluster_group: np.mean(np.stack(embeddings), axis=0)
        for cluster_group, embeddings in grouped.items()
    }


def _cluster_diversity(centroids: dict[str, ndarray]) -> ClusterDiversity:
    if len(centroids) < 2:
        return ClusterDiversity(
            cluster_count=len(centroids),
            mean_inter_cluster_distance=None,
        )

    distances = [
        1.0 - _cosine_similarity(left, right)
        for left, right in combinations(centroids.values(), 2)
    ]
    return ClusterDiversity(
        cluster_count=len(centroids),
        mean_inter_cluster_distance=float(np.mean(distances)),
    )


def _outlier_ratio(notes: list[MemoryNote], centroids: dict[str, ndarray]) -> RatioMetric:
    tier1_embedded = [
        note for note in notes if note.tier == 1 and note.embedding is not None
    ]
    if not tier1_embedded or not centroids:
        return RatioMetric(count=0, total=len(tier1_embedded), fraction=None)

    outliers = 0
    for note in tier1_embedded:
        max_similarity = max(_cosine_similarity(note.embedding, centroid) for centroid in centroids.values())
        if max_similarity < OUTLIER_SIMILARITY_THRESHOLD:
            outliers += 1
    return _ratio(outliers, len(tier1_embedded))


def _bridge_node_density(notes: list[MemoryNote], centroids: dict[str, ndarray]) -> RatioMetric:
    embedded_notes = [note for note in notes if note.embedding is not None]
    if not embedded_notes or len(centroids) < 2:
        return RatioMetric(count=0, total=len(embedded_notes), fraction=None)

    bridge_count = 0
    for note in embedded_notes:
        similar_clusters = [
            cluster_group
            for cluster_group, centroid in centroids.items()
            if _cosine_similarity(note.embedding, centroid) > BRIDGE_SIMILARITY_THRESHOLD
        ]
        if len(similar_clusters) < 2:
            continue
        distant_pair_exists = any(
            _cosine_similarity(centroids[left], centroids[right])
            < DISTANT_CLUSTER_SIMILARITY_THRESHOLD
            for left, right in combinations(similar_clusters, 2)
        )
        if distant_pair_exists:
            bridge_count += 1
    return _ratio(bridge_count, len(embedded_notes))


def _unresolvedness_histogram(notes: list[MemoryNote]) -> list[int]:
    bins = [0, 0, 0, 0, 0]
    for note in notes:
        score = min(max(note.unresolvedness, 0.0), 1.0)
        index = min(int(score / 0.2), 4)
        bins[index] += 1
    return bins


def _compression_damage(notes: list[MemoryNote]) -> RatioMetric:
    existing_ids = {note.note_id for note in notes}
    orphaned = 0
    total_links = 0
    for note in notes:
        total_links += len(note.links)
        orphaned += sum(1 for target_id in note.links if target_id not in existing_ids)
    return _ratio(orphaned, total_links)


def _raptor_louvain_divergence(notes: list[MemoryNote]) -> LouvainDivergence:
    note_by_id = {note.note_id: note for note in notes}
    adjacency = _linked_adjacency(notes, note_by_id)
    linked_note_ids = {note_id for note_id, neighbors in adjacency.items() if neighbors}
    if len(linked_note_ids) < LOUVAIN_MIN_LINKED_NOTES:
        return LouvainDivergence(
            fraction=None,
            differing_count=0,
            compared_count=0,
            reason="N/A - insufficient link density",
        )

    partition = _louvain_partition(adjacency)
    tier2_notes = [
        note for note in notes if note.tier == 2 and note.cluster_group and note.note_id in partition
    ]
    if not tier2_notes:
        return LouvainDivergence(
            fraction=None,
            differing_count=0,
            compared_count=0,
            reason="N/A - no Tier 2 cluster assignments",
        )

    community_majorities = _community_majority_clusters(tier2_notes, partition)
    differing = sum(
        1
        for note in tier2_notes
        if community_majorities.get(partition[note.note_id]) != note.cluster_group
    )
    metric = _ratio(differing, len(tier2_notes))
    return LouvainDivergence(
        fraction=metric.fraction,
        differing_count=metric.count,
        compared_count=metric.total,
    )


def _linked_adjacency(
    notes: list[MemoryNote],
    note_by_id: dict[str, MemoryNote],
) -> dict[str, set[str]]:
    adjacency = {note.note_id: set() for note in notes}
    for note in notes:
        for target_id in note.links:
            if target_id not in note_by_id:
                continue
            adjacency[note.note_id].add(target_id)
            adjacency[target_id].add(note.note_id)
    return adjacency


def _louvain_partition(adjacency: dict[str, set[str]]) -> dict[str, int]:
    try:
        import community  # type: ignore[import-untyped]
        import networkx as nx  # type: ignore[import-untyped]
        best_partition = community.best_partition
    except (AttributeError, ModuleNotFoundError):
        return _component_partition(adjacency)

    graph = nx.Graph()
    for note_id, neighbors in adjacency.items():
        graph.add_node(note_id)
        for neighbor_id in neighbors:
            graph.add_edge(note_id, neighbor_id)
    if graph.number_of_edges() == 0:
        return {note_id: index for index, note_id in enumerate(sorted(adjacency))}
    return best_partition(graph)


def _component_partition(adjacency: dict[str, set[str]]) -> dict[str, int]:
    partition: dict[str, int] = {}
    community_id = 0
    for note_id in sorted(adjacency):
        if note_id in partition:
            continue
        stack = [note_id]
        partition[note_id] = community_id
        while stack:
            current_id = stack.pop()
            for neighbor_id in adjacency[current_id]:
                if neighbor_id in partition:
                    continue
                partition[neighbor_id] = community_id
                stack.append(neighbor_id)
        community_id += 1
    return partition


def _community_majority_clusters(
    tier2_notes: list[MemoryNote],
    partition: dict[str, int],
) -> dict[int, str]:
    counts: dict[int, Counter[str]] = defaultdict(Counter)
    for note in tier2_notes:
        counts[partition[note.note_id]][note.cluster_group or ""] += 1
    return {
        community_id: counter.most_common(1)[0][0]
        for community_id, counter in counts.items()
    }


def _cosine_similarity(left: ndarray, right: ndarray) -> float:
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0 or left.shape != right.shape:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def _ratio(count: int, total: int) -> RatioMetric:
    return RatioMetric(
        count=count,
        total=total,
        fraction=(count / total) if total else None,
    )


def _format_optional_float(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def _format_louvain(value: LouvainDivergence) -> str:
    if value.reason is not None:
        return value.reason
    return (
        f"{value.differing_count}/{value.compared_count} "
        f"({_format_optional_float(value.fraction)})"
    )


if __name__ == "__main__":
    raise SystemExit(main())
