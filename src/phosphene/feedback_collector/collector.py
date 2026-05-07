"""Feedback Collector public constructor and ARCH method shell."""

from __future__ import annotations

from phosphene.feedback_collector.types import (
    FeedbackCollectorConfig,
    FeedbackEvent,
    OutputRecord,
)


class FeedbackCollector:
    """Track delivered outputs and normalize feedback into Memory Store events."""

    def __init__(
        self,
        memory_store,
        config: FeedbackCollectorConfig | None = None,
    ) -> None:
        self.memory_store = memory_store
        self.config = config or FeedbackCollectorConfig()
        self.output_records: dict[str, OutputRecord] = {}

    def register_output(self, output, delivery) -> None:
        return None

    def process_signal(self, signal) -> FeedbackEvent | None:
        return None

    def check_silence(self) -> list[FeedbackEvent]:
        return []

    def check_delayed_engagement(self) -> list[FeedbackEvent]:
        return []

    def update_unresolvedness_on_feedback(self, event: FeedbackEvent) -> None:
        return None
