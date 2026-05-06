"""Public Distillation API surface."""

from phosphene.distillation.engine import DistillationEngine
from phosphene.distillation.errors import (
    DistillationConfigError,
    DistillationError,
    DistillationLockError,
    InsufficientDataError,
    NoPatternDataError,
)
from phosphene.distillation.types import (
    CriteriaAdjustment,
    DistillationConfig,
    EvolutionResult,
    GateStatus,
    ReflectionInsight,
    SupersessionRecord,
    TierPromotionResult,
)

__all__ = [
    "CriteriaAdjustment",
    "DistillationConfig",
    "DistillationConfigError",
    "DistillationEngine",
    "DistillationError",
    "DistillationLockError",
    "EvolutionResult",
    "GateStatus",
    "InsufficientDataError",
    "NoPatternDataError",
    "ReflectionInsight",
    "SupersessionRecord",
    "TierPromotionResult",
]
