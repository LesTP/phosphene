"""Rebuild Tier 2 cross-links from stored cluster centroids."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Sequence

sys.path.insert(0, "src")
sys.path.insert(0, ".python_deps")

import numpy as np

from phosphene.memory_store.embeddings import load_embedding
from phosphene.memory_store.types import MemoryNote
from phosphene.memory_store.vault import parse_note, serialize_note


@dataclass(frozen=True)
class RebuildReport:
    tier2_count: int
    rewritten_count: int
    missing_embedding_count: int
    stripped_t2_link_count: int
    preserved_non_t2_link_count: int
    added_t2_link_count: int
    t2_link_distribution: dict[int, int]
    dry_run: bool


def rebuild_t2_crosslinks(
    *,
    vault_path: Path,
    embedding_path: Path | None = None,
    threshold: float = 0.45,
    max_links: int = 15,
    dry_run: bool = True,
) -> RebuildReport:
    """Strip existing T2 links and rebuild them from centroid similarity."""
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError("threshold must be in [0.0, 1.0]")
    if max_links < 0:
        raise ValueError("max_links must be non-negative")

    embedding_path = embedding_path or vault_path / ".embeddings"
    tier1_ids = _note_ids(vault_path / "tier1")
    tier2_notes = _load_notes(vault_path / "tier2")
    tier2_ids = {note.note_id for note, _path in tier2_notes}
    embeddings = _load_t2_embeddings(tier2_notes, embedding_path)
    rebuilt_links = _build_similarity_links(
        [note for note, _path in tier2_notes],
        embeddings,
        threshold=threshold,
        max_links=max_links,
    )

    missing_embedding_count = len(tier2_notes) - len(embeddings)
    stripped_t2_link_count = 0
    preserved_non_t2_link_count = 0
    added_t2_link_count = 0
    distribution: Counter[int] = Counter()
    rewritten_count = 0

    for note, path in tier2_notes:
        preserved_links: list[str] = []
        for link in note.links:
            if link in tier2_ids:
                stripped_t2_link_count += 1
            else:
                preserved_links.append(link)
                if link in tier1_ids:
                    preserved_non_t2_link_count += 1

        new_t2_links = rebuilt_links.get(note.note_id, [])
        added_t2_link_count += len(new_t2_links)
        distribution[len(new_t2_links)] += 1

        new_links = _dedupe_preserving_order(preserved_links + new_t2_links)
        if new_links != note.links or note.link_count != len(new_links):
            rewritten_count += 1
            if not dry_run:
                note.links = new_links
                note.link_count = len(new_links)
                path.write_text(serialize_note(note), encoding="utf-8")

    return RebuildReport(
        tier2_count=len(tier2_notes),
        rewritten_count=rewritten_count,
        missing_embedding_count=missing_embedding_count,
        stripped_t2_link_count=stripped_t2_link_count,
        preserved_non_t2_link_count=preserved_non_t2_link_count,
        added_t2_link_count=added_t2_link_count,
        t2_link_distribution=dict(sorted(distribution.items())),
        dry_run=dry_run,
    )


def format_report(report: RebuildReport) -> str:
    mode = "dry-run" if report.dry_run else "write"
    distribution = ", ".join(
        f"{link_count}:{note_count}"
        for link_count, note_count in report.t2_link_distribution.items()
    )
    return "\n".join(
        [
            f"mode: {mode}",
            f"tier2_count: {report.tier2_count}",
            f"rewritten_count: {report.rewritten_count}",
            f"missing_embedding_count: {report.missing_embedding_count}",
            f"stripped_t2_link_count: {report.stripped_t2_link_count}",
            f"preserved_non_t2_link_count: {report.preserved_non_t2_link_count}",
            f"added_t2_link_count: {report.added_t2_link_count}",
            f"t2_link_distribution: {distribution or 'empty'}",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip all Tier 2 to Tier 2 links and rebuild related links."
    )
    parser.add_argument("--vault-path", type=Path, default=Path("vault"))
    parser.add_argument("--embedding-path", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=0.45)
    parser.add_argument("--max-links", type=int, default=15)
    parser.add_argument(
        "--dry-run",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Preview changes without rewriting notes (default: true).",
    )
    args = parser.parse_args(argv)

    report = rebuild_t2_crosslinks(
        vault_path=args.vault_path,
        embedding_path=args.embedding_path,
        threshold=args.threshold,
        max_links=args.max_links,
        dry_run=args.dry_run,
    )
    print(format_report(report))
    return 0


def _load_notes(tier_path: Path) -> list[tuple[MemoryNote, Path]]:
    if not tier_path.exists():
        return []
    notes: list[tuple[MemoryNote, Path]] = []
    for path in sorted(tier_path.glob("*.md")):
        notes.append((parse_note(path.read_text(encoding="utf-8")), path))
    return notes


def _note_ids(tier_path: Path) -> set[str]:
    return {note.note_id for note, _path in _load_notes(tier_path)}


def _load_t2_embeddings(
    tier2_notes: Sequence[tuple[MemoryNote, Path]],
    embedding_path: Path,
) -> dict[str, np.ndarray]:
    embeddings: dict[str, np.ndarray] = {}
    for note, _path in tier2_notes:
        embedding = load_embedding(embedding_path, note.note_id)
        if embedding is not None:
            embeddings[note.note_id] = np.asarray(embedding, dtype=float)
    return embeddings


def _build_similarity_links(
    notes: Sequence[MemoryNote],
    embeddings: dict[str, np.ndarray],
    *,
    threshold: float,
    max_links: int,
) -> dict[str, list[str]]:
    if max_links == 0:
        return {note.note_id: [] for note in notes}

    links: dict[str, list[str]] = {}
    for source in notes:
        source_embedding = embeddings.get(source.note_id)
        if source_embedding is None:
            links[source.note_id] = []
            continue

        scored_targets: list[tuple[float, str]] = []
        for target in notes:
            if target.note_id == source.note_id:
                continue
            target_embedding = embeddings.get(target.note_id)
            if target_embedding is None:
                continue
            similarity = _cosine_similarity(source_embedding, target_embedding)
            if similarity >= threshold:
                scored_targets.append((similarity, target.note_id))
        scored_targets.sort(key=lambda item: (-item[0], item[1]))
        links[source.note_id] = [
            target_id for _similarity, target_id in scored_targets[:max_links]
        ]
    return links


def _cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return 0.0
    left_norm = float(np.linalg.norm(left))
    right_norm = float(np.linalg.norm(right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return float(np.dot(left, right) / (left_norm * right_norm))


def _dedupe_preserving_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped


if __name__ == "__main__":
    raise SystemExit(main())
