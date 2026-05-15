"""Vault-backed Memory Store implementation."""

from __future__ import annotations

import os
import hashlib
import json
import datetime as datetime_module
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from numpy import ndarray

from phosphene.memory_store.errors import (
    AlreadySupersededError,
    DimensionMismatchError,
    InvalidScoreError,
    InvalidTierError,
    NoteNotFoundError,
    TierMismatchError,
    TitleTooLongError,
    VaultError,
)
from phosphene.memory_store.embeddings import delete_embedding, load_embedding, save_embedding
from phosphene.memory_store.index import Index
from phosphene.memory_store.types import (
    DensityMetrics,
    IndexEntry,
    MemoryNote,
    MemoryStoreConfig,
    NoteInput,
    NotePatch,
    NoteQuery,
    PersonalityContext,
    DecayReport,
)
from phosphene.memory_store.vault import generate_note_id, note_path, parse_note, serialize_note

_VALID_TIERS = {1, 2, 3}
_MAX_TITLE_LENGTH = 150
_INDEX_CACHE_VERSION = 1
_INDEX_CACHE_FILENAME = ".index_cache.json"


class MemoryStore:
    """Store Memory Store notes in a tiered markdown vault."""

    def __init__(self, config: MemoryStoreConfig):
        self.config = config
        self.vault_path = Path(config.vault_path)
        self.embedding_path = Path(config.embedding_path) if config.embedding_path else None
        self._index = Index()

        self._ensure_vault()
        self._rebuild_index()

    def store_note(self, note: NoteInput) -> str:
        """Persist a note and return its generated note id."""
        _validate_tier(note.tier)
        _validate_title(note.title)
        _validate_score("importance", note.importance)
        _validate_score("unresolvedness", note.unresolvedness)

        created_at = note.created_at or datetime.now(timezone.utc)
        note_id = generate_note_id(note.title, created_at, note.content)
        memory_note = MemoryNote(
            note_id=note_id,
            tier=note.tier,
            content=note.content,
            title=note.title,
            importance=note.importance,
            unresolvedness=note.unresolvedness,
            links=list(note.links),
            tags=list(note.tags),
            source=note.source,
            friction_target=note.friction_target,
            embedding=note.embedding,
            attractor_relevance=note.attractor_relevance,
            cluster_group=note.cluster_group,
            supersedes=None,
            created_at=created_at,
            updated_at=created_at,
            link_count=len(note.links),
            decay_deadline=None,
            change_summary=None,
        )

        path = note_path(self.vault_path, note.tier, note_id)
        path.write_text(serialize_note(memory_note), encoding="utf-8")
        self._save_embedding(note_id, note.embedding)
        self._index.register(memory_note, path)
        return note_id

    def get_index(self, tier: int | None = None) -> list[IndexEntry]:
        """Return lightweight index entries sorted by creation time descending."""
        if tier is not None:
            _validate_tier(tier)

        entries = [
            self._index.to_index_entry(note_id)
            for note_id, entry in self._index.entries.items()
            if tier is None or entry.tier == tier
        ]
        return sorted(entries, key=lambda entry: entry.created_at, reverse=True)

    def get_note(self, note_id: str) -> MemoryNote:
        """Load a note by id from any tier."""
        return self._load_note(note_id)

    def get_density_metrics(self) -> DensityMetrics:
        """Return a cheap density snapshot derived from the in-memory index."""
        entries = list(self._index.entries.values())
        note_count = len(entries)
        tier_counts = {tier: 0 for tier in sorted(_VALID_TIERS)}
        link_degree_total = 0
        clusters: set[str] = set()
        unresolved_count = 0
        max_unresolvedness = 0.0

        for entry in entries:
            tier_counts[entry.tier] += 1
            link_degree_total += self._index.inbound_count(entry.note_id) + len(entry.links)
            if entry.tier == 2 and entry.cluster_group is not None:
                clusters.add(entry.cluster_group)
            if entry.unresolvedness > 0.5:
                unresolved_count += 1
            max_unresolvedness = max(max_unresolvedness, entry.unresolvedness)

        mean_link_degree = link_degree_total / note_count if note_count else 0.0
        return DensityMetrics(
            note_count=note_count,
            tier_counts=tier_counts,
            mean_link_degree=mean_link_degree,
            cluster_count=len(clusters),
            unresolved_count=unresolved_count,
            max_unresolvedness=max_unresolvedness,
        )

    def query_notes(self, query: NoteQuery) -> list[MemoryNote]:
        """Return full notes matching the query filters."""
        if query.tier is not None:
            _validate_tier(query.tier)

        valid_order_fields = {"created_at", "importance", "unresolvedness", "link_count"}
        if query.order_by not in valid_order_fields:
            raise ValueError(f"order_by must be one of {sorted(valid_order_fields)}")

        matching_ids = [
            note_id
            for note_id, entry in self._index.entries.items()
            if (query.tier is None or entry.tier == query.tier)
            and (query.min_importance is None or entry.importance >= query.min_importance)
            and (
                query.min_unresolvedness is None
                or entry.unresolvedness >= query.min_unresolvedness
            )
            and (query.tags is None or bool(set(query.tags) & set(entry.tags)))
            and (query.source is None or entry.source == query.source)
            and (query.since is None or entry.created_at >= query.since)
            and (query.until is None or entry.created_at <= query.until)
        ]
        notes = [self._load_note(note_id) for note_id in matching_ids]
        notes.sort(
            key=lambda note: getattr(note, query.order_by),
            reverse=query.descending,
        )
        return notes[: query.limit]

    def search_by_embedding(
        self,
        embedding: ndarray,
        tier: int | None = None,
        limit: int = 10,
    ) -> list[tuple[MemoryNote, float]]:
        """Return notes with stored embeddings ranked by cosine similarity."""
        if tier is not None:
            _validate_tier(tier)

        if self.embedding_path is None:
            return []

        query_norm = float(np.linalg.norm(embedding))
        if query_norm == 0.0:
            return []

        scored_notes: list[tuple[MemoryNote, float]] = []
        for note_id, entry in self._index.entries.items():
            if tier is not None and entry.tier != tier:
                continue

            stored_embedding = self._load_embedding(note_id)
            if stored_embedding is None:
                continue
            if stored_embedding.shape != embedding.shape:
                raise DimensionMismatchError(
                    "query embedding dimensions do not match stored embedding "
                    f"for note {note_id}: {embedding.shape} != {stored_embedding.shape}"
                )

            stored_norm = float(np.linalg.norm(stored_embedding))
            if stored_norm == 0.0:
                continue

            note = self._load_note(note_id)
            similarity = float(np.dot(embedding, stored_embedding) / (query_norm * stored_norm))
            scored_notes.append((note, similarity))

        scored_notes.sort(key=lambda result: result[1], reverse=True)
        return scored_notes[:limit]

    def update_note(self, note_id: str, patch: NotePatch) -> MemoryNote:
        """Apply a partial update to a note and return the updated note."""
        path = self._note_path_from_index(note_id)
        note = parse_note(path.read_text(encoding="utf-8"))

        if patch.title is not None:
            _validate_title(patch.title)
            note.title = patch.title
        if patch.importance is not None:
            _validate_score("importance", patch.importance)
            note.importance = patch.importance
        if patch.unresolvedness is not None:
            _validate_score("unresolvedness", patch.unresolvedness)
            note.unresolvedness = patch.unresolvedness
        if patch.content is not None:
            note.content = patch.content
        if patch.links is not None:
            note.links = list(patch.links)
            note.link_count = len(note.links)
        if patch.tags is not None:
            note.tags = list(patch.tags)
        if patch.embedding is not None:
            note.embedding = patch.embedding
        if patch.attractor_relevance is not None:
            note.attractor_relevance = patch.attractor_relevance

        updated_at = datetime.now(timezone.utc).replace(microsecond=0)
        if updated_at <= note.updated_at:
            updated_at = note.updated_at + timedelta(seconds=1)
        note.updated_at = updated_at

        note.link_count = len(note.links)
        path.write_text(serialize_note(note), encoding="utf-8")
        self._save_embedding(note_id, patch.embedding)
        self._index.register(note, path)
        note.embedding = self._load_embedding(note_id)
        return self._with_computed_link_count(note)

    def add_links(self, source_id: str, target_ids: list[str]) -> None:
        """Add outbound links from a source note to existing target notes."""
        if not target_ids:
            return

        path = self._note_path_from_index(source_id)
        for target_id in target_ids:
            if target_id != source_id:
                self._note_path_from_index(target_id)

        note = parse_note(path.read_text(encoding="utf-8"))
        links = list(note.links)
        seen = set(links)
        for target_id in target_ids:
            if target_id == source_id or target_id in seen:
                continue
            links.append(target_id)
            seen.add(target_id)

        if links == note.links:
            return

        note.links = links
        updated_at = datetime.now(timezone.utc).replace(microsecond=0)
        if updated_at <= note.updated_at:
            updated_at = note.updated_at + timedelta(seconds=1)
        note.updated_at = updated_at
        note.link_count = len(note.links)

        path.write_text(serialize_note(note), encoding="utf-8")
        self._index.register(note, path)

    def get_linked(self, note_id: str, depth: int = 1) -> list[MemoryNote]:
        """Return notes reachable through outbound and inbound links."""
        if depth < 1 or depth > 3:
            raise ValueError("depth must be between 1 and 3")

        self._note_path_from_index(note_id)

        linked_ids: list[str] = []
        visited = {note_id}
        frontier = [note_id]

        for _ in range(depth):
            next_frontier: list[str] = []
            for current_id in frontier:
                current_note = self._load_note(current_id)
                neighbor_ids = list(current_note.links) + self._index.inbound_for(current_id)
                for neighbor_id in neighbor_ids:
                    if neighbor_id in visited or neighbor_id not in self._index.entries:
                        continue
                    visited.add(neighbor_id)
                    linked_ids.append(neighbor_id)
                    next_frontier.append(neighbor_id)
            frontier = next_frontier
            if not frontier:
                break

        return [self._load_note(linked_id) for linked_id in linked_ids]

    def get_personality_context(self) -> PersonalityContext:
        """Return current non-superseded Tier 3 notes with a stable version id."""
        self._rebuild_index()
        superseded_ids = {
            entry.supersedes
            for entry in self._index.entries.values()
            if entry.tier == 3 and entry.supersedes is not None
        }
        selected_ids = [
            note_id
            for note_id, entry in self._index.entries.items()
            if entry.tier == 3 and note_id not in superseded_ids
        ]
        notes = [self._load_note(note_id) for note_id in selected_ids]
        notes.sort(key=lambda note: note.note_id)

        version_payload = "\0".join(
            f"{note.note_id}|{note.updated_at.isoformat()}" for note in notes
        )
        version_id = hashlib.sha1(version_payload.encode("utf-8")).hexdigest()
        return PersonalityContext(personality_files=notes, version_id=version_id)

    def run_decay(self) -> DecayReport:
        """Expire notes according to configured decay windows."""
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []
        extended_count = 0
        tier_breakdown = {tier: 0 for tier in sorted(_VALID_TIERS)}

        for note_id, entry in list(self._index.entries.items()):
            note = self._load_note(note_id)
            expired = False

            if entry.tier == 1:
                age = now - entry.created_at
                base_days = self.config.tier1_base_retention_days
                retention_days = base_days
                was_extended = False
                if self._index.inbound_count(note_id) >= self.config.link_density_threshold:
                    retention_days = self.config.tier1_extended_retention_days
                    was_extended = True

                effective_days = retention_days * (1 + (note.attractor_relevance or 0.0))
                base_window = timedelta(days=base_days)
                effective_window = timedelta(days=effective_days)

                if age > effective_window:
                    expired = True
                elif was_extended and age > base_window:
                    extended_count += 1
            elif entry.tier == 2:
                age = now - entry.created_at
                retention_window = timedelta(days=2 * self.config.tier2_cycle_window_days)
                expired = age > retention_window
            elif entry.tier == 3:
                expired = note.decay_deadline is not None and now > note.decay_deadline

            if expired:
                expired_ids.append(note_id)
                tier_breakdown[entry.tier] += 1

        for note_id in expired_ids:
            self._expire_note(note_id)

        return DecayReport(
            expired_count=len(expired_ids),
            expired_ids=expired_ids,
            extended_count=extended_count,
            tier_breakdown=tier_breakdown,
        )

    def supersede(
        self,
        note_id: str,
        new_content: str,
        new_title: str,
        change_summary: str,
    ) -> MemoryNote:
        """Create a new Tier 3 version and schedule the old version for decay."""
        old_path = self._note_path_from_index(note_id)
        old_note = parse_note(old_path.read_text(encoding="utf-8"))

        if old_note.tier != 3:
            raise TierMismatchError(f"supersede requires a Tier 3 note: {note_id}")
        if any(
            entry.tier == 3 and entry.supersedes == note_id
            for entry in self._index.entries.values()
        ):
            raise AlreadySupersededError(f"note has already been superseded: {note_id}")
        _validate_title(new_title)

        created_at = datetime.now(timezone.utc)
        new_note_id = generate_note_id(new_title, created_at)
        new_note = MemoryNote(
            note_id=new_note_id,
            tier=3,
            content=new_content,
            title=new_title,
            importance=old_note.importance,
            unresolvedness=old_note.unresolvedness,
            links=list(old_note.links),
            tags=list(old_note.tags),
            source=old_note.source,
            friction_target=old_note.friction_target,
            embedding=self._load_embedding(note_id),
            attractor_relevance=old_note.attractor_relevance,
            cluster_group=old_note.cluster_group,
            supersedes=note_id,
            created_at=created_at,
            updated_at=created_at,
            link_count=len(old_note.links),
            decay_deadline=None,
            change_summary=change_summary,
        )

        old_note.decay_deadline = created_at + timedelta(
            days=self.config.tier3_superseded_retention_days
        )
        old_note.link_count = len(old_note.links)

        new_path = note_path(self.vault_path, 3, new_note_id)
        new_path.write_text(serialize_note(new_note), encoding="utf-8")
        self._save_embedding(new_note_id, new_note.embedding)
        self._index.register(new_note, new_path)

        old_path.write_text(serialize_note(old_note), encoding="utf-8")
        self._index.register(old_note, old_path)
        return self._load_note(new_note_id)

    def _ensure_vault(self) -> None:
        if self.vault_path.exists() and not self.vault_path.is_dir():
            raise VaultError(f"vault path is not a directory: {self.vault_path}")

        try:
            self.vault_path.mkdir(parents=True, exist_ok=True)
            for tier in _VALID_TIERS:
                (self.vault_path / f"tier{tier}").mkdir(exist_ok=True)
        except OSError as exc:
            raise VaultError(f"could not create vault directories: {self.vault_path}") from exc

        if not os.access(self.vault_path, os.W_OK):
            raise VaultError(f"vault path is not writable: {self.vault_path}")

    def _rebuild_index(self) -> None:
        import time as _time
        _t0 = _time.monotonic()
        if not self.config.skip_cache and self._load_index_cache():
            print(f"  MemoryStore: index loaded from cache in {_time.monotonic() - _t0:.1f}s "
                  f"({len(self._index.entries)} entries)")
            return

        print(f"  MemoryStore: cache miss, scanning vault...")
        self._index = Index()
        for tier in sorted(_VALID_TIERS):
            tier_t0 = _time.monotonic()
            count = 0
            for path in sorted((self.vault_path / f"tier{tier}").glob("*.md")):
                note = parse_note(path.read_text(encoding="utf-8"))
                self._index.register(note, path)
                count += 1
            print(f"    tier{tier}: {count} notes in {_time.monotonic() - tier_t0:.1f}s")
        print(f"  MemoryStore: full scan complete in {_time.monotonic() - _t0:.1f}s "
              f"({len(self._index.entries)} entries)")
        self._write_index_cache()

    def _write_index_cache(self) -> None:
        cache_path = self.vault_path / _INDEX_CACHE_FILENAME
        notes = [
            parse_note(entry.path.read_text(encoding="utf-8"))
            for entry in sorted(
                self._index.entries.values(),
                key=lambda indexed: (indexed.tier, indexed.note_id),
            )
        ]
        payload = {
            "version": _INDEX_CACHE_VERSION,
            "created_at": datetime_module.datetime.now(timezone.utc).isoformat(),
            "notes": [
                {
                    "note_id": note.note_id,
                    "tier": note.tier,
                    "title": note.title,
                    "path": str(
                        note_path(self.vault_path, note.tier, note.note_id).relative_to(
                            self.vault_path
                        )
                    ),
                    "created_at": note.created_at.isoformat(),
                    "updated_at": note.updated_at.isoformat(),
                    "supersedes": note.supersedes,
                    "links": list(note.links),
                    "tags": list(note.tags),
                    "importance": note.importance,
                    "unresolvedness": note.unresolvedness,
                    "cluster_group": note.cluster_group,
                    "source": note.source,
                    "link_count": self._index.inbound_count(note.note_id) + len(note.links),
                    "decay_deadline": (
                        note.decay_deadline.isoformat()
                        if note.decay_deadline is not None
                        else None
                    ),
                }
                for note in notes
            ],
        }
        tmp_path = cache_path.with_name(f"{cache_path.name}.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(cache_path)

    def _read_index_cache(self) -> dict[str, object] | None:
        cache_path = self.vault_path / _INDEX_CACHE_FILENAME
        if not cache_path.exists():
            return None
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _load_index_cache(self) -> bool:
        payload = self._read_index_cache()
        if payload is None or payload.get("version") != _INDEX_CACHE_VERSION:
            return False

        cache_created_at = _parse_cache_datetime(payload.get("created_at"))
        newest_note_mtime = self._newest_note_mtime()
        if cache_created_at is None or cache_created_at <= newest_note_mtime:
            return False

        notes = payload.get("notes")
        if not isinstance(notes, list):
            return False
        cached_paths = {
            note_payload.get("path")
            for note_payload in notes
            if isinstance(note_payload, dict)
        }
        if cached_paths != self._note_relative_paths():
            return False

        cached_index = Index()
        try:
            for note_payload in notes:
                if not isinstance(note_payload, dict):
                    return False
                relative_path = note_payload["path"]
                if not isinstance(relative_path, str):
                    return False
                path = self.vault_path / relative_path
                if not path.is_file():
                    return False
                note = MemoryNote(
                    note_id=str(note_payload["note_id"]),
                    tier=int(note_payload["tier"]),
                    content="",
                    title=str(note_payload["title"]),
                    importance=float(note_payload["importance"]),
                    unresolvedness=float(note_payload["unresolvedness"]),
                    links=list(note_payload["links"]),
                    tags=list(note_payload["tags"]),
                    source=note_payload["source"],
                    friction_target=None,
                    embedding=None,
                    attractor_relevance=None,
                    cluster_group=note_payload["cluster_group"],
                    supersedes=note_payload["supersedes"],
                    created_at=_require_cache_datetime(note_payload["created_at"]),
                    updated_at=_require_cache_datetime(note_payload["updated_at"]),
                    link_count=int(note_payload["link_count"]),
                    decay_deadline=_parse_cache_datetime(note_payload["decay_deadline"]),
                )
                cached_index.register(note, path)
        except (KeyError, TypeError, ValueError, VaultError):
            return False

        self._index = cached_index
        return True

    def _newest_note_mtime(self) -> datetime:
        newest = datetime.fromtimestamp(0, tz=timezone.utc)
        for tier in sorted(_VALID_TIERS):
            for path in (self.vault_path / f"tier{tier}").glob("*.md"):
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                newest = max(newest, mtime)
        return newest

    def _note_relative_paths(self) -> set[str]:
        paths: set[str] = set()
        for tier in sorted(_VALID_TIERS):
            for path in (self.vault_path / f"tier{tier}").glob("*.md"):
                paths.add(str(path.relative_to(self.vault_path)))
        return paths

    def _note_path_from_index(self, note_id: str) -> Path:
        entry = self._index.entries.get(note_id)
        if entry is None:
            raise NoteNotFoundError(f"note not found: {note_id}")
        return entry.path

    def _expire_note(self, note_id: str) -> None:
        path = self._note_path_from_index(note_id)
        path.unlink()
        delete_embedding(self.embedding_path, note_id)
        del self._index.entries[note_id]
        self._index.rebuild_inbound()

    def _load_note(self, note_id: str) -> MemoryNote:
        path = self._note_path_from_index(note_id)
        note = parse_note(path.read_text(encoding="utf-8"))
        note.embedding = self._load_embedding(note_id)
        return self._with_computed_link_count(note)

    def _with_computed_link_count(self, note: MemoryNote) -> MemoryNote:
        note.link_count = self._index.inbound_count(note.note_id) + len(note.links)
        return note

    def _save_embedding(self, note_id: str, embedding: ndarray | None) -> None:
        if self.embedding_path is not None and embedding is not None:
            save_embedding(self.embedding_path, note_id, embedding)

    def _load_embedding(self, note_id: str) -> ndarray | None:
        if self.embedding_path is None:
            return None
        return load_embedding(self.embedding_path, note_id)


def _validate_tier(tier: int) -> None:
    if tier not in _VALID_TIERS:
        raise InvalidTierError(f"tier must be one of 1, 2, or 3: {tier}")


def _validate_title(title: str) -> None:
    if len(title) > _MAX_TITLE_LENGTH:
        raise TitleTooLongError("title must be 150 characters or fewer")


def _validate_score(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise InvalidScoreError(f"{field_name} must be between 0.0 and 1.0")


def _parse_cache_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _require_cache_datetime(value: object) -> datetime:
    parsed = _parse_cache_datetime(value)
    if parsed is None:
        raise ValueError("cache datetime is missing or invalid")
    return parsed
