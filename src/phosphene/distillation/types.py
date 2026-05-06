"""Dataclasses for the Distillation public API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Any

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
