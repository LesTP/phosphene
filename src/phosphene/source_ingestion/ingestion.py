"""Source Ingestion manager entry point."""

from __future__ import annotations

from collections.abc import Iterable

from phosphene.source_ingestion.errors import AdapterConfigError, AdapterNotFoundError
from phosphene.source_ingestion.types import AdapterConfig, IngestionConfig, IngestionResult


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


class SourceIngestion:
    """Constructor-compatible Source Ingestion manager stub."""

    def __init__(self, config: IngestionConfig) -> None:
        self.config = config
        self._adapters_by_label = _validate_and_index_adapters(config.adapters)

    def poll(self, adapter_label: str | None = None) -> list[IngestionResult]:
        if adapter_label is not None:
            self._get_adapter_config(adapter_label)
            raise NotImplementedError(
                "SourceIngestion.poll is implemented in a later phase step"
            )

        if not self._enabled_adapter_configs():
            return []
        raise NotImplementedError("SourceIngestion.poll is implemented in a later phase step")

    def poll_once(self, adapter_label: str) -> IngestionResult:
        self._get_adapter_config(adapter_label)
        raise NotImplementedError("SourceIngestion.poll_once is implemented in a later phase step")

    def _enabled_adapter_configs(self) -> list[AdapterConfig]:
        return [adapter for adapter in self.config.adapters if adapter.enabled]

    def _get_adapter_config(self, adapter_label: str) -> AdapterConfig:
        try:
            return self._adapters_by_label[adapter_label]
        except KeyError as exc:
            raise AdapterNotFoundError(f"adapter label not found: {adapter_label}") from exc


def _validate_and_index_adapters(adapters: Iterable[AdapterConfig]) -> dict[str, AdapterConfig]:
    adapters_by_label: dict[str, AdapterConfig] = {}
    for adapter in adapters:
        _validate_adapter_config(adapter)
        if adapter.source_label in adapters_by_label:
            raise AdapterConfigError(f"duplicate adapter source_label: {adapter.source_label}")
        adapters_by_label[adapter.source_label] = adapter
    return adapters_by_label


def _validate_adapter_config(adapter: AdapterConfig) -> None:
    if adapter.adapter_type not in _SUPPORTED_ADAPTER_TYPES:
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
