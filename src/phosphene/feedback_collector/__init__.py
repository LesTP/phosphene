"""Public Feedback Collector API surface."""

from phosphene.feedback_collector.collector import FeedbackCollector
from phosphene.feedback_collector.types import (
    FeedbackCollectorConfig,
    FeedbackEvent,
    OutputRecord,
)

__all__ = [
    "FeedbackCollector",
    "FeedbackCollectorConfig",
    "FeedbackEvent",
    "OutputRecord",
]
