"""Public Gateway API surface."""

from phosphene.gateway.errors import (
    DeliveryError,
    FormatNotSupportedError,
    GatewayError,
    PlatformConfigError,
    PlatformConnectionError,
    PlatformNotFoundError,
)
from phosphene.gateway.gateway import Gateway
from phosphene.gateway.types import (
    DeliveryResult,
    FeedbackSignal,
    GatewayConfig,
    InboundMessage,
    OutboundMessage,
    PlatformConfig,
)

__all__ = [
    "DeliveryError",
    "DeliveryResult",
    "FeedbackSignal",
    "FormatNotSupportedError",
    "Gateway",
    "GatewayConfig",
    "GatewayError",
    "InboundMessage",
    "OutboundMessage",
    "PlatformConfig",
    "PlatformConfigError",
    "PlatformConnectionError",
    "PlatformNotFoundError",
]
