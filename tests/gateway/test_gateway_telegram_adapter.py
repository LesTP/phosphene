import pytest

from phosphene.gateway import (
    DeliveryResult,
    Gateway,
    GatewayConfig,
    OutboundMessage,
    PlatformConfig,
    PlatformConfigError,
)


class FakeTelegramClient:
    def __init__(self, config: PlatformConfig) -> None:
        self.bot_token = config.credentials["bot_token"]
        self.chat_id = config.params["chat_id"]
        self.sent_messages: list[dict] = []
        self.api_requests: list[dict] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to: int | None = None,
    ) -> int:
        self.sent_messages.append(
            {"chat_id": chat_id, "text": text, "reply_to": reply_to}
        )
        return 200 + len(self.sent_messages)

    async def request_api(self, method: str, payload: dict | None = None) -> dict:
        self.api_requests.append({"method": method, "payload": dict(payload or {})})
        return {"ok": True, "result": {"message_id": 500 + len(self.api_requests)}}


def _telegram_platform() -> PlatformConfig:
    return PlatformConfig(
        name="telegram",
        adapter_type="telegram",
        credentials={"bot_token": "test-token"},
        params={"chat_id": "12345"},
        output_formats=["text", "markdown", "telegraph", "thread"],
    )


def test_telegram_adapter_constructs_client_through_injected_factory() -> None:
    created: list[PlatformConfig] = []

    def factory(config: PlatformConfig) -> FakeTelegramClient:
        created.append(config)
        return FakeTelegramClient(config)

    gateway = Gateway(
        GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
        lambda _: None,
        lambda _: None,
        _telegram_client_factory=factory,
    )

    adapter = gateway._adapters_by_platform["telegram"]

    assert created == [_telegram_platform()]
    assert adapter.client.bot_token == "test-token"
    assert adapter.client.chat_id == "12345"
    assert adapter.chat_id == "12345"


def test_telegram_adapter_sends_text_and_thread_messages_through_client() -> None:
    gateway = Gateway(
        GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
        lambda _: None,
        lambda _: None,
        _telegram_client_factory=FakeTelegramClient,
    )
    adapter = gateway._adapters_by_platform["telegram"]

    text_result = gateway.send(
        OutboundMessage(
            content="plain",
            platform="telegram",
            format="text",
            intent_tag="free_play",
        )
    )
    thread_result = gateway.send(
        OutboundMessage(
            content="threaded",
            platform="telegram",
            format="thread",
            reply_to="77",
            intent_tag="reply",
        )
    )

    assert text_result == DeliveryResult(
        success=True,
        platform="telegram",
        message_id="201",
    )
    assert thread_result == DeliveryResult(
        success=True,
        platform="telegram",
        message_id="202",
    )
    assert adapter.client.sent_messages == [
        {"chat_id": 12345, "text": "plain", "reply_to": None},
        {"chat_id": 12345, "text": "threaded", "reply_to": 77},
    ]
    assert gateway._recent_deliveries[("telegram", "202")].intent_tag == "reply"


def test_telegram_adapter_sends_markdown_with_parse_mode_and_reply_metadata() -> None:
    gateway = Gateway(
        GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
        lambda _: None,
        lambda _: None,
        _telegram_client_factory=FakeTelegramClient,
    )
    adapter = gateway._adapters_by_platform["telegram"]

    result = gateway.send(
        OutboundMessage(
            content="*rich*",
            platform="telegram",
            format="markdown",
            reply_to="42",
            metadata={"parse_mode": "Markdown", "disable_web_page_preview": True},
        )
    )

    assert result == DeliveryResult(
        success=True,
        platform="telegram",
        message_id="501",
    )
    assert adapter.client.api_requests == [
        {
            "method": "sendMessage",
            "payload": {
                "chat_id": 12345,
                "text": "*rich*",
                "disable_web_page_preview": True,
                "reply_to_message_id": 42,
                "parse_mode": "Markdown",
            },
        }
    ]


def test_telegram_adapter_sends_telegraph_format_via_supported_long_method() -> None:
    class TelegraphClient(FakeTelegramClient):
        def __init__(self, config: PlatformConfig) -> None:
            super().__init__(config)
            self.telegraph_messages: list[dict] = []

        def send_telegraph(
            self,
            chat_id: int,
            content: str,
            reply_to_message_id: int | None = None,
        ) -> dict:
            self.telegraph_messages.append(
                {
                    "chat_id": chat_id,
                    "content": content,
                    "reply_to_message_id": reply_to_message_id,
                }
            )
            return {"message_id": 900}

    gateway = Gateway(
        GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
        lambda _: None,
        lambda _: None,
        _telegram_client_factory=TelegraphClient,
    )
    adapter = gateway._adapters_by_platform["telegram"]

    result = gateway.send(
        OutboundMessage(
            content="long",
            platform="telegram",
            format="telegraph",
            reply_to="8",
        )
    )

    assert result == DeliveryResult(
        success=True,
        platform="telegram",
        message_id="900",
    )
    assert adapter.client.telegraph_messages == [
        {"chat_id": 12345, "content": "long", "reply_to_message_id": 8}
    ]


def test_telegram_adapter_converts_client_send_failure_to_delivery_result() -> None:
    class FailingClient(FakeTelegramClient):
        async def send_message(
            self,
            chat_id: int,
            text: str,
            reply_to: int | None = None,
        ) -> int:
            raise RuntimeError("telegram unavailable")

    gateway = Gateway(
        GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
        lambda _: None,
        lambda _: None,
        _telegram_client_factory=FailingClient,
    )

    result = gateway.send(OutboundMessage(content="plain", platform="telegram"))

    assert result == DeliveryResult(
        success=False,
        platform="telegram",
        message_id=None,
        error="telegram unavailable",
    )


def test_telegram_adapter_rejects_noncallable_client_factory() -> None:
    with pytest.raises(PlatformConfigError, match="failed to create adapter"):
        Gateway(
            GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
            lambda _: None,
            lambda _: None,
            _telegram_client_factory=object(),
        )


def test_telegram_adapter_wraps_client_factory_failure() -> None:
    def factory(config: PlatformConfig) -> FakeTelegramClient:
        raise RuntimeError("factory failed")

    with pytest.raises(PlatformConfigError, match="failed to create adapter"):
        Gateway(
            GatewayConfig(platforms=[_telegram_platform()], default_platform="telegram"),
            lambda _: None,
            lambda _: None,
            _telegram_client_factory=factory,
        )
