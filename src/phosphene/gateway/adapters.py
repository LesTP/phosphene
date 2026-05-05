"""Internal adapter protocol and registry for Gateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol

from phosphene.gateway.errors import PlatformConnectionError
from phosphene.gateway.types import FeedbackSignal, InboundMessage, PlatformConfig

InboundCallback = Callable[[InboundMessage], None]
FeedbackCallback = Callable[[FeedbackSignal], None]


class GatewayAdapter(Protocol):
    """Internal interface implemented by concrete Gateway adapters."""

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        """Start adapter-owned inbound listening if supported."""

    def stop_listener(self) -> None:
        """Stop adapter-owned inbound listening if supported."""


AdapterFactory = Callable[[PlatformConfig], GatewayAdapter]


class AdapterRegistry:
    """Immutable internal Gateway adapter factory registry."""

    def __init__(self, factories: Mapping[str, AdapterFactory]) -> None:
        self._factories = dict(factories)
        for adapter_type, factory in self._factories.items():
            if not adapter_type:
                raise ValueError("adapter_type is required")
            if not callable(factory):
                raise TypeError(f"adapter factory for {adapter_type} must be callable")

    def with_factories(
        self, factories: Mapping[str, AdapterFactory] | None
    ) -> "AdapterRegistry":
        if not factories:
            return self
        merged = dict(self._factories)
        merged.update(factories)
        return AdapterRegistry(merged)

    def supports(self, adapter_type: str) -> bool:
        return adapter_type in self._factories

    def create(self, config: PlatformConfig) -> GatewayAdapter:
        return self._factories[config.adapter_type](config)


class OutputOnlyAdapter:
    """Adapter base for platforms with no inbound listener in this phase."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.listener_started = False

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        self.listener_started = True

    def stop_listener(self) -> None:
        self.listener_started = False


class FakeGatewayAdapter(OutputOnlyAdapter):
    """Deterministic in-process adapter for Gateway lifecycle tests."""


class PendingGatewayAdapter:
    """Placeholder for ARCH adapter types implemented in later phases."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        raise PlatformConnectionError(
            f"{self.config.adapter_type} adapter is not implemented"
        )

    def stop_listener(self) -> None:
        return None


def fake_adapter_factory(config: PlatformConfig) -> GatewayAdapter:
    return FakeGatewayAdapter(config)


def log_adapter_factory(config: PlatformConfig) -> GatewayAdapter:
    return OutputOnlyAdapter(config)


def pending_adapter_factory(config: PlatformConfig) -> GatewayAdapter:
    return PendingGatewayAdapter(config)


DEFAULT_ADAPTER_REGISTRY = AdapterRegistry(
    {
        "fake": fake_adapter_factory,
        "log": log_adapter_factory,
        "telegram": pending_adapter_factory,
    }
)
