from datetime import datetime

import pytest

from phosphene.source_ingestion.normalization import (
    build_content_item,
    extract_urls,
    truncate_content,
)
from phosphene.source_ingestion.types import IngestionConfig


def test_extract_urls_preserves_order_and_deduplicates() -> None:
    text = (
        "See https://example.com/a, then https://example.com/b?q=1. "
        "Again: https://example.com/a"
    )

    assert extract_urls(text) == [
        "https://example.com/a",
        "https://example.com/b?q=1",
    ]


def test_extract_urls_ignores_empty_text() -> None:
    assert extract_urls(None) == []
    assert extract_urls("") == []


def test_truncate_content_applies_configured_character_limit() -> None:
    assert truncate_content("abcdef", 4) == "abcd"
    assert truncate_content("abcdef", 6) == "abcdef"
    assert truncate_content("abcdef", 0) == ""


def test_truncate_content_rejects_negative_limit() -> None:
    with pytest.raises(ValueError, match="max_content_length"):
        truncate_content("abcdef", -1)


def test_build_content_item_truncates_content_and_preserves_metadata() -> None:
    timestamp = datetime(2026, 1, 2, 3, 4, 5)

    item = build_content_item(
        content="abcdef https://example.com/content",
        source="human_share",
        timestamp=timestamp,
        config=IngestionConfig(adapters=[], max_content_length=6),
        url="https://example.com/source",
        linked_urls=["https://example.com/source"],
        title="Title",
        author="Author",
        human_annotation="note https://example.com/annotation",
    )

    assert item.content == "abcdef"
    assert item.source == "human_share"
    assert item.timestamp is timestamp
    assert item.url == "https://example.com/source"
    assert item.linked_urls == [
        "https://example.com/source",
        "https://example.com/content",
        "https://example.com/annotation",
    ]
    assert item.title == "Title"
    assert item.author == "Author"
    assert item.human_annotation == "note https://example.com/annotation"


def test_build_content_item_can_disable_link_extraction() -> None:
    item = build_content_item(
        content="https://example.com/content",
        source="rss",
        timestamp=datetime(2026, 1, 1),
        config=IngestionConfig(adapters=[], extract_links=False),
        linked_urls=["https://example.com/explicit"],
    )

    assert item.linked_urls == ["https://example.com/explicit"]


def test_build_content_item_deduplicates_explicit_and_extracted_links() -> None:
    item = build_content_item(
        content="Read https://example.com/a and https://example.com/b",
        source="rss",
        timestamp=datetime(2026, 1, 1),
        config=IngestionConfig(adapters=[]),
        linked_urls=["https://example.com/b", "https://example.com/a"],
        human_annotation="same https://example.com/a",
    )

    assert item.linked_urls == [
        "https://example.com/b",
        "https://example.com/a",
    ]
