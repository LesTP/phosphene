"""Shared content normalization helpers for source adapters."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
import re

from phosphene.source_ingestion.types import ContentItem, IngestionConfig

_URL_RE = re.compile(r"https?://[^\s<>'\"]+")
_TRAILING_URL_PUNCTUATION = ".,;:!?)]}"


def extract_urls(text: str | None) -> list[str]:
    """Extract HTTP(S) URLs from text, preserving first-seen order."""

    if not text:
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(_TRAILING_URL_PUNCTUATION)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def truncate_content(content: str, max_content_length: int) -> str:
    if max_content_length < 0:
        raise ValueError("max_content_length must be non-negative")
    return content[:max_content_length]


def build_content_item(
    *,
    content: str,
    source: str,
    timestamp: datetime,
    config: IngestionConfig,
    url: str | None = None,
    linked_urls: Iterable[str] | None = None,
    title: str | None = None,
    author: str | None = None,
    human_annotation: str | None = None,
) -> ContentItem:
    """Assemble a normalized ContentItem without fetching external content."""

    normalized_links = list(linked_urls or [])
    if config.extract_links:
        normalized_links.extend(extract_urls(content))
        normalized_links.extend(extract_urls(human_annotation))

    deduped_links: list[str] = []
    seen: set[str] = set()
    for linked_url in normalized_links:
        if linked_url not in seen:
            seen.add(linked_url)
            deduped_links.append(linked_url)

    return ContentItem(
        content=truncate_content(content, config.max_content_length),
        source=source,
        timestamp=timestamp,
        url=url,
        linked_urls=deduped_links,
        title=title,
        author=author,
        human_annotation=human_annotation,
    )
