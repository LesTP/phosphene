"""Vault file helpers for Memory Store notes."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from phosphene.memory_store.types import MemoryNote

_ID_SLUG_MAX_LENGTH = 60


def generate_note_id(title: str, created_at: datetime) -> str:
    """Generate a deterministic note id from title and creation time."""
    slug = _slugify(title)
    timestamp = created_at.strftime("%Y%m%d%H%M%S")
    hash_input = f"{title}\0{created_at.isoformat()}".encode("utf-8")
    suffix = hashlib.sha1(hash_input).hexdigest()[:4]
    return f"{slug}-{timestamp}-{suffix}"


def note_path(vault_path: Path, tier: int, note_id: str) -> Path:
    """Return the markdown path for a note in the tiered vault layout."""
    return vault_path / f"tier{tier}" / f"{note_id}.md"


def serialize_note(note: MemoryNote) -> str:
    """Serialize a note to Obsidian-compatible markdown with YAML frontmatter."""
    metadata = {
        "note_id": note.note_id,
        "tier": note.tier,
        "title": note.title,
        "importance": note.importance,
        "unresolvedness": note.unresolvedness,
        "links": note.links,
        "tags": note.tags,
        "source": note.source,
        "friction_target": note.friction_target,
        "attractor_relevance": note.attractor_relevance,
        "cluster_group": note.cluster_group,
        "supersedes": note.supersedes,
        "change_summary": note.change_summary,
        "created_at": _format_datetime(note.created_at),
        "updated_at": _format_datetime(note.updated_at),
        "link_count": note.link_count,
        "decay_deadline": _format_datetime(note.decay_deadline),
    }
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{frontmatter}---\n{note.content}"


def parse_note(text: str) -> MemoryNote:
    """Parse a note serialized by ``serialize_note``."""
    if not text.startswith("---\n"):
        raise ValueError("note text must start with YAML frontmatter")

    try:
        frontmatter, content = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("note text is missing frontmatter separator") from exc

    metadata = yaml.safe_load(frontmatter) or {}
    return MemoryNote(
        note_id=metadata["note_id"],
        tier=metadata["tier"],
        content=content,
        title=metadata["title"],
        importance=metadata["importance"],
        unresolvedness=metadata["unresolvedness"],
        links=list(metadata.get("links") or []),
        tags=list(metadata.get("tags") or []),
        source=metadata.get("source"),
        friction_target=metadata.get("friction_target"),
        embedding=None,
        attractor_relevance=metadata.get("attractor_relevance"),
        cluster_group=metadata.get("cluster_group"),
        supersedes=metadata.get("supersedes"),
        created_at=_parse_datetime(metadata["created_at"]),
        updated_at=_parse_datetime(metadata["updated_at"]),
        link_count=metadata["link_count"],
        decay_deadline=_parse_datetime(metadata.get("decay_deadline")),
        change_summary=metadata.get("change_summary"),
    )


def _slugify(title: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", title.lower())
    slug = "-".join(words)[:_ID_SLUG_MAX_LENGTH].strip("-")
    return slug or "note"


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat(timespec="seconds")


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
