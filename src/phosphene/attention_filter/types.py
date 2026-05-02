"""Dataclasses for the Attention Filter public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from numpy import ndarray

from phosphene.memory_store import DensityMetrics

try:
    from toolkit.embedding import EmbeddingConfig
    from toolkit.llm_client import LLMConfig, ModelTier
except ImportError:
    LLMConfig = Any
    EmbeddingConfig = Any

    class ModelTier(str, Enum):
        """Fallback model tiers for import-time compatibility without toolkit."""

        DEFAULT = "default"
        COMMODITY = "commodity"


@dataclass
class ContentItem:
    content: str
    source: str
    timestamp: datetime
    url: str | None = None
    linked_urls: list[str] = field(default_factory=list)


@dataclass
class FilterCriterion:
    name: str
    description: str
    weight: float = 1.0


@dataclass
class ScoringConfig:
    precision_surplus_weight: float = 1.0
    liminality_weight: float = 1.0
    friction_weight: float = 1.0
    unexpected_connection_weight: float = 1.0
    structural_insight_weight: float = 1.0
    link_density_weight: float = 1.0
    cluster_novelty_weight: float = 1.0
    unresolvedness_affinity_weight: float = 1.0
    link_density_sim_threshold: float = 0.4
    gap_factor_exponent: float = 2.0
    assertion_alignment_threshold: float = 0.5
    note_count_threshold: int = 50
    cluster_count_threshold: int = 3
    phase2_max_weight: float = 0.7


@dataclass(kw_only=True)
class AttentionFilterConfig:
    prompt_criteria: list[FilterCriterion]
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    acceptance_threshold: float = 0.3
    auto_accept_sources: list[str] = field(default_factory=list)
    density_crossover: float = 3.0
    similarity_candidates: int = 20
    llm_tier: ModelTier = ModelTier.DEFAULT
    assertion_extraction_tier: ModelTier = ModelTier.COMMODITY


@dataclass
class AnnotatedFragment:
    content: str
    annotation: str
    importance_score: float
    unresolvedness: float
    retention_criteria: list[str]
    prompt_score: float
    structure_score: float
    friction_target: str | None
    connections: list[str]
    source: str
    timestamp: datetime
    url: str | None
    linked_urls: list[str]
    embedding: ndarray


@dataclass
class FilterResult:
    accepted: list[AnnotatedFragment]
    rejected_count: int
    total_count: int
    prompt_weight: float
    structure_weight: float
    density_snapshot: DensityMetrics
