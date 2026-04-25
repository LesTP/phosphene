"""Vault-backed Memory Store implementation."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from phosphene.memory_store.errors import (
    InvalidScoreError,
    InvalidTierError,
    NoteNotFoundError,
    TitleTooLongError,
    VaultError,
)
from phosphene.memory_store.types import MemoryNote, MemoryStoreConfig, NoteInput, NotePatch
from phosphene.memory_store.vault import generate_note_id, note_path, parse_note, serialize_note

_VALID_TIERS = {1, 2, 3}
_MAX_TITLE_LENGTH = 150


class MemoryStore:
    """Store Memory Store notes in a tiered markdown vault."""

    def __init__(self, config: MemoryStoreConfig):
        self.config = config
        self.vault_path = Path(config.vault_path)
        self.embedding_path = Path(config.embedding_path) if config.embedding_path else None

        self._ensure_vault()

    def store_note(self, note: NoteInput) -> str:
        """Persist a note and return its generated note id."""
        _validate_tier(note.tier)
        _validate_title(note.title)
        _validate_score("importance", note.importance)
        _validate_score("unresolvedness", note.unresolvedness)

        created_at = datetime.now(timezone.utc)
        note_id = generate_note_id(note.title, created_at)
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
        )

        path = note_path(self.vault_path, note.tier, note_id)
        path.write_text(serialize_note(memory_note), encoding="utf-8")
        return note_id

    def get_note(self, note_id: str) -> MemoryNote:
        """Load a note by id from any tier."""
        path = self._find_note_path(note_id)
        return parse_note(path.read_text(encoding="utf-8"))

    def update_note(self, note_id: str, patch: NotePatch) -> MemoryNote:
        """Apply a partial update to a note and return the updated note."""
        path = self._find_note_path(note_id)
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

        path.write_text(serialize_note(note), encoding="utf-8")
        return note

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

    def _find_note_path(self, note_id: str) -> Path:
        for tier in sorted(_VALID_TIERS):
            path = note_path(self.vault_path, tier, note_id)
            if path.exists():
                return path
        raise NoteNotFoundError(f"note not found: {note_id}")


def _validate_tier(tier: int) -> None:
    if tier not in _VALID_TIERS:
        raise InvalidTierError(f"tier must be one of 1, 2, or 3: {tier}")


def _validate_title(title: str) -> None:
    if len(title) > _MAX_TITLE_LENGTH:
        raise TitleTooLongError("title must be 150 characters or fewer")


def _validate_score(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise InvalidScoreError(f"{field_name} must be between 0.0 and 1.0")
