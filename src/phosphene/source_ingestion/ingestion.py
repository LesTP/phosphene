"""Source Ingestion manager entry point."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from phosphene.source_ingestion.adapters import (
    AdapterFactory,
    AdapterItemError,
    AdapterRegistry,
    LastSeenMarker,
    SourceAdapter,
    pending_adapter_factory,
)
from phosphene.source_ingestion.corpus import (
    corpus_blog_adapter_factory,
    corpus_conversations_adapter_factory,
    corpus_livejournal_adapter_factory,
    corpus_text_adapter_factory,
    corpus_twitter_adapter_factory,
)
from phosphene.source_ingestion.errors import AdapterConfigError, AdapterNotFoundError
from phosphene.source_ingestion.human_share import human_share_adapter_factory
from phosphene.source_ingestion.reddit import reddit_adapter_factory
from phosphene.source_ingestion.rss import rss_adapter_factory
from phosphene.source_ingestion.telegram_channel import (
    telegram_channel_adapter_factory,
)
from phosphene.source_ingestion.types import (
    AdapterConfig,
    IngestionConfig,
    IngestionError,
    IngestionResult,
)


_SUPPORTED_ADAPTER_TYPES = {
    "telegram_channel",
    "telegram_bot",
    "rss",
    "reddit",
    "human_share",
    "corpus_livejournal",
    "corpus_twitter",
    "corpus_blog",
    "corpus_conversations",
    "corpus_text",
}

_REQUIRED_CREDENTIAL_KEYS = {
    "telegram_channel": (("bot_token",),),
    "reddit": (("client_id", "client_secret"),),
    "human_share": (("bot_token",),),
}

_REQUIRED_PARAM_KEYS = {
    "telegram_channel": (("channel_id",), ("channel_username",)),
    "rss": (("feed_url",),),
    "reddit": (("subreddit", "sort"),),
    "human_share": (("bot_chat_id",),),
    "corpus_livejournal": (("archive_path",),),
    "corpus_twitter": (("archive_path",),),
    "corpus_blog": (("archive_path", "format"),),
    "corpus_conversations": (("archive_path", "format"),),
    "corpus_text": (("archive_path",),),
}

_REDDIT_SORT_VALUES = {"new", "hot", "top"}
_CORPUS_BLOG_FORMAT_VALUES = {"markdown", "html"}
_CORPUS_CONVERSATION_FORMAT_VALUES = {"json", "text"}

_ADAPTER_REGISTRY: dict[str, AdapterFactory] = {
    adapter_type: pending_adapter_factory(adapter_type)
    for adapter_type in _SUPPORTED_ADAPTER_TYPES
}
_ADAPTER_REGISTRY["rss"] = rss_adapter_factory
_ADAPTER_REGISTRY["corpus_text"] = corpus_text_adapter_factory
_ADAPTER_REGISTRY["corpus_blog"] = corpus_blog_adapter_factory
_ADAPTER_REGISTRY["corpus_livejournal"] = corpus_livejournal_adapter_factory
_ADAPTER_REGISTRY["corpus_twitter"] = corpus_twitter_adapter_factory
_ADAPTER_REGISTRY["corpus_conversations"] = corpus_conversations_adapter_factory
_ADAPTER_REGISTRY["human_share"] = human_share_adapter_factory
_ADAPTER_REGISTRY["telegram_channel"] = telegram_channel_adapter_factory
_ADAPTER_REGISTRY["reddit"] = reddit_adapter_factory
_DEFAULT_ADAPTER_REGISTRY = AdapterRegistry(_ADAPTER_REGISTRY)


class SourceIngestion:
    """Source Ingestion manager."""

    def __init__(self, config: IngestionConfig) -> None:
        self.config = config
        self._adapter_registry = _build_adapter_registry(_ADAPTER_REGISTRY)
        self._adapters_by_label = _validate_and_index_adapters(
            config.adapters, self._adapter_registry
        )
        self._adapter_instances = {
            adapter.source_label: _create_adapter(
                adapter, self._adapter_registry, self.config
            )
            for adapter in config.adapters
        }
        self._last_seen_markers: dict[str, LastSeenMarker] = {}

    def poll(self, adapter_label: str | None = None) -> list[IngestionResult]:
        if adapter_label is not None:
            return [self.poll_once(adapter_label)]

        return [self._poll_adapter(adapter) for adapter in self._enabled_adapter_configs()]

    def poll_once(self, adapter_label: str) -> IngestionResult:
        return self._poll_adapter(self._get_adapter_config(adapter_label))

    def _enabled_adapter_configs(self) -> list[AdapterConfig]:
        return [adapter for adapter in self.config.adapters if adapter.enabled]

    def _get_adapter_config(self, adapter_label: str) -> AdapterConfig:
        try:
            return self._adapters_by_label[adapter_label]
        except KeyError as exc:
            raise AdapterNotFoundError(f"adapter label not found: {adapter_label}") from exc

    def _poll_adapter(self, adapter_config: AdapterConfig) -> IngestionResult:
        adapter = self._adapter_instances[adapter_config.source_label]
        poll_timestamp = datetime.now(timezone.utc)

        try:
            poll_result = adapter.poll(self._last_seen_markers.get(adapter_config.source_label))
        except Exception as exc:  # noqa: BLE001 - adapter failures are reported per ARCH.
            return IngestionResult(
                items=[],
                adapter_label=adapter_config.source_label,
                errors=[
                    IngestionError(
                        url=None,
                        error=str(exc),
                        adapter_label=adapter_config.source_label,
                    )
                ],
                poll_timestamp=poll_timestamp,
            )

        self._last_seen_markers[adapter_config.source_label] = poll_result.next_marker
        return IngestionResult(
            items=poll_result.items,
            adapter_label=adapter_config.source_label,
            errors=[
                _to_ingestion_error(error, adapter_config.source_label)
                for error in poll_result.errors
            ],
            poll_timestamp=poll_timestamp,
        )


def _build_adapter_registry(
    factories: dict[str, AdapterFactory] | None = None,
) -> AdapterRegistry:
    return _DEFAULT_ADAPTER_REGISTRY.with_factories(factories)


def _validate_and_index_adapters(
    adapters: Iterable[AdapterConfig], registry: AdapterRegistry | None = None
) -> dict[str, AdapterConfig]:
    registry = registry or _build_adapter_registry(_ADAPTER_REGISTRY)
    adapters_by_label: dict[str, AdapterConfig] = {}
    for adapter in adapters:
        _validate_adapter_config(adapter, registry)
        if adapter.source_label in adapters_by_label:
            raise AdapterConfigError(f"duplicate adapter source_label: {adapter.source_label}")
        adapters_by_label[adapter.source_label] = adapter
    return adapters_by_label


def _validate_adapter_config(
    adapter: AdapterConfig, registry: AdapterRegistry | None = None
) -> None:
    registry = registry or _build_adapter_registry(_ADAPTER_REGISTRY)
    if not registry.supports(adapter.adapter_type):
        raise AdapterConfigError(f"unknown adapter_type: {adapter.adapter_type}")
    if not adapter.source_label:
        raise AdapterConfigError("adapter source_label is required")

    _validate_required_keys(
        adapter.params,
        _REQUIRED_PARAM_KEYS.get(adapter.adapter_type, ()),
        "params",
        adapter.adapter_type,
    )
    _validate_required_keys(
        adapter.credentials,
        _REQUIRED_CREDENTIAL_KEYS.get(adapter.adapter_type, ()),
        "credentials",
        adapter.adapter_type,
    )
    _validate_enum_values(adapter)


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
    raise AdapterConfigError(
        f"{adapter_type} adapter missing required {field_name}: {required}"
    )


def _has_value(values: dict, key: str) -> bool:
    value = values.get(key)
    return value is not None and value != ""


def _validate_enum_values(adapter: AdapterConfig) -> None:
    if adapter.adapter_type == "reddit":
        sort = adapter.params.get("sort")
        if sort not in _REDDIT_SORT_VALUES:
            raise AdapterConfigError("reddit adapter params.sort must be new, hot, or top")
    if adapter.adapter_type == "corpus_blog":
        file_format = adapter.params.get("format")
        if file_format not in _CORPUS_BLOG_FORMAT_VALUES:
            raise AdapterConfigError("corpus_blog adapter params.format must be markdown or html")
    if adapter.adapter_type == "corpus_conversations":
        file_format = adapter.params.get("format")
        if file_format not in _CORPUS_CONVERSATION_FORMAT_VALUES:
            raise AdapterConfigError(
                "corpus_conversations adapter params.format must be json or text"
            )


def _create_adapter(
    adapter: AdapterConfig,
    registry: AdapterRegistry | None = None,
    ingestion_config: IngestionConfig | None = None,
) -> SourceAdapter:
    registry = registry or _build_adapter_registry(_ADAPTER_REGISTRY)
    try:
        return registry.create(adapter, ingestion_config)
    except KeyError as exc:
        raise AdapterConfigError(f"unknown adapter_type: {adapter.adapter_type}") from exc


def _to_ingestion_error(error: AdapterItemError, adapter_label: str) -> IngestionError:
    return IngestionError(url=error.url, error=error.error, adapter_label=adapter_label)
