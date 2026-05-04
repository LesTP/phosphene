"""Local corpus source adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from phosphene.source_ingestion.adapters import (
    AdapterItemError,
    AdapterPollResult,
    LastSeenMarker,
)
from phosphene.source_ingestion.normalization import (
    build_content_item,
    fetch_url_text,
    html_to_text,
    is_marker_newer,
)
from phosphene.source_ingestion.types import AdapterConfig, ContentItem, IngestionConfig

_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_HTML_SUFFIXES = {".html", ".htm"}
_JSON_SUFFIXES = {".json", ".js"}
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


class CorpusLiveJournalAdapter:
    """Import LiveJournal-style HTML exports from a local path."""

    def __init__(self, config: AdapterConfig, ingestion_config: IngestionConfig) -> None:
        self.config = config
        self.ingestion_config = ingestion_config
        self.archive_path = Path(str(config.params["archive_path"]))

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        return _poll_local_corpus(
            archive_path=self.archive_path,
            source="corpus_livejournal",
            allowed_suffixes=_HTML_SUFFIXES,
            parse_document=_parse_html_document,
            last_seen_marker=last_seen_marker,
            ingestion_config=self.ingestion_config,
        )


class CorpusTwitterAdapter:
    """Import Twitter/X JSON archive exports from a local path."""

    def __init__(self, config: AdapterConfig, ingestion_config: IngestionConfig) -> None:
        self.config = config
        self.ingestion_config = ingestion_config
        self.archive_path = Path(str(config.params["archive_path"]))

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        try:
            paths = _iter_archive_files(self.archive_path, _JSON_SUFFIXES)
        except OSError as exc:
            return AdapterPollResult(
                errors=[AdapterItemError(error=str(exc), url=str(self.archive_path))],
                next_marker=last_seen_marker,
            )

        items: list[ContentItem] = []
        errors: list[AdapterItemError] = []
        newest_marker = last_seen_marker

        for path in paths:
            try:
                tweets = _load_twitter_tweets(path)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                errors.append(AdapterItemError(error=str(exc), url=str(path)))
                continue

            for index, tweet in enumerate(tweets):
                timestamp = _twitter_timestamp(tweet) or _file_timestamp(path)
                marker = _document_marker(path, timestamp, index)
                if not is_marker_newer(marker, last_seen_marker):
                    continue

                item, item_errors = _twitter_item(
                    tweet=tweet,
                    path=path,
                    timestamp=timestamp,
                    ingestion_config=self.ingestion_config,
                )
                items.append(item)
                errors.extend(item_errors)
                if is_marker_newer(marker, newest_marker):
                    newest_marker = marker

        return AdapterPollResult(items=items, errors=errors, next_marker=newest_marker)


class CorpusConversationsAdapter:
    """Import conversation history exports from local JSON or text files."""

    def __init__(self, config: AdapterConfig, ingestion_config: IngestionConfig) -> None:
        self.config = config
        self.ingestion_config = ingestion_config
        self.archive_path = Path(str(config.params["archive_path"]))
        self.file_format = str(config.params["format"])

    def poll(self, last_seen_marker: LastSeenMarker) -> AdapterPollResult:
        if self.file_format == "json":
            return _poll_json_conversations(
                archive_path=self.archive_path,
                last_seen_marker=last_seen_marker,
                ingestion_config=self.ingestion_config,
            )

        return _poll_local_corpus(
            archive_path=self.archive_path,
            source="corpus_conversations",
            allowed_suffixes=_TEXT_SUFFIXES,
            parse_document=_parse_text_conversation_document,
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


def corpus_livejournal_adapter_factory(
    config: AdapterConfig, ingestion_config: IngestionConfig
) -> CorpusLiveJournalAdapter:
    return CorpusLiveJournalAdapter(config, ingestion_config)


def corpus_twitter_adapter_factory(
    config: AdapterConfig, ingestion_config: IngestionConfig
) -> CorpusTwitterAdapter:
    return CorpusTwitterAdapter(config, ingestion_config)


def corpus_conversations_adapter_factory(
    config: AdapterConfig, ingestion_config: IngestionConfig
) -> CorpusConversationsAdapter:
    return CorpusConversationsAdapter(config, ingestion_config)


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


def _parse_text_conversation_document(path: Path) -> _CorpusDocument:
    content = path.read_text(encoding="utf-8")
    return _CorpusDocument(
        path=path,
        timestamp=_file_timestamp(path),
        title=path.stem,
        author=None,
        parts=_split_text_parts(content),
        linked_urls=[],
    )


def _poll_json_conversations(
    *,
    archive_path: Path,
    last_seen_marker: LastSeenMarker,
    ingestion_config: IngestionConfig,
) -> AdapterPollResult:
    try:
        paths = _iter_archive_files(archive_path, {".json"})
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
            conversations = _load_conversations(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(AdapterItemError(error=str(exc), url=str(path)))
            continue

        for index, message in enumerate(_iter_conversation_messages(conversations)):
            timestamp = message["timestamp"] or _file_timestamp(path)
            marker = _document_marker(path, timestamp, index)
            if not is_marker_newer(marker, last_seen_marker):
                continue
            items.append(
                build_content_item(
                    content=message["content"],
                    source="corpus_conversations",
                    timestamp=timestamp,
                    config=ingestion_config,
                    url=str(path),
                    title=message["title"],
                    author=message["author"],
                )
            )
            if is_marker_newer(marker, newest_marker):
                newest_marker = marker

    return AdapterPollResult(items=items, errors=errors, next_marker=newest_marker)


def _load_json_or_js(path: Path) -> object:
    content = path.read_text(encoding="utf-8")
    stripped = content.strip()
    if not stripped:
        raise ValueError("archive file is empty")
    if stripped[0] not in "[{":
        starts = [index for index in (stripped.find("["), stripped.find("{")) if index >= 0]
        if not starts:
            raise ValueError("archive file does not contain JSON")
        stripped = stripped[min(starts) :]
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(stripped)
    return value


def _load_twitter_tweets(path: Path) -> list[dict]:
    data = _load_json_or_js(path)
    tweets: list[dict] = []
    seen: set[str] = set()
    for value in _walk_json(data):
        if isinstance(value, dict) and "tweet" in value and isinstance(value["tweet"], dict):
            tweet = value["tweet"]
        elif isinstance(value, dict) and (
            "full_text" in value or "created_at" in value or "entities" in value
        ):
            tweet = value
        else:
            continue

        identity = str(tweet.get("id_str") or tweet.get("id") or id(tweet))
        if identity in seen:
            continue
        seen.add(identity)
        tweets.append(tweet)
    if not tweets:
        raise ValueError("no tweets found in archive")
    return tweets


def _load_conversations(path: Path) -> object:
    data = _load_json_or_js(path)
    if not isinstance(data, dict | list):
        raise ValueError("conversation archive must be an object or list")
    return data


def _iter_conversation_messages(data: object) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []

    def visit(value: object, title: str | None = None) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item, title)
            return
        if not isinstance(value, dict):
            return

        next_title = _string_value(value, "title", "name", "conversation_title") or title
        nested = value.get("messages") or value.get("chat_messages") or value.get("mapping")
        if nested is not None:
            visit(nested, next_title)

        content = _message_content(value)
        if not content:
            return
        messages.append(
            {
                "content": content,
                "title": next_title,
                "author": _message_author(value),
                "timestamp": _message_timestamp(value),
            }
        )

    visit(data)
    return messages


def _walk_json(value: object) -> list[object]:
    values = [value]
    if isinstance(value, dict):
        for child in value.values():
            values.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_json(child))
    return values


def _twitter_item(
    *,
    tweet: dict,
    path: Path,
    timestamp: datetime,
    ingestion_config: IngestionConfig,
) -> tuple[ContentItem, list[AdapterItemError]]:
    text = _tweet_text(tweet)
    links = _tweet_urls(tweet)
    author = _tweet_author(tweet)
    annotation = _strip_urls(text).strip() or None
    title = f"Tweet {tweet.get('id_str') or tweet.get('id') or path.stem}"
    errors: list[AdapterItemError] = []

    if links:
        url = links[0]
        try:
            fetched = fetch_url_text(
                url, ingestion_config.fetch_timeout.total_seconds()
            )
        except Exception as exc:  # noqa: BLE001 - archive link failures are per-item.
            content = annotation or text or url
            title = title if annotation else f"Linked tweet {url}"
            errors.append(AdapterItemError(error=str(exc), url=url))
            linked_urls = links
        else:
            content = fetched.text or annotation or text or url
            title = fetched.title or title
            linked_urls = [*links, *(fetched.linked_urls or [])]

        return (
            build_content_item(
                content=content,
                source="corpus_twitter",
                timestamp=timestamp,
                config=ingestion_config,
                url=url,
                linked_urls=linked_urls,
                title=title,
                author=author,
                human_annotation=annotation,
            ),
            errors,
        )

    content = annotation or text
    if _is_uncommented_retweet(tweet, text):
        title = f"Retweet {tweet.get('id_str') or tweet.get('id') or path.stem}"
    return (
        build_content_item(
            content=content,
            source="corpus_twitter",
            timestamp=timestamp,
            config=ingestion_config,
            url=None,
            linked_urls=[],
            title=title,
            author=author,
            human_annotation=None if _is_uncommented_retweet(tweet, text) else annotation,
        ),
        errors,
    )


def _tweet_text(tweet: dict) -> str:
    value = tweet.get("full_text") or tweet.get("text") or tweet.get("tweet_text") or ""
    return str(value).strip()


def _tweet_urls(tweet: dict) -> list[str]:
    urls: list[str] = []
    entity_short_urls: set[str] = set()
    entities = tweet.get("entities")
    if isinstance(entities, dict):
        for entry in entities.get("urls") or []:
            if not isinstance(entry, dict):
                continue
            short_url = entry.get("url")
            if short_url:
                entity_short_urls.add(str(short_url))
            url = entry.get("expanded_url") or short_url
            if url:
                urls.append(str(url))
    urls.extend(
        url
        for url in re.findall(r"https?://\S+", _tweet_text(tweet))
        if url.rstrip(".,;:!?)]}") not in entity_short_urls
    )

    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = url.rstrip(".,;:!?)]}")
        if normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _tweet_author(tweet: dict) -> str | None:
    user = tweet.get("user") or tweet.get("account")
    if isinstance(user, dict):
        return _string_value(user, "screen_name", "name", "username")
    return _string_value(tweet, "screen_name", "username", "author")


def _twitter_timestamp(tweet: dict) -> datetime | None:
    created_at = _string_value(tweet, "created_at", "createdAt", "timestamp")
    parsed = _parse_datetime(created_at)
    if parsed is not None:
        return parsed
    if created_at:
        try:
            return datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").astimezone(
                timezone.utc
            )
        except ValueError:
            return None
    return None


def _is_uncommented_retweet(tweet: dict, text: str) -> bool:
    return bool(tweet.get("retweeted_status")) or text.startswith("RT @")


def _strip_urls(text: str) -> str:
    return re.sub(r"https?://\S+", "", text).strip()


def _message_content(message: dict) -> str | None:
    value = message.get("content") or message.get("text") or message.get("message")
    if isinstance(value, list):
        parts: list[str] = []
        for part in value:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if text:
                    parts.append(str(text))
        value = " ".join(parts)
    if isinstance(value, dict):
        value = value.get("text") or value.get("content")
    if not value:
        return None
    return str(value).strip() or None


def _message_author(message: dict) -> str | None:
    author = message.get("author") or message.get("role") or message.get("sender")
    if isinstance(author, dict):
        return _string_value(author, "name", "role", "username")
    return str(author) if author else None


def _message_timestamp(message: dict) -> datetime | None:
    value = _string_value(
        message, "timestamp", "created_at", "createdAt", "date", "datetime"
    )
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    numeric = message.get("create_time") or message.get("created")
    if isinstance(numeric, int | float):
        return datetime.fromtimestamp(float(numeric), timezone.utc)
    return None


def _string_value(value: dict, *keys: str) -> str | None:
    for key in keys:
        item = value.get(key)
        if item is not None and item != "":
            return str(item)
    return None


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
