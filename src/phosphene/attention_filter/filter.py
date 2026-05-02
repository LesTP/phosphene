"""Attention Filter entry point."""

from __future__ import annotations

from phosphene.attention_filter.types import AttentionFilterConfig, ContentItem, FilterResult


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
