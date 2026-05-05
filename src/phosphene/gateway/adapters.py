"""Internal adapter protocol and registry for Gateway."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Protocol

from phosphene.gateway.errors import PlatformConfigError, PlatformConnectionError
from phosphene.gateway.types import (
    DeliveryResult,
    FeedbackSignal,
    InboundMessage,
    OutboundMessage,
    PlatformConfig,
)

InboundCallback = Callable[[InboundMessage], None]
FeedbackCallback = Callable[[FeedbackSignal], None]


class GatewayAdapter(Protocol):
    """Internal interface implemented by concrete Gateway adapters."""

    def send(self, message: OutboundMessage) -> DeliveryResult:
        """Deliver an outbound message through this adapter."""

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        """Start adapter-owned inbound listening if supported."""

    def stop_listener(self) -> None:
        """Stop adapter-owned inbound listening if supported."""


AdapterFactory = Callable[[PlatformConfig], GatewayAdapter]
TelegramClientFactory = Callable[[PlatformConfig], object]


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
        self.sent_messages: list[OutboundMessage] = []
        self._on_message: InboundCallback | None = None
        self._on_feedback: FeedbackCallback | None = None

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent_messages.append(message)
        return DeliveryResult(
            success=True,
            platform=self.config.name,
            message_id=f"{self.config.name}-{len(self.sent_messages)}",
        )

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        self.listener_started = True
        self._on_message = on_message
        self._on_feedback = on_feedback

    def stop_listener(self) -> None:
        self.listener_started = False
        self._on_message = None
        self._on_feedback = None


class FakeGatewayAdapter(OutputOnlyAdapter):
    """Deterministic in-process adapter for Gateway lifecycle tests."""

    def dispatch_inbound(self, message: InboundMessage) -> None:
        if self.listener_started and self._on_message is not None:
            self._on_message(message)

    def dispatch_feedback(self, signal: FeedbackSignal) -> None:
        if self.listener_started and self._on_feedback is not None:
            self._on_feedback(signal)


class LogGatewayAdapter:
    """Local development adapter that appends outbound messages as JSON lines."""

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self.log_path = Path(config.params["log_path"])
        self.sent_count = 0

    def send(self, message: OutboundMessage) -> DeliveryResult:
        self.sent_count += 1
        message_id = f"{self.config.name}-{self.sent_count}"
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "platform": self.config.name,
            "message_id": message_id,
            "content": message.content,
            "format": message.format,
            "reply_to": message.reply_to,
            "intent_tag": message.intent_tag,
            "metadata": message.metadata,
        }
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(record, sort_keys=True) + "\n")

        return DeliveryResult(
            success=True,
            platform=self.config.name,
            message_id=message_id,
        )

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        return None

    def stop_listener(self) -> None:
        return None


class TelegramGatewayAdapter:
    """Telegram Gateway adapter backed by toolkit/telegram_client."""

    def __init__(
        self,
        config: PlatformConfig,
        client_factory: TelegramClientFactory | None = None,
    ) -> None:
        self.config = config
        self.chat_id = config.params["chat_id"]
        factory = client_factory or default_telegram_client_factory
        if not callable(factory):
            raise PlatformConfigError("telegram client factory must be callable")
        self.client = factory(config)

    def send(self, message: OutboundMessage) -> DeliveryResult:
        return DeliveryResult(
            success=False,
            platform=self.config.name,
            message_id=None,
            error="telegram delivery is not implemented",
        )

    def start_listener(
        self,
        on_message: InboundCallback,
        on_feedback: FeedbackCallback,
    ) -> None:
        raise PlatformConnectionError("telegram polling is not implemented")

    def stop_listener(self) -> None:
        return None


def fake_adapter_factory(config: PlatformConfig) -> GatewayAdapter:
    return FakeGatewayAdapter(config)


def log_adapter_factory(config: PlatformConfig) -> GatewayAdapter:
    return LogGatewayAdapter(config)


def default_telegram_client_factory(config: PlatformConfig) -> object:
    try:
        from toolkit.telegram_client import TelegramClient
    except ImportError as exc:
        raise PlatformConfigError("toolkit telegram client is unavailable") from exc

    bot_token = config.credentials["bot_token"]
    chat_id = config.params["chat_id"]
    allowed_chat_ids: list[int] | None = None
    try:
        allowed_chat_ids = [int(chat_id)]
    except (TypeError, ValueError):
        allowed_chat_ids = None
    return TelegramClient(bot_token=bot_token, allowed_chat_ids=allowed_chat_ids)


def telegram_adapter_factory(
    config: PlatformConfig,
    client_factory: TelegramClientFactory | None = None,
) -> GatewayAdapter:
    return TelegramGatewayAdapter(config, client_factory=client_factory)


DEFAULT_ADAPTER_REGISTRY = AdapterRegistry(
    {
        "fake": fake_adapter_factory,
        "log": log_adapter_factory,
        "telegram": telegram_adapter_factory,
    }
)
