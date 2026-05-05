"""Gateway manager entry point."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from phosphene.gateway.errors import (
    FormatNotSupportedError,
    PlatformConfigError,
    PlatformNotFoundError,
)
from phosphene.gateway.types import (
    DeliveryResult,
    FeedbackSignal,
    GatewayConfig,
    InboundMessage,
    OutboundMessage,
    PlatformConfig,
)


_SUPPORTED_ADAPTER_TYPES = {"telegram", "log", "fake"}
_SUPPORTED_OUTPUT_FORMATS = {"text", "markdown", "thread", "telegraph"}

_REQUIRED_CREDENTIAL_KEYS = {
    "telegram": (("bot_token",),),
}
_REQUIRED_PARAM_KEYS = {
    "telegram": (("chat_id",),),
    "log": (("log_path",),),
}


class Gateway:
    """Gateway public entry point."""

    def __init__(
        self,
        config: GatewayConfig,
        on_message: Callable[[InboundMessage], None],
        on_feedback: Callable[[FeedbackSignal], None],
    ) -> None:
        self.config = config
        self.on_message = on_message
        self.on_feedback = on_feedback
        self._platforms_by_name = _validate_and_index_platforms(config)

    def send(self, message: OutboundMessage) -> DeliveryResult:
        platform = self._get_enabled_platform(message.platform)
        _validate_message_format(message, platform)
        raise NotImplementedError("Gateway.send is implemented in Step 4.1.3")

    def send_to_default(
        self,
        content: str,
        format: str = "text",
        intent_tag: str | None = None,
    ) -> DeliveryResult:
        return self.send(
            OutboundMessage(
                content=content,
                platform=self.config.default_platform,
                format=format,
                intent_tag=intent_tag,
            )
        )

    def start_listener(self) -> None:
        raise NotImplementedError("Gateway.start_listener is implemented in Step 4.1.2")

    def stop_listener(self) -> None:
        raise NotImplementedError("Gateway.stop_listener is implemented in Step 4.1.2")

    def _enabled_platform_configs(self) -> list[PlatformConfig]:
        return [platform for platform in self.config.platforms if platform.enabled]

    def _get_enabled_platform(self, platform_name: str) -> PlatformConfig:
        try:
            platform = self._platforms_by_name[platform_name]
        except KeyError as exc:
            raise PlatformNotFoundError(
                f"platform not found: {platform_name}"
            ) from exc
        if not platform.enabled:
            raise PlatformNotFoundError(f"platform is disabled: {platform_name}")
        return platform


def _validate_and_index_platforms(
    config: GatewayConfig,
) -> dict[str, PlatformConfig]:
    platforms_by_name: dict[str, PlatformConfig] = {}
    for platform in config.platforms:
        _validate_platform_config(platform)
        if platform.name in platforms_by_name:
            raise PlatformConfigError(f"duplicate platform name: {platform.name}")
        platforms_by_name[platform.name] = platform

    default_platform = platforms_by_name.get(config.default_platform)
    if default_platform is None:
        raise PlatformConfigError(
            f"default platform not configured: {config.default_platform}"
        )
    if not default_platform.enabled:
        raise PlatformConfigError(
            f"default platform is disabled: {config.default_platform}"
        )

    return platforms_by_name


def _validate_platform_config(platform: PlatformConfig) -> None:
    if not platform.name:
        raise PlatformConfigError("platform name is required")
    if not platform.adapter_type:
        raise PlatformConfigError("platform adapter_type is required")
    if platform.adapter_type not in _SUPPORTED_ADAPTER_TYPES:
        raise PlatformConfigError(f"unknown adapter_type: {platform.adapter_type}")

    _validate_required_keys(
        platform.params,
        _REQUIRED_PARAM_KEYS.get(platform.adapter_type, ()),
        "params",
        platform.adapter_type,
    )
    _validate_required_keys(
        platform.credentials,
        _REQUIRED_CREDENTIAL_KEYS.get(platform.adapter_type, ()),
        "credentials",
        platform.adapter_type,
    )
    _validate_output_formats(platform)


def _validate_required_keys(
    values: dict | None,
    acceptable_key_sets: tuple[tuple[str, ...], ...],
    field_name: str,
    adapter_type: str,
) -> None:
    if not acceptable_key_sets:
        return

    value_map = values or {}
    for key_set in acceptable_key_sets:
        if all(_has_value(value_map, key) for key in key_set):
            return

    required = " or ".join(", ".join(key_set) for key_set in acceptable_key_sets)
    raise PlatformConfigError(
        f"{adapter_type} adapter missing required {field_name}: {required}"
    )


def _has_value(values: dict, key: str) -> bool:
    value = values.get(key)
    return value is not None and value != ""


def _validate_output_formats(platform: PlatformConfig) -> None:
    if not platform.output_formats:
        raise PlatformConfigError(
            f"platform output_formats must not be empty: {platform.name}"
        )
    unsupported = [
        output_format
        for output_format in platform.output_formats
        if output_format not in _SUPPORTED_OUTPUT_FORMATS
    ]
    if unsupported:
        raise PlatformConfigError(
            f"platform output_formats contain unsupported formats: {', '.join(unsupported)}"
        )


def _validate_message_format(
    message: OutboundMessage,
    platform: PlatformConfig,
) -> None:
    if message.format not in platform.output_formats:
        raise FormatNotSupportedError(
            f"format not supported by platform {platform.name}: {message.format}"
        )


def _enabled_platforms(platforms: Iterable[PlatformConfig]) -> list[PlatformConfig]:
    return [platform for platform in platforms if platform.enabled]
