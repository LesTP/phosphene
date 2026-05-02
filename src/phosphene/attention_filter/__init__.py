"""Public Attention Filter API surface."""

from phosphene.attention_filter.errors import AttentionFilterError, InvalidScoreError
from phosphene.attention_filter.filter import AttentionFilter
from phosphene.attention_filter.types import (
    AnnotatedFragment,
    AttentionFilterConfig,
    ContentItem,
    FilterCriterion,
    FilterResult,
    ScoringConfig,
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
]
