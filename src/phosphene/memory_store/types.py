"""Dataclasses for the Memory Store public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from numpy import ndarray


@dataclass
class MemoryStoreConfig:
    vault_path: str
    embedding_path: str | None = None
    tier1_base_retention_days: int = 30
    tier1_extended_retention_days: int = 90
    tier3_superseded_retention_days: int = 90
    link_density_threshold: int = 2


@dataclass
class NoteInput:
    tier: int
    content: str
    title: str
    importance: float = 0.0
    unresolvedness: float = 0.0
    links: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    friction_target: str | None = None
    embedding: ndarray | None = None
    attractor_relevance: float | None = None
    cluster_group: str | None = None


@dataclass
class MemoryNote:
    note_id: str
    tier: int
    content: str
    title: str
    importance: float
    unresolvedness: float
    links: list[str]
    tags: list[str]
    source: str | None
    friction_target: str | None
    embedding: ndarray | None
    attractor_relevance: float | None
    cluster_group: str | None
    supersedes: str | None
    created_at: datetime
    updated_at: datetime
    link_count: int
    decay_deadline: datetime | None
    change_summary: str | None = None


@dataclass
class IndexEntry:
    note_id: str
    tier: int
    title: str
    importance: float
    unresolvedness: float
    link_count: int
    tags: list[str]
    created_at: datetime


@dataclass
class DensityMetrics:
    note_count: int
    tier_counts: dict[int, int]
    mean_link_degree: float
    cluster_count: int
    unresolved_count: int
    max_unresolvedness: float


@dataclass
class PersonalityContext:
    personality_files: list[MemoryNote]
    version_id: str


@dataclass
class NoteQuery:
    tier: int | None = None
    min_importance: float | None = None
    min_unresolvedness: float | None = None
    tags: list[str] | None = None
    source: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 50
    order_by: str = "created_at"
    descending: bool = True


@dataclass
class NotePatch:
    content: str | None = None
    title: str | None = None
    importance: float | None = None
    unresolvedness: float | None = None
    links: list[str] | None = None
    tags: list[str] | None = None
    embedding: ndarray | None = None
    attractor_relevance: float | None = None


@dataclass
class DecayReport:
    expired_count: int
    expired_ids: list[str]
    extended_count: int
    tier_breakdown: dict[int, int]
