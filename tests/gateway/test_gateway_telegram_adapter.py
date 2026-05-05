import pytest

from phosphene.gateway import Gateway, GatewayConfig, PlatformConfig, PlatformConfigError


class FakeTelegramClient:
    def __init__(self, config: PlatformConfig) -> None:
        self.bot_token = config.credentials["bot_token"]
        self.chat_id = config.params["chat_id"]


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
