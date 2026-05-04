from datetime import datetime

import pytest

from phosphene.source_ingestion import (
    AdapterConfig,
    ContentItem,
    IngestionConfig,
    SourceIngestion,
)
from phosphene.source_ingestion.adapters import (
    AdapterItemError,
    AdapterRegistry,
    AdapterPollResult,
    LastSeenMarker,
    adapter_error_from_exception,
)
from phosphene.source_ingestion.ingestion import _ADAPTER_REGISTRY, _build_adapter_registry


class FakeAdapter:
    def __init__(self, result: AdapterPollResult) -> None:
        self.result = result
        self.seen_markers: list[LastSeenMarker] = []

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        self.seen_markers.append(last_seen_marker)
        return self.result


class FailingAdapter:
    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        raise RuntimeError("adapter broke")


@pytest.fixture
def fake_registry(monkeypatch: pytest.MonkeyPatch) -> dict[str, FakeAdapter]:
    adapters: dict[str, FakeAdapter] = {}

    def factory(config: AdapterConfig) -> FakeAdapter:
        adapter = FakeAdapter(
            AdapterPollResult(
                items=[
                    ContentItem(
                        content=f"{config.source_label} item",
                        source=config.adapter_type,
                        timestamp=datetime(2026, 1, 1),
                    )
                ],
                errors=[AdapterItemError(error="bad item", url="https://example.com/bad")],
                next_marker=f"{config.source_label}:marker",
            )
        )
        adapters[config.source_label] = adapter
        return adapter

    monkeypatch.setitem(_ADAPTER_REGISTRY, "fake_source", factory)
    return adapters


def test_poll_once_assembles_result_and_tracks_last_seen_marker(
    fake_registry: dict[str, FakeAdapter],
) -> None:
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(adapter_type="fake_source", source_label="fake"),
            ]
        )
    )

    first = manager.poll_once("fake")
    second = manager.poll_once("fake")

    assert first.adapter_label == "fake"
    assert [item.content for item in first.items] == ["fake item"]
    assert first.errors[0].adapter_label == "fake"
    assert first.errors[0].url == "https://example.com/bad"
    assert first.errors[0].error == "bad item"
    assert fake_registry["fake"].seen_markers == [None, "fake:marker"]
    assert second.poll_timestamp >= first.poll_timestamp


def test_poll_all_uses_enabled_adapters_in_config_order(
    fake_registry: dict[str, FakeAdapter],
) -> None:
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(adapter_type="fake_source", source_label="first"),
                AdapterConfig(
                    adapter_type="fake_source",
                    source_label="disabled",
                    enabled=False,
                ),
                AdapterConfig(adapter_type="fake_source", source_label="second"),
            ]
        )
    )

    results = manager.poll()

    assert [result.adapter_label for result in results] == ["first", "second"]
    assert "disabled" in fake_registry
    assert fake_registry["disabled"].seen_markers == []


def test_poll_once_can_poll_disabled_adapter_by_explicit_label(
    fake_registry: dict[str, FakeAdapter],
) -> None:
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="fake_source",
                    source_label="disabled",
                    enabled=False,
                ),
            ]
        )
    )

    result = manager.poll_once("disabled")

    assert result.adapter_label == "disabled"
    assert [item.content for item in result.items] == ["disabled item"]
    assert fake_registry["disabled"].seen_markers == [None]


def test_poll_specific_adapter_wraps_adapter_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(_ADAPTER_REGISTRY, "failing_source", lambda config: FailingAdapter())
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(adapter_type="failing_source", source_label="failing"),
            ]
        )
    )

    result = manager.poll("failing")[0]

    assert result.items == []
    assert result.adapter_label == "failing"
    assert result.errors[0].adapter_label == "failing"
    assert result.errors[0].url is None
    assert result.errors[0].error == "adapter broke"


def test_pending_arch_adapter_error_is_reported_in_result() -> None:
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="rss",
                    source_label="feed",
                    params={"feed_url": "https://example.com/feed.xml"},
                )
            ]
        )
    )

    result = manager.poll_once("feed")

    assert result.items == []
    assert result.adapter_label == "feed"
    assert result.errors[0].adapter_label == "feed"
    assert result.errors[0].url is None
    assert result.errors[0].error == "rss adapter is not implemented"


def test_private_registry_builds_with_concrete_factory_override() -> None:
    def factory(config: AdapterConfig) -> FakeAdapter:
        return FakeAdapter(
            AdapterPollResult(
                items=[
                    ContentItem(
                        content=config.source_label,
                        source=config.adapter_type,
                        timestamp=datetime(2026, 1, 1),
                    )
                ],
                next_marker=1,
            )
        )

    registry = _build_adapter_registry({"rss": factory})
    adapter = registry.create(
        AdapterConfig(
            adapter_type="rss",
            source_label="feed",
            params={"feed_url": "https://example.com/feed.xml"},
        )
    )

    assert adapter.poll(None).items[0].content == "feed"


def test_private_registry_rejects_invalid_factory() -> None:
    with pytest.raises(TypeError, match="must be callable"):
        AdapterRegistry({"rss": None})  # type: ignore[arg-type]


def test_adapter_error_from_exception_preserves_url_context() -> None:
    error = adapter_error_from_exception(
        RuntimeError("bad fetch"), url="https://example.com/bad"
    )

    assert error.error == "bad fetch"
    assert error.url == "https://example.com/bad"
