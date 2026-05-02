"""Public Attention Filter API surface."""

from phosphene.attention_filter.errors import AttentionFilterError, InvalidScoreError
from phosphene.attention_filter.filter import (
    AttentionFilter,
    compute_phase2_composite,
    compute_blend_weights,
    phase2_is_active,
    score_cluster_novelty,
    score_friction,
    score_liminality,
    score_link_density,
    score_structural_insight,
    score_unexpected_connection,
    score_unresolvedness_affinity,
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
    "compute_phase2_composite",
    "compute_blend_weights",
    "default_prompt_criteria",
    "phase2_is_active",
    "score_cluster_novelty",
    "score_friction",
    "score_liminality",
    "score_link_density",
    "score_structural_insight",
    "score_unexpected_connection",
    "score_unresolvedness_affinity",
]
