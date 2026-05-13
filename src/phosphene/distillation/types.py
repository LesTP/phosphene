"""Dataclasses for the Distillation public API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any

from phosphene.distillation.errors import DistillationConfigError

try:
    from toolkit.clustering import ClusterConfig
    from toolkit.embedding import EmbeddingConfig
    from toolkit.llm_client import LLMConfig, ModelTier
except ImportError:
    LLMConfig = Any
    EmbeddingConfig = Any
    ClusterConfig = Any

    class ModelTier(str, Enum):
        """Fallback model tiers for import-time compatibility without toolkit."""

        DEFAULT = "default"
        COMMODITY = "commodity"
        QUALITY = "quality"


def _require_present(value: object, field_name: str) -> None:
    if value is None:
        raise DistillationConfigError(f"{field_name} is required")


def _require_non_negative_timedelta(value: timedelta, field_name: str) -> None:
    if not isinstance(value, timedelta):
        raise DistillationConfigError(f"{field_name} must be a timedelta")
    if value < timedelta(0):
        raise DistillationConfigError(f"{field_name} must be non-negative")


def _require_positive_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DistillationConfigError(f"{field_name} must be an integer")
    if value <= 0:
        raise DistillationConfigError(f"{field_name} must be positive")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DistillationConfigError(f"{field_name} must be an integer")
    if value < 0:
        raise DistillationConfigError(f"{field_name} must be non-negative")


def _require_non_negative_float(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DistillationConfigError(f"{field_name} must be a number")
    if value < 0.0:
        raise DistillationConfigError(f"{field_name} must be non-negative")


def _require_probability(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DistillationConfigError(f"{field_name} must be a number")
    if value < 0.0 or value > 1.0:
        raise DistillationConfigError(f"{field_name} must be in [0.0, 1.0]")


@dataclass(kw_only=True)
class DistillationConfig:
    llm_config: LLMConfig
    llm_configs_rotation: list[LLMConfig] | None = None
    reflection_tier: ModelTier = ModelTier.QUALITY
    evolution_tier: ModelTier = ModelTier.QUALITY
    embedding_config: EmbeddingConfig
    clustering_config: ClusterConfig | None = None
    min_time_between_runs: timedelta = timedelta(hours=24)
    min_tier1_volume: int = 20
    t2_to_t3_cycle_days: int = 30
    inertia_per_cycle: float = 0.25
    max_inertia: float = 3.0
    max_compression_ratio: float = 0.5
    incorporate_feedback: bool = True
    min_cluster_coherence: float = 0.4
    cross_link_threshold: float = 0.45
    max_cross_links: int = 15

    def __post_init__(self) -> None:
        _require_present(self.llm_config, "llm_config")
        _require_present(self.embedding_config, "embedding_config")

        for index, llm_config in enumerate(self.llm_configs_rotation or []):
            _require_present(llm_config, f"llm_configs_rotation[{index}]")

        _require_non_negative_timedelta(
            self.min_time_between_runs,
            "min_time_between_runs",
        )
        _require_positive_int(self.min_tier1_volume, "min_tier1_volume")
        _require_positive_int(self.t2_to_t3_cycle_days, "t2_to_t3_cycle_days")
        _require_non_negative_float(self.inertia_per_cycle, "inertia_per_cycle")
        _require_non_negative_float(self.max_inertia, "max_inertia")
        if self.max_inertia < 1.0:
            raise DistillationConfigError("max_inertia must be at least 1.0")
        _require_probability(self.max_compression_ratio, "max_compression_ratio")
        _require_probability(self.min_cluster_coherence, "min_cluster_coherence")
        _require_probability(self.cross_link_threshold, "cross_link_threshold")
        _require_non_negative_int(self.max_cross_links, "max_cross_links")


@dataclass
class GateStatus:
    ready: bool
    time_gate: bool
    volume_gate: bool
    lock_gate: bool
    t1_to_t2_ready: bool
    t2_to_t3_ready: bool
    time_since_last_run: timedelta | None
    tier1_pending: int
    days_since_last_t3: int | None


@dataclass
class TierPromotionResult:
    new_cluster_ids: list[str]
    updated_cluster_ids: list[str]
    promoted_count: int
    noise_count: int
    incoherent_cluster_count: int
    cluster_tree_depth: int
    feedback_processed: int
    assertion_cache_updated: list[str]


@dataclass
class ReflectionInsight:
    content: str
    source_pattern_ids: list[str]
    insight_type: str
    confidence: float


@dataclass
class SupersessionRecord:
    old_note_id: str
    new_note_id: str
    change_summary: str


@dataclass
class CriteriaAdjustment:
    criterion_name: str
    old_weight: float
    new_weight: float
    evidence: str


@dataclass
class EvolutionResult:
    insights: list[ReflectionInsight]
    superseded: list[SupersessionRecord]
    unchanged_ids: list[str]
    criteria_adjustments: list[CriteriaAdjustment]
    compression_ratio: float
