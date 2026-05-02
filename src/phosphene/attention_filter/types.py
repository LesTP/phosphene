"""Dataclasses for the Attention Filter public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from numpy import ndarray

from phosphene.attention_filter.errors import InvalidScoreError
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


PRECISION_SURPLUS_DESCRIPTION = (
    "Score the ratio of precise claim to vague gesture in this text. "
    "High score: claims are specific, evidence is tight, the text could not "
    "have been written without knowing something. Low score: claims are general, "
    "evidence is gestures toward evidence."
)


def default_prompt_criteria(precision_surplus_weight: float = 1.0) -> list[FilterCriterion]:
    return [
        FilterCriterion(
            name="precision_surplus",
            description=PRECISION_SURPLUS_DESCRIPTION,
            weight=precision_surplus_weight,
        )
    ]


def _require_non_negative(value: float, field_name: str) -> None:
    if value < 0.0:
        raise InvalidScoreError(f"{field_name} must be non-negative")


def _require_probability(value: float, field_name: str) -> None:
    if value < 0.0 or value > 1.0:
        raise InvalidScoreError(f"{field_name} must be in [0.0, 1.0]")


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

    def __post_init__(self) -> None:
        for field_name in (
            "precision_surplus_weight",
            "liminality_weight",
            "friction_weight",
            "unexpected_connection_weight",
            "structural_insight_weight",
            "link_density_weight",
            "cluster_novelty_weight",
            "unresolvedness_affinity_weight",
        ):
            _require_non_negative(getattr(self, field_name), field_name)

        _require_probability(self.phase2_max_weight, "phase2_max_weight")

        if self.note_count_threshold <= 0:
            raise InvalidScoreError("note_count_threshold must be positive")
        if self.cluster_count_threshold <= 0:
            raise InvalidScoreError("cluster_count_threshold must be positive")


@dataclass(kw_only=True)
class AttentionFilterConfig:
    prompt_criteria: list[FilterCriterion] = field(default_factory=default_prompt_criteria)
    llm_config: LLMConfig
    embedding_config: EmbeddingConfig
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    acceptance_threshold: float = 0.3
    auto_accept_sources: list[str] = field(default_factory=list)
    density_crossover: float = 3.0
    similarity_candidates: int = 20
    llm_tier: ModelTier = ModelTier.DEFAULT
    assertion_extraction_tier: ModelTier = ModelTier.COMMODITY

    def __post_init__(self) -> None:
        _require_probability(self.acceptance_threshold, "acceptance_threshold")

        if self.density_crossover <= 0.0:
            raise InvalidScoreError("density_crossover must be positive")


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
