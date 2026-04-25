"""Vault-backed Memory Store implementation."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from phosphene.memory_store.errors import (
    InvalidScoreError,
    InvalidTierError,
    TitleTooLongError,
    VaultError,
)
from phosphene.memory_store.types import MemoryNote, MemoryStoreConfig, NoteInput
from phosphene.memory_store.vault import generate_note_id, note_path, serialize_note

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


def _validate_tier(tier: int) -> None:
    if tier not in _VALID_TIERS:
        raise InvalidTierError(f"tier must be one of 1, 2, or 3: {tier}")


def _validate_title(title: str) -> None:
    if len(title) > _MAX_TITLE_LENGTH:
        raise TitleTooLongError("title must be 150 characters or fewer")


def _validate_score(field_name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise InvalidScoreError(f"{field_name} must be between 0.0 and 1.0")
