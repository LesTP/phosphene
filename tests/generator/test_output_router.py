from dataclasses import dataclass, field

from phosphene.gateway import DeliveryResult, OutboundMessage
from phosphene.generator import GeneratorOutput, LengthThresholds, RouterConfig, route
from phosphene.generator.types import TokenUsage


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


def make_output(
    content: str,
    *,
    intent_tag: str = "synthesis",
    output_mode: str = "prompted",
    originating_message_id: str | None = None,
) -> GeneratorOutput:
    return GeneratorOutput(
        content=content,
        intent_tag=intent_tag,
        output_mode=output_mode,
        importance_score=0.5,
        is_lateral=False,
        source_note_ids=["personality-1"],
        contradictions_noted=[],
        token_usage=TokenUsage(),
        originating_message_id=originating_message_id,
    )


def test_route_suppresses_log_only_intents_without_gateway_delivery() -> None:
    gateway = FakeGateway()

    result = route(make_output("private", intent_tag="internal_note"), RouterConfig(), gateway)

    assert result is None
    assert gateway.sent_messages == []


def test_route_delivers_short_output_as_text_to_default_platform() -> None:
    gateway = FakeGateway(FakeGatewayConfig(default_platform="default-channel"))

    result = route(make_output("short"), RouterConfig(), gateway)

    assert result == DeliveryResult(
        success=True,
        platform="default-channel",
        message_id="default-channel-1",
    )
    assert gateway.sent_messages == [
        OutboundMessage(
            content="short",
            platform="default-channel",
            format="text",
            intent_tag="synthesis",
        )
    ]


def test_route_selects_markdown_and_telegraph_by_length() -> None:
    gateway = FakeGateway()
    config = RouterConfig(length_thresholds=LengthThresholds(short_max=5, medium_max=10))

    markdown_result = route(make_output("123456"), config, gateway)
    telegraph_result = route(make_output("12345678901"), config, gateway)

    assert markdown_result is not None
    assert markdown_result.platform == "telegram"
    assert telegraph_result is not None
    assert telegraph_result.platform == "telegram"
    assert [message.format for message in gateway.sent_messages] == [
        "markdown",
        "telegraph",
    ]


def test_route_threads_response_outputs_from_originating_message_id() -> None:
    gateway = FakeGateway()

    route(
        make_output(
            "reply",
            output_mode="response",
            originating_message_id="inbound-42",
        ),
        RouterConfig(),
        gateway,
    )

    assert gateway.sent_messages[0].reply_to == "inbound-42"


def test_route_uses_intent_platform_override_and_returns_gateway_result() -> None:
    gateway = FakeGateway()
    config = RouterConfig(intent_routing={"synthesis": "local-log"})

    result = route(make_output("archive this"), config, gateway)

    assert result == DeliveryResult(
        success=True,
        platform="local-log",
        message_id="local-log-1",
    )
    assert gateway.sent_messages[0].platform == "local-log"
