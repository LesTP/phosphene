"""Dataclasses for the Feedback Collector public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


def _require_positive_timedelta(value: timedelta, field_name: str) -> None:
    if not isinstance(value, timedelta):
        raise ValueError(f"{field_name} must be a timedelta")
    if value <= timedelta(0):
        raise ValueError(f"{field_name} must be positive")


def _require_string_list(value: list[str], field_name: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not value:
        raise ValueError(f"{field_name} must not be empty")
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{field_name} must contain non-empty strings")


@dataclass
class FeedbackEvent:
    output_message_id: str
    output_intent_tag: str
    output_mode: str
    signal_type: str
    signal_value: str | None = None
    source_note_ids: list[str] = field(default_factory=list)
    retention_criteria: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class FeedbackCollectorConfig:
    silence_window: timedelta = timedelta(hours=24)
    delayed_recheck_window: timedelta = timedelta(days=7)
    positive_reactions: list[str] = field(
        default_factory=lambda: ["👍", "❤️", "🔥", "💡", "🤔"]
    )
    negative_reactions: list[str] = field(default_factory=lambda: ["👎"])
    reply_is_positive: bool = True
    forward_is_positive: bool = True

    def __post_init__(self) -> None:
        _require_positive_timedelta(self.silence_window, "silence_window")
        _require_positive_timedelta(
            self.delayed_recheck_window,
            "delayed_recheck_window",
        )
        _require_string_list(self.positive_reactions, "positive_reactions")
        _require_string_list(self.negative_reactions, "negative_reactions")
        if not isinstance(self.reply_is_positive, bool):
            raise ValueError("reply_is_positive must be a bool")
        if not isinstance(self.forward_is_positive, bool):
            raise ValueError("forward_is_positive must be a bool")


@dataclass
class OutputRecord:
    message_id: str
    intent_tag: str
    output_mode: str
    source_note_ids: list[str]
    retention_criteria: list[str]
    delivered_at: datetime
    feedback_events: list[FeedbackEvent] = field(default_factory=list)
    silence_recorded: bool = False
