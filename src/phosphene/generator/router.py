"""Output Router public entry point."""

from __future__ import annotations

from phosphene.gateway import DeliveryResult, Gateway
from phosphene.generator.types import GeneratorOutput, RouterConfig


def route(
    output: GeneratorOutput,
    router_config: RouterConfig,
    gateway: Gateway,
) -> DeliveryResult | None:
    raise NotImplementedError("deterministic routing is implemented in a later phase")
