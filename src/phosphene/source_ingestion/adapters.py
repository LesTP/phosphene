"""Internal adapter protocol and registry for Source Ingestion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from phosphene.source_ingestion.types import AdapterConfig, ContentItem

LastSeenMarker = str | int | float | datetime | None


@dataclass
class AdapterItemError:
    """Adapter-local item failure, converted to public IngestionError by the manager."""

    error: str
    url: str | None = None


@dataclass
class AdapterPollResult:
    """Internal adapter poll result with an optional next last-seen marker."""

    items: list[ContentItem] = field(default_factory=list)
    errors: list[AdapterItemError] = field(default_factory=list)
    next_marker: LastSeenMarker = None


class SourceAdapter(Protocol):
    """Internal interface implemented by concrete source adapters."""

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        """Fetch content newer than last_seen_marker."""


AdapterFactory = Callable[[AdapterConfig], SourceAdapter]


class PendingAdapter:
    """Placeholder for ARCH adapter types whose fetching is implemented later."""

    def __init__(self, adapter_type: str) -> None:
        self.adapter_type = adapter_type

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        raise NotImplementedError(f"{self.adapter_type} adapter is not implemented")


def pending_adapter_factory(adapter_type: str) -> AdapterFactory:
    def _factory(config: AdapterConfig) -> SourceAdapter:
        return PendingAdapter(config.adapter_type)

    return _factory
