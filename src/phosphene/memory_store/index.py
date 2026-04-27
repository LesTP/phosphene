"""In-memory index for Memory Store notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from phosphene.memory_store.errors import VaultError
from phosphene.memory_store.types import IndexEntry, MemoryNote


@dataclass
class IndexedNote:
    note_id: str
    tier: int
    title: str
    importance: float
    unresolvedness: float
    tags: list[str]
    source: str | None
    created_at: datetime
    links: list[str]
    path: Path


class Index:
    """Track note metadata and inbound link counts for a vault."""

    def __init__(self) -> None:
        self.entries: dict[str, IndexedNote] = {}
        self.inbound: dict[str, int] = {}

    def register(self, note: MemoryNote, path: Path) -> None:
        """Register or refresh a note entry, then rebuild inbound counts."""
        existing = self.entries.get(note.note_id)
        if existing is not None and existing.path != path:
            raise VaultError(f"duplicate note_id in vault: {note.note_id}")

        self.entries[note.note_id] = IndexedNote(
            note_id=note.note_id,
            tier=note.tier,
            title=note.title,
            importance=note.importance,
            unresolvedness=note.unresolvedness,
            tags=list(note.tags),
            source=note.source,
            created_at=note.created_at,
            links=list(note.links),
            path=path,
        )
        self.rebuild_inbound()

    def rebuild_inbound(self) -> None:
        """Recompute inbound link counts from all indexed outbound links."""
        inbound = {note_id: 0 for note_id in self.entries}
        for entry in self.entries.values():
            for target_id in entry.links:
                inbound[target_id] = inbound.get(target_id, 0) + 1
        self.inbound = inbound

    def inbound_count(self, note_id: str) -> int:
        return self.inbound.get(note_id, 0)

    def inbound_for(self, note_id: str) -> list[str]:
        """Return note ids that link to the given note id."""
        return [
            entry.note_id
            for entry in self.entries.values()
            if note_id in entry.links
        ]

    def to_index_entry(self, note_id: str) -> IndexEntry:
        entry = self.entries[note_id]
        return IndexEntry(
            note_id=entry.note_id,
            tier=entry.tier,
            title=entry.title,
            importance=entry.importance,
            unresolvedness=entry.unresolvedness,
            link_count=self.inbound_count(note_id) + len(entry.links),
            tags=list(entry.tags),
            created_at=entry.created_at,
        )
