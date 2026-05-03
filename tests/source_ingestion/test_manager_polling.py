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
    AdapterPollResult,
    LastSeenMarker,
)
from phosphene.source_ingestion.ingestion import _ADAPTER_REGISTRY


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
