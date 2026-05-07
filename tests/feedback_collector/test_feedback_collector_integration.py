from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pytest

from phosphene.feedback_collector import FeedbackCollector
from phosphene.gateway import DeliveryResult, FeedbackSignal, OutboundMessage
from phosphene.generator import GeneratorOutput, RouterConfig, route
from phosphene.generator.types import TokenUsage
from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NoteQuery


@dataclass
class FakeGatewayConfig:
    default_platform: str = "telegram"


@dataclass
class FakeGateway:
    config: FakeGatewayConfig = field(default_factory=FakeGatewayConfig)

    def __post_init__(self) -> None:
        self.sent_messages: list[OutboundMessage] = []

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent_messages.append(message)
        return DeliveryResult(
            success=True,
            platform=message.platform,
            message_id=f"{message.platform}-{len(self.sent_messages)}",
        )


def _memory_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def test_feedback_collector_round_trips_gateway_generator_and_memory_store(
    tmp_path: Path,
) -> None:
    store = _memory_store(tmp_path)
    source_note_id = store.store_note(
        NoteInput(
            tier=1,
            content="A note that contributed to an output.",
            title="Source Note",
            importance=0.4,
            unresolvedness=0.35,
            tags=["precision_surplus", "friction", "not-a-criterion"],
            source="ingestion",
        )
    )
    output = GeneratorOutput(
        content="A generated synthesis.",
        intent_tag="synthesis",
        output_mode="prompted",
        importance_score=0.6,
        is_lateral=False,
        source_note_ids=[source_note_id],
        contradictions_noted=[],
        token_usage=TokenUsage(),
    )
    gateway = FakeGateway()
    delivery = route(output, RouterConfig(), gateway)
    assert delivery is not None

    collector = FeedbackCollector(memory_store=store)
    collector.register_output(output, delivery)
    event = collector.process_signal(
        FeedbackSignal(
            platform="telegram",
            message_id=delivery.message_id or "",
            signal_type="reply",
            value="tell me more",
            sender="human",
            timestamp=datetime(2026, 5, 7, 12, 0),
        )
    )

    assert event is not None
    assert event.output_message_id == delivery.message_id
    assert event.output_intent_tag == "synthesis"
    assert event.output_mode == "prompted"
    assert event.signal_type == "reply"
    assert event.signal_value == "tell me more"
    assert event.source_note_ids == [source_note_id]
    assert event.retention_criteria == ["precision_surplus", "friction"]
    assert gateway.sent_messages == [
        OutboundMessage(
            content="A generated synthesis.",
            platform="telegram",
            format="text",
            intent_tag="synthesis",
        )
    ]

    feedback_notes = store.query_notes(NoteQuery(source="feedback"))
    assert len(feedback_notes) == 1
    assert feedback_notes[0].tier == 1
    assert feedback_notes[0].content == "Feedback: reply on [synthesis] output"
    assert feedback_notes[0].importance == 0.7
    assert feedback_notes[0].tags == [
        "feedback",
        "reply",
        "synthesis",
        "precision_surplus",
        "friction",
    ]
    assert feedback_notes[0].links == [source_note_id]
    assert store.get_note(source_note_id).unresolvedness == pytest.approx(0.45)


def test_feedback_collector_imports_alongside_public_boundary_types() -> None:
    from phosphene.feedback_collector import (
        FeedbackCollectorConfig,
        FeedbackEvent,
        OutputRecord,
    )
    from phosphene.gateway import FeedbackSignal as GatewayFeedbackSignal
    from phosphene.generator import GeneratorOutput as PublicGeneratorOutput
    from phosphene.memory_store import NoteInput as PublicNoteInput

    assert FeedbackCollectorConfig is not None
    assert FeedbackEvent is not None
    assert OutputRecord is not None
    assert GatewayFeedbackSignal is FeedbackSignal
    assert PublicGeneratorOutput is GeneratorOutput
    assert PublicNoteInput is NoteInput
