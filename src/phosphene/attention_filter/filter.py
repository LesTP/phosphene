"""Attention Filter entry point."""

from __future__ import annotations

from phosphene.memory_store import DensityMetrics

from phosphene.attention_filter.types import AttentionFilterConfig, ContentItem, FilterResult


def phase2_is_active(metrics: DensityMetrics, config: AttentionFilterConfig) -> bool:
    """Return whether memory density has crossed the Phase 2 triple gate."""

    density_activation_threshold = config.density_crossover * 0.5
    return (
        metrics.note_count >= config.scoring.note_count_threshold
        and metrics.cluster_count >= config.scoring.cluster_count_threshold
        and metrics.mean_link_degree >= density_activation_threshold
    )


def compute_blend_weights(
    metrics: DensityMetrics, config: AttentionFilterConfig
) -> tuple[float, float]:
    """Compute prompt and structure weights from current memory density."""

    if not phase2_is_active(metrics, config):
        return 1.0, 0.0

    ramp_start = config.density_crossover * 0.5
    ramp_end = config.density_crossover * 2.0
    ramp_progress = (metrics.mean_link_degree - ramp_start) / (ramp_end - ramp_start)
    capped_progress = min(max(ramp_progress, 0.0), 1.0)
    structure_weight = capped_progress * config.scoring.phase2_max_weight
    prompt_weight = 1.0 - structure_weight
    return prompt_weight, structure_weight


class AttentionFilter:
    """Personality-driven content selector.

    Full scoring and annotation behavior is implemented in later Attention
    Filter phases; this scaffold establishes the ARCH-defined constructor.
    """

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def filter_content(
        self, items: list[ContentItem], config: AttentionFilterConfig
    ) -> FilterResult:
        raise NotImplementedError("AttentionFilter.filter_content is implemented in a later phase")
