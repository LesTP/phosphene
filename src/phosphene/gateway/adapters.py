"""Internal adapter protocol and registry for Gateway."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
import inspect
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
        try:
            message_id = _send_telegram_message(
                self.client,
                chat_id=self.chat_id,
                message=message,
            )
        except Exception as exc:  # noqa: BLE001 - platform API failures are result data.
            return DeliveryResult(
                success=False,
                platform=self.config.name,
                message_id=None,
                error=str(exc),
            )

        return DeliveryResult(
            success=True,
            platform=self.config.name,
            message_id=str(message_id),
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


def _send_telegram_message(
    client: object,
    *,
    chat_id: str,
    message: OutboundMessage,
) -> object:
    chat_id_value = _coerce_optional_int(chat_id) or chat_id
    reply_to = _coerce_optional_int(message.reply_to)

    if message.format == "markdown":
        return _send_telegram_api_message(
            client,
            chat_id=chat_id_value,
            text=message.content,
            reply_to=reply_to,
            parse_mode=str(message.metadata.get("parse_mode") or "MarkdownV2"),
            metadata=message.metadata,
        )

    if message.format == "telegraph":
        for method_name in (
            "send_telegraph",
            "send_telegraph_message",
            "send_long_message",
        ):
            method = getattr(client, method_name, None)
            if method is not None:
                return _extract_message_id(
                    _resolve_awaitable(
                        _invoke_flexible(
                            method,
                            {
                                "chat_id": chat_id_value,
                                "text": message.content,
                                "content": message.content,
                                "reply_to": reply_to,
                                "reply_to_message_id": reply_to,
                                **message.metadata,
                            },
                        )
                    )
                )

    return _send_plain_telegram_message(
        client,
        chat_id=chat_id_value,
        text=message.content,
        reply_to=reply_to,
        metadata=message.metadata,
    )


def _send_plain_telegram_message(
    client: object,
    *,
    chat_id: object,
    text: str,
    reply_to: int | None,
    metadata: dict,
) -> object:
    method = getattr(client, "send_message", None)
    if method is not None:
        return _extract_message_id(
            _resolve_awaitable(
                _invoke_flexible(
                    method,
                    {
                        "chat_id": chat_id,
                        "text": text,
                        "reply_to": reply_to,
                        "reply_to_message_id": reply_to,
                        **metadata,
                    },
                )
            )
        )

    return _send_telegram_api_message(
        client,
        chat_id=chat_id,
        text=text,
        reply_to=reply_to,
        parse_mode=None,
        metadata=metadata,
    )


def _send_telegram_api_message(
    client: object,
    *,
    chat_id: object,
    text: str,
    reply_to: int | None,
    parse_mode: str | None,
    metadata: dict,
) -> object:
    method = getattr(client, "request_api", None)
    if method is None:
        raise RuntimeError("telegram client does not expose a supported send method")

    payload = {
        "chat_id": chat_id,
        "text": text,
        **{
            key: value
            for key, value in metadata.items()
            if key not in {"parse_mode", "intent_tag"} and value is not None
        },
    }
    if reply_to is not None:
        payload["reply_to_message_id"] = reply_to
    if parse_mode is not None:
        payload["parse_mode"] = parse_mode

    return _extract_message_id(
        _resolve_awaitable(
            _invoke_flexible(
                method,
                {
                    "method": "sendMessage",
                    "payload": payload,
                },
            )
        )
    )


def _invoke_flexible(method: object, kwargs: dict[str, object]) -> object:
    assert callable(method)
    signature = inspect.signature(method)
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return method(**kwargs)
    supported_kwargs = {
        key: value for key, value in kwargs.items() if key in signature.parameters
    }
    return method(**supported_kwargs)


def _resolve_awaitable(value: object) -> object:
    if not inspect.isawaitable(value):
        return value
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    raise RuntimeError("telegram client returned awaitable inside a running event loop")


def _extract_message_id(result: object) -> object:
    if isinstance(result, dict):
        response_result = result.get("result")
        if isinstance(response_result, dict) and "message_id" in response_result:
            return response_result["message_id"]
        if "message_id" in result:
            return result["message_id"]
    message_id = getattr(result, "message_id", None)
    if message_id is not None:
        return message_id
    return result


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


DEFAULT_ADAPTER_REGISTRY = AdapterRegistry(
    {
        "fake": fake_adapter_factory,
        "log": log_adapter_factory,
        "telegram": telegram_adapter_factory,
    }
)
