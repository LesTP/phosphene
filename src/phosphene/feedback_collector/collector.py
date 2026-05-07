"""Feedback Collector public constructor and ARCH method shell."""

from __future__ import annotations

from datetime import datetime

from phosphene.feedback_collector.types import (
    FeedbackCollectorConfig,
    FeedbackEvent,
    OutputRecord,
)

_RETENTION_CRITERIA_TAGS = {
    "precision_surplus",
    "liminality",
    "friction",
    "unexpected_connection",
    "structural_insight",
    "link_density",
    "cluster_novelty",
    "unresolvedness_affinity",
    "wild_card",
}


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
        if not delivery.success or delivery.message_id is None:
            return None

        source_note_ids = list(output.source_note_ids)
        self.output_records[delivery.message_id] = OutputRecord(
            message_id=delivery.message_id,
            intent_tag=output.intent_tag,
            output_mode=output.output_mode,
            source_note_ids=source_note_ids,
            retention_criteria=self._retention_criteria_for_source_notes(
                source_note_ids
            ),
            delivered_at=datetime.now(),
        )
        return None

    def _retention_criteria_for_source_notes(
        self, source_note_ids: list[str]
    ) -> list[str]:
        criteria: list[str] = []
        seen: set[str] = set()
        for note_id in source_note_ids:
            try:
                note = self.memory_store.get_note(note_id)
            except Exception:
                continue
            for tag in getattr(note, "tags", []):
                if tag not in _RETENTION_CRITERIA_TAGS or tag in seen:
                    continue
                seen.add(tag)
                criteria.append(tag)
        return criteria

    def process_signal(self, signal) -> FeedbackEvent | None:
        return None

    def check_silence(self) -> list[FeedbackEvent]:
        return []

    def check_delayed_engagement(self) -> list[FeedbackEvent]:
        return []

    def update_unresolvedness_on_feedback(self, event: FeedbackEvent) -> None:
        return None
