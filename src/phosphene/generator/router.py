"""Output Router public entry point."""

from __future__ import annotations

from toolkit.gateway import DeliveryResult, Gateway, OutboundMessage
from phosphene.generator.types import GeneratorOutput, RouterConfig


def route(
    output: GeneratorOutput,
    router_config: RouterConfig,
    gateway: Gateway,
) -> DeliveryResult | None:
    platform = router_config.intent_routing.get(output.intent_tag)
    if platform == "log":
        return None

    if platform is None:
        platform = gateway.config.default_platform

    message = OutboundMessage(
        content=output.content,
        platform=platform,
        format=_format_for_length(output.content, router_config),
        reply_to=_reply_to_for_output(output),
        intent_tag=output.intent_tag,
    )
    return gateway.send(message)


def _format_for_length(content: str, router_config: RouterConfig) -> str:
    length = len(content)
    thresholds = router_config.length_thresholds
    if length <= thresholds.short_max:
        return "text"
    if length <= thresholds.medium_max:
        return "markdown"
    return "telegraph"


def _reply_to_for_output(output: GeneratorOutput) -> str | None:
    if output.output_mode != "response":
        return None
    return output.originating_message_id
