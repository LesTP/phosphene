import json
from dataclasses import dataclass, field
from datetime import datetime

import phosphene.generator.generator as generator_module
from phosphene.gateway import DeliveryResult, OutboundMessage
from phosphene.generator import (
    GenerationPrompt,
    Generator,
    GeneratorConfig,
    GeneratorOutput,
    LengthThresholds,
    RouterConfig,
    route,
)
from phosphene.generator.types import TokenUsage
from phosphene.memory_store import MemoryNote, PersonalityContext


def make_note(note_id: str, *, tier: int, importance: float = 0.0) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"{note_id} content",
        title=note_id,
        importance=importance,
        unresolvedness=0.0,
        links=[],
        tags=[],
        source=None,
        friction_target=None,
        embedding=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        link_count=0,
        decay_deadline=None,
    )


@dataclass
class RecordingMemoryStore:
    personality_files: list[MemoryNote]
    pattern_files: list[MemoryNote] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.context_calls = 0
        self.query_calls: list[object] = []
        self.write_calls: list[str] = []

    def get_personality_context(self) -> PersonalityContext:
        self.context_calls += 1
        return PersonalityContext(
            personality_files=list(self.personality_files),
            version_id=f"snapshot-{self.context_calls}",
        )

    def query_notes(self, query: object) -> list[MemoryNote]:
        self.query_calls.append(query)
        return list(self.pattern_files)

    def store_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("store_note")

    def update_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("update_note")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("add_links")


@dataclass
class CredentiallessGatewayConfig:
    default_platform: str = "test-platform"


@dataclass
class RecordingGateway:
    config: CredentiallessGatewayConfig = field(default_factory=CredentiallessGatewayConfig)

    def __post_init__(self) -> None:
        self.sent_messages: list[OutboundMessage] = []

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent_messages.append(message)
        return DeliveryResult(
            success=True,
            platform=message.platform,
            message_id=f"{message.platform}-{len(self.sent_messages)}",
        )


def output_from_snapshot(generator: Generator, content: str) -> GeneratorOutput:
    snapshot = generator._load_personality_snapshot(
        {"activation": "integration"},
        GeneratorConfig(llm_config=object()),
    )
    return GeneratorOutput(
        content=content,
        intent_tag="synthesis",
        output_mode="response",
        importance_score=0.6,
        is_lateral=False,
        source_note_ids=generator._source_note_ids(snapshot),
        contradictions_noted=snapshot.contradictions,
        token_usage=TokenUsage(),
        originating_message_id="inbound-1",
    )


def test_foundation_is_stateless_read_only_and_routes_gateway_compatible_output() -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    store = RecordingMemoryStore([personality], [pattern])
    gateway = RecordingGateway()
    generator = Generator(store)

    first_output = output_from_snapshot(generator, "short output")
    second_output = output_from_snapshot(generator, "x" * 11)
    config = RouterConfig(length_thresholds=LengthThresholds(short_max=10, medium_max=20))

    first_result = route(first_output, config, gateway)
    second_result = route(second_output, config, gateway)

    assert store.context_calls == 2
    assert len(store.query_calls) == 2
    assert store.write_calls == []
    assert first_output.source_note_ids == ["personality-1", "pattern-1"]
    assert second_output.source_note_ids == ["personality-1", "pattern-1"]
    assert first_result == DeliveryResult(
        success=True,
        platform="test-platform",
        message_id="test-platform-1",
    )
    assert second_result == DeliveryResult(
        success=True,
        platform="test-platform",
        message_id="test-platform-2",
    )
    assert gateway.sent_messages == [
        OutboundMessage(
            content="short output",
            platform="test-platform",
            format="markdown",
            reply_to="inbound-1",
            intent_tag="synthesis",
        ),
        OutboundMessage(
            content="x" * 11,
            platform="test-platform",
            format="markdown",
            reply_to="inbound-1",
            intent_tag="synthesis",
        ),
    ]


def test_public_generate_boundary_loads_context_without_live_credentials(
    monkeypatch,
) -> None:
    store = RecordingMemoryStore([make_note("personality-1", tier=3)])

    def fake_complete(**_kwargs: object) -> object:
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=TokenUsage(),
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(topic="density"),
        {},
        GeneratorConfig(llm_config=object()),
    )

    assert output.content == "generated"
    assert output.source_note_ids == ["personality-1"]
    assert store.context_calls == 1
    assert store.write_calls == []
