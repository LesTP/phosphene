"""Local corpus source adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

from phosphene.source_ingestion.adapters import (
    AdapterItemError,
    AdapterPollResult,
    LastSeenMarker,
)
from phosphene.source_ingestion.normalization import (
    build_content_item,
    html_to_text,
    is_marker_newer,
)
from phosphene.source_ingestion.types import AdapterConfig, ContentItem, IngestionConfig

_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_HTML_SUFFIXES = {".html", ".htm"}
_TEXT_SUFFIXES = {".txt", ".text"}
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_HTML_META_RE = re.compile(
    r"<meta\s+[^>]*(?:name|property)=[\"'](?:date|article:published_time|pubdate)[\"'][^>]*>",
    re.IGNORECASE,
)
_HTML_CONTENT_RE = re.compile(r"content=[\"']([^\"']+)[\"']", re.IGNORECASE)
_HTML_TIME_RE = re.compile(
    r"<time\s+[^>]*datetime=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE
)


@dataclass
class _CorpusDocument:
    path: Path
    timestamp: datetime
    title: str | None
    author: str | None
    parts: list[str]
    linked_urls: list[str]


class CorpusTextAdapter:
    """Import plain text corpus files from a local path."""

    def __init__(self, config: AdapterConfig, ingestion_config: IngestionConfig) -> None:
        self.config = config
        self.ingestion_config = ingestion_config
        self.archive_path = Path(str(config.params["archive_path"]))

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        return _poll_local_corpus(
            archive_path=self.archive_path,
            source="corpus_text",
            allowed_suffixes=_TEXT_SUFFIXES,
            parse_document=_parse_text_document,
            last_seen_marker=last_seen_marker,
            ingestion_config=self.ingestion_config,
        )


class CorpusBlogAdapter:
    """Import markdown or HTML blog archives from a local path."""

    def __init__(self, config: AdapterConfig, ingestion_config: IngestionConfig) -> None:
        self.config = config
        self.ingestion_config = ingestion_config
        self.archive_path = Path(str(config.params["archive_path"]))
        self.file_format = str(config.params["format"])

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        if self.file_format == "markdown":
            allowed_suffixes = _MARKDOWN_SUFFIXES
            parser = _parse_markdown_document
        else:
            allowed_suffixes = _HTML_SUFFIXES
            parser = _parse_html_document

        return _poll_local_corpus(
            archive_path=self.archive_path,
            source="corpus_blog",
            allowed_suffixes=allowed_suffixes,
            parse_document=parser,
            last_seen_marker=last_seen_marker,
            ingestion_config=self.ingestion_config,
        )


def corpus_text_adapter_factory(
    config: AdapterConfig, ingestion_config: IngestionConfig
) -> CorpusTextAdapter:
    return CorpusTextAdapter(config, ingestion_config)


def corpus_blog_adapter_factory(
    config: AdapterConfig, ingestion_config: IngestionConfig
) -> CorpusBlogAdapter:
    return CorpusBlogAdapter(config, ingestion_config)


def _poll_local_corpus(
    *,
    archive_path: Path,
    source: str,
    allowed_suffixes: set[str],
    parse_document: Callable[[Path], _CorpusDocument],
    last_seen_marker: LastSeenMarker,
    ingestion_config: IngestionConfig,
) -> AdapterPollResult:
    try:
        paths = _iter_archive_files(archive_path, allowed_suffixes)
    except OSError as exc:
        return AdapterPollResult(
            errors=[AdapterItemError(error=str(exc), url=str(archive_path))],
            next_marker=last_seen_marker,
        )

    items: list[ContentItem] = []
    errors: list[AdapterItemError] = []
    newest_marker = last_seen_marker

    for path in paths:
        try:
            document = parse_document(path)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(AdapterItemError(error=str(exc), url=str(path)))
            continue

        for index, part in enumerate(document.parts):
            marker = _document_marker(document.path, document.timestamp, index)
            if not is_marker_newer(marker, last_seen_marker):
                continue
            items.append(
                build_content_item(
                    content=part,
                    source=source,
                    timestamp=document.timestamp,
                    config=ingestion_config,
                    url=str(document.path),
                    linked_urls=document.linked_urls,
                    title=document.title,
                    author=document.author,
                )
            )
            if is_marker_newer(marker, newest_marker):
                newest_marker = marker

    return AdapterPollResult(items=items, errors=errors, next_marker=newest_marker)


def _iter_archive_files(archive_path: Path, allowed_suffixes: set[str]) -> list[Path]:
    if not archive_path.exists():
        raise FileNotFoundError(f"archive path not found: {archive_path}")
    if archive_path.is_file():
        return [archive_path] if archive_path.suffix.lower() in allowed_suffixes else []
    if not archive_path.is_dir():
        raise OSError(f"archive path is not a file or directory: {archive_path}")
    return sorted(
        path
        for path in archive_path.rglob("*")
        if path.is_file()
        and not any(part.startswith(".") for part in path.parts)
        and path.suffix.lower() in allowed_suffixes
    )


def _parse_text_document(path: Path) -> _CorpusDocument:
    content = path.read_text(encoding="utf-8")
    return _CorpusDocument(
        path=path,
        timestamp=_file_timestamp(path),
        title=path.stem,
        author=None,
        parts=_split_text_parts(content),
        linked_urls=[],
    )


def _parse_markdown_document(path: Path) -> _CorpusDocument:
    content = path.read_text(encoding="utf-8")
    metadata, body = _split_frontmatter(content)
    title = metadata.get("title") or _first_markdown_heading(body) or path.stem
    timestamp = _parse_datetime(metadata.get("date")) or _file_timestamp(path)
    author = metadata.get("author")
    body = _HEADING_RE.sub("", body).strip() if metadata.get("title") else body
    return _CorpusDocument(
        path=path,
        timestamp=timestamp,
        title=title,
        author=author,
        parts=_split_text_parts(_strip_markdown_markup(body)),
        linked_urls=[],
    )


def _parse_html_document(path: Path) -> _CorpusDocument:
    content = path.read_text(encoding="utf-8")
    extracted = html_to_text(content)
    timestamp = _html_datetime(content) or _file_timestamp(path)
    return _CorpusDocument(
        path=path,
        timestamp=timestamp,
        title=extracted.title or path.stem,
        author=None,
        parts=_split_text_parts(extracted.text),
        linked_urls=extracted.linked_urls or [],
    )


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}, content

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip("\"'")
    return metadata, content[match.end() :]


def _first_markdown_heading(content: str) -> str | None:
    match = _HEADING_RE.search(content)
    return match.group(1).strip() if match else None


def _strip_markdown_markup(content: str) -> str:
    content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content = re.sub(r"`([^`]+)`", r"\1", content)
    content = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", content)
    content = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 \2", content)
    content = re.sub(r"^\s{0,3}#{1,6}\s+", "", content, flags=re.MULTILINE)
    content = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", content)
    return content.strip()


def _split_text_parts(content: str) -> list[str]:
    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"\n\s*\n+", content)
    ]
    return [paragraph for paragraph in paragraphs if paragraph]


def _file_timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _html_datetime(content: str) -> datetime | None:
    time_match = _HTML_TIME_RE.search(content)
    if time_match:
        parsed = _parse_datetime(time_match.group(1))
        if parsed is not None:
            return parsed

    meta_match = _HTML_META_RE.search(content)
    if not meta_match:
        return None
    content_match = _HTML_CONTENT_RE.search(meta_match.group(0))
    if not content_match:
        return None
    return _parse_datetime(content_match.group(1))


def _document_marker(path: Path, timestamp: datetime, index: int) -> str:
    try:
        stable_path = str(path.resolve())
    except OSError:
        stable_path = str(path)
    return f"{timestamp.timestamp():020.6f}:{stable_path}:{index:06d}"
