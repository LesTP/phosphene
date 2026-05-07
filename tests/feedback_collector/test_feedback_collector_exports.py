from dataclasses import fields
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from phosphene.gateway import DeliveryResult
from phosphene.gateway import FeedbackSignal
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


class FakeMemoryStore:
    def __init__(self, notes: dict[str, object]) -> None:
        self.notes = notes
        self.stored_notes: list[object] = []

    def get_note(self, note_id: str) -> object:
        return self.notes[note_id]

    def store_note(self, note: object) -> str:
        self.stored_notes.append(note)
        return f"feedback-{len(self.stored_notes)}"


def test_register_output_tracks_successful_delivery_metadata() -> None:
    store = FakeMemoryStore(
        {
            "note-1": SimpleNamespace(
                tags=["source", "precision_surplus", "friction"]
            ),
            "note-2": SimpleNamespace(
                tags=["friction", "unresolvedness_affinity", "other"]
            ),
        }
    )
    collector = FeedbackCollector(memory_store=store)
    output = SimpleNamespace(
        intent_tag="synthesis",
        output_mode="prompted",
        source_note_ids=["note-1", "note-2"],
    )
    delivery = DeliveryResult(
        success=True,
        platform="telegram",
        message_id="msg-1",
    )

    collector.register_output(output, delivery)

    record = collector.output_records["msg-1"]
    assert record.message_id == "msg-1"
    assert record.intent_tag == "synthesis"
    assert record.output_mode == "prompted"
    assert record.source_note_ids == ["note-1", "note-2"]
    assert record.retention_criteria == [
        "precision_surplus",
        "friction",
        "unresolvedness_affinity",
    ]
    assert isinstance(record.delivered_at, datetime)
    assert record.feedback_events == []
    assert record.silence_recorded is False


@pytest.mark.parametrize(
    "delivery",
    [
        DeliveryResult(success=False, platform="telegram", message_id="msg-1"),
        DeliveryResult(success=True, platform="telegram", message_id=None),
    ],
)
def test_register_output_ignores_failed_or_unaddressable_deliveries(
    delivery: DeliveryResult,
) -> None:
    collector = FeedbackCollector(memory_store=FakeMemoryStore({}))
    output = SimpleNamespace(
        intent_tag="synthesis",
        output_mode="prompted",
        source_note_ids=["note-1"],
    )

    collector.register_output(output, delivery)

    assert collector.output_records == {}


def test_register_output_keeps_tracking_state_in_memory_only() -> None:
    store = FakeMemoryStore({"note-1": SimpleNamespace(tags=["precision_surplus"])})
    collector = FeedbackCollector(memory_store=store)
    output = SimpleNamespace(
        intent_tag="synthesis",
        output_mode="prompted",
        source_note_ids=["note-1"],
    )
    delivery = DeliveryResult(success=True, platform="telegram", message_id="msg-1")

    collector.register_output(output, delivery)

    assert collector.output_records["msg-1"].retention_criteria == [
        "precision_surplus"
    ]
    assert store.stored_notes == []


def _registered_collector() -> tuple[FeedbackCollector, FakeMemoryStore]:
    store = FakeMemoryStore(
        {
            "note-1": SimpleNamespace(tags=["precision_surplus"]),
            "note-2": SimpleNamespace(tags=["friction", "other"]),
        }
    )
    collector = FeedbackCollector(memory_store=store)
    output = SimpleNamespace(
        intent_tag="synthesis",
        output_mode="prompted",
        source_note_ids=["note-1", "note-2"],
    )
    delivery = DeliveryResult(success=True, platform="telegram", message_id="msg-1")
    collector.register_output(output, delivery)
    return collector, store


def _feedback_signal(
    *,
    message_id: str = "msg-1",
    signal_type: str = "reaction",
    value: str | None = "👍",
) -> FeedbackSignal:
    return FeedbackSignal(
        platform="telegram",
        message_id=message_id,
        signal_type=signal_type,
        value=value,
        sender="human",
        timestamp=datetime(2026, 5, 7, 12, 0),
    )


def test_process_signal_stores_positive_reaction_feedback_note() -> None:
    collector, store = _registered_collector()

    event = collector.process_signal(_feedback_signal(value="💡"))

    assert event == collector.output_records["msg-1"].feedback_events[0]
    assert event is not None
    assert event.output_message_id == "msg-1"
    assert event.output_intent_tag == "synthesis"
    assert event.output_mode == "prompted"
    assert event.signal_type == "like"
    assert event.signal_value == "💡"
    assert event.source_note_ids == ["note-1", "note-2"]
    assert event.retention_criteria == ["precision_surplus", "friction"]
    assert event.timestamp == datetime(2026, 5, 7, 12, 0)

    stored = store.stored_notes[0]
    assert stored.tier == 1
    assert stored.content == "Feedback: like on [synthesis] output"
    assert stored.title == "Feedback: like on synthesis"
    assert stored.importance == 0.7
    assert stored.tags == ["feedback", "like", "synthesis", "precision_surplus", "friction"]
    assert stored.source == "feedback"
    assert stored.links == ["note-1", "note-2"]


@pytest.mark.parametrize(
    ("signal", "expected_type", "expected_importance"),
    [
        (_feedback_signal(value="👎"), "dislike", 0.8),
        (_feedback_signal(signal_type="reply", value="tell me more"), "reply", 0.7),
        (_feedback_signal(signal_type="forward", value=None), "forward", 0.9),
    ],
)
def test_process_signal_classifies_supported_feedback_signals(
    signal: FeedbackSignal,
    expected_type: str,
    expected_importance: float,
) -> None:
    collector, store = _registered_collector()

    event = collector.process_signal(signal)

    assert event is not None
    assert event.signal_type == expected_type
    assert store.stored_notes[0].importance == expected_importance


@pytest.mark.parametrize(
    "signal",
    [
        _feedback_signal(message_id="missing", value="👍"),
        _feedback_signal(value="❓"),
        _feedback_signal(signal_type="edit", value="changed"),
    ],
)
def test_process_signal_ignores_unknown_or_untracked_signals(
    signal: FeedbackSignal,
) -> None:
    collector, store = _registered_collector()

    event = collector.process_signal(signal)

    assert event is None
    assert collector.output_records["msg-1"].feedback_events == []
    assert store.stored_notes == []
