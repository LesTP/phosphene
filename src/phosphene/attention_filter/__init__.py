"""Public Attention Filter API surface."""

from phosphene.attention_filter.errors import AttentionFilterError, InvalidScoreError
from phosphene.attention_filter.filter import (
    AttentionFilter,
    compute_blend_weights,
    phase2_is_active,
)
from phosphene.attention_filter.types import (
    AnnotatedFragment,
    AttentionFilterConfig,
    ContentItem,
    FilterCriterion,
    FilterResult,
    ScoringConfig,
    default_prompt_criteria,
)

__all__ = [
    "AnnotatedFragment",
    "AttentionFilter",
    "AttentionFilterConfig",
    "AttentionFilterError",
    "ContentItem",
    "FilterCriterion",
    "FilterResult",
    "InvalidScoreError",
    "ScoringConfig",
    "compute_blend_weights",
    "default_prompt_criteria",
    "phase2_is_active",
]
