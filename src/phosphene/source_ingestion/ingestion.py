"""Source Ingestion manager entry point."""

from __future__ import annotations

from phosphene.source_ingestion.types import IngestionConfig, IngestionResult


class SourceIngestion:
    """Constructor-compatible Source Ingestion manager stub."""

    def __init__(self, config: IngestionConfig) -> None:
        self.config = config

    def poll(self, adapter_label: str | None = None) -> list[IngestionResult]:
        raise NotImplementedError("SourceIngestion.poll is implemented in a later phase step")

    def poll_once(self, adapter_label: str) -> IngestionResult:
        raise NotImplementedError("SourceIngestion.poll_once is implemented in a later phase step")
