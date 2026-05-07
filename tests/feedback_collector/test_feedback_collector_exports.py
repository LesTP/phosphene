from dataclasses import fields
from datetime import datetime, timedelta

import pytest

import phosphene.feedback_collector as feedback_collector
from phosphene.feedback_collector import (
    FeedbackCollector,
    FeedbackCollectorConfig,
    FeedbackEvent,
    OutputRecord,
)


def test_package_exports_arch_public_api() -> None:
    expected_exports = {
        "FeedbackCollector",
        "FeedbackCollectorConfig",
        "FeedbackEvent",
        "OutputRecord",
    }

    assert set(feedback_collector.__all__) == expected_exports
    for exported_name in expected_exports:
        assert getattr(feedback_collector, exported_name) is not None


def test_arch_dataclass_field_names_match_contract() -> None:
    assert [field.name for field in fields(FeedbackEvent)] == [
        "output_message_id",
        "output_intent_tag",
        "output_mode",
        "signal_type",
        "signal_value",
        "source_note_ids",
        "retention_criteria",
        "timestamp",
    ]
    assert [field.name for field in fields(FeedbackCollectorConfig)] == [
        "silence_window",
        "delayed_recheck_window",
        "positive_reactions",
        "negative_reactions",
        "reply_is_positive",
        "forward_is_positive",
    ]
    assert [field.name for field in fields(OutputRecord)] == [
        "message_id",
        "intent_tag",
        "output_mode",
        "source_note_ids",
        "retention_criteria",
        "delivered_at",
        "feedback_events",
        "silence_recorded",
    ]


def test_arch_dataclasses_construct_with_expected_defaults() -> None:
    event = FeedbackEvent(
        output_message_id="msg-1",
        output_intent_tag="synthesis",
        output_mode="prompted",
        signal_type="like",
    )
    config = FeedbackCollectorConfig()
    delivered_at = datetime(2026, 5, 7)
    record = OutputRecord(
        message_id="msg-1",
        intent_tag="synthesis",
        output_mode="prompted",
        source_note_ids=["note-1"],
        retention_criteria=["friction"],
        delivered_at=delivered_at,
    )
    collector = FeedbackCollector(memory_store=object())

    assert event.signal_value is None
    assert event.source_note_ids == []
    assert event.retention_criteria == []
    assert isinstance(event.timestamp, datetime)
    assert config.silence_window == timedelta(hours=24)
    assert config.delayed_recheck_window == timedelta(days=7)
    assert config.positive_reactions == ["👍", "❤️", "🔥", "💡", "🤔"]
    assert config.negative_reactions == ["👎"]
    assert config.reply_is_positive is True
    assert config.forward_is_positive is True
    assert record.feedback_events == []
    assert record.silence_recorded is False
    assert collector.memory_store is not None
    assert collector.config == FeedbackCollectorConfig()
    assert collector.output_records == {}
    assert callable(collector.register_output)
    assert callable(collector.process_signal)
    assert callable(collector.check_silence)
    assert callable(collector.check_delayed_engagement)
    assert callable(collector.update_unresolvedness_on_feedback)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("silence_window", timedelta(0), "silence_window must be positive"),
        (
            "delayed_recheck_window",
            timedelta(seconds=-1),
            "delayed_recheck_window must be positive",
        ),
        ("positive_reactions", [], "positive_reactions must not be empty"),
        (
            "negative_reactions",
            ["👎", ""],
            "negative_reactions must contain non-empty strings",
        ),
        ("reply_is_positive", "yes", "reply_is_positive must be a bool"),
        ("forward_is_positive", 1, "forward_is_positive must be a bool"),
    ],
)
def test_config_validates_arch_runtime_settings(
    field_name: str,
    value: object,
    message: str,
) -> None:
    kwargs = {field_name: value}

    with pytest.raises(ValueError, match=message):
        FeedbackCollectorConfig(**kwargs)
