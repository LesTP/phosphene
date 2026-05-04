from datetime import datetime, timezone
import os

from phosphene.source_ingestion import AdapterConfig, IngestionConfig, SourceIngestion


def test_corpus_text_imports_plain_text_paragraphs_and_advances_marker(tmp_path) -> None:
    corpus_file = tmp_path / "notes.txt"
    corpus_file.write_text(
        "First paragraph with https://example.com/a\n\nSecond paragraph", encoding="utf-8"
    )
    os.utime(corpus_file, (1_777_777_777, 1_777_777_777))

    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_text",
                    source_label="notes",
                    params={"archive_path": str(corpus_file)},
                )
            ]
        )
    )

    first = manager.poll_once("notes")
    second = manager.poll_once("notes")

    assert first.errors == []
    assert [item.content for item in first.items] == [
        "First paragraph with https://example.com/a",
        "Second paragraph",
    ]
    assert {item.source for item in first.items} == {"corpus_text"}
    assert first.items[0].title == "notes"
    assert first.items[0].url == str(corpus_file)
    assert first.items[0].linked_urls == ["https://example.com/a"]
    assert first.items[0].timestamp == datetime.fromtimestamp(
        1_777_777_777, timezone.utc
    )
    assert second.items == []
    assert second.errors == []


def test_corpus_text_imports_recursive_directory_in_stable_order(tmp_path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("B", encoding="utf-8")
    (tmp_path / "a.txt").write_text("A", encoding="utf-8")
    (tmp_path / "ignored.md").write_text("ignored", encoding="utf-8")

    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_text",
                    source_label="notes",
                    params={"archive_path": str(tmp_path)},
                )
            ]
        )
    )

    result = manager.poll_once("notes")

    assert [item.content for item in result.items] == ["A", "B"]
    assert result.errors == []


def test_corpus_blog_imports_markdown_frontmatter_metadata(tmp_path) -> None:
    post = tmp_path / "post.md"
    post.write_text(
        """---
title: Exact Post Title
date: 2026-05-01T10:30:00Z
author: Writer
---

Intro paragraph.

Second [link](https://example.com/post).
""",
        encoding="utf-8",
    )

    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_blog",
                    source_label="blog",
                    params={"archive_path": str(tmp_path), "format": "markdown"},
                )
            ]
        )
    )

    result = manager.poll_once("blog")

    assert result.errors == []
    assert [item.content for item in result.items] == [
        "Intro paragraph.",
        "Second link https://example.com/post.",
    ]
    assert result.items[0].source == "corpus_blog"
    assert result.items[0].title == "Exact Post Title"
    assert result.items[0].author == "Writer"
    assert result.items[0].timestamp == datetime(2026, 5, 1, 10, 30, tzinfo=timezone.utc)
    assert result.items[1].linked_urls == ["https://example.com/post"]


def test_corpus_blog_imports_html_title_date_and_links(tmp_path) -> None:
    post = tmp_path / "post.html"
    post.write_text(
        """
        <html>
          <head>
            <title>HTML Post</title>
            <meta name="date" content="2026-05-02T12:00:00Z">
          </head>
          <body>
            <p>First HTML paragraph.</p>
            <p>Second <a href="https://example.com/html">HTML link</a>.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )

    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_blog",
                    source_label="blog",
                    params={"archive_path": str(post), "format": "html"},
                )
            ]
        )
    )

    result = manager.poll_once("blog")

    assert result.errors == []
    assert result.items[0].title == "HTML Post"
    assert result.items[0].timestamp == datetime(2026, 5, 2, 12, tzinfo=timezone.utc)
    assert result.items[0].content == "First HTML paragraph. Second HTML link ."
    assert result.items[0].linked_urls == ["https://example.com/html"]


def test_corpus_adapter_reports_invalid_path_without_raising(tmp_path) -> None:
    missing = tmp_path / "missing"
    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_text",
                    source_label="notes",
                    params={"archive_path": str(missing)},
                )
            ]
        )
    )

    result = manager.poll_once("notes")

    assert result.items == []
    assert result.errors[0].adapter_label == "notes"
    assert result.errors[0].url == str(missing)
    assert "archive path not found" in result.errors[0].error


def test_corpus_adapter_applies_max_content_truncation(tmp_path) -> None:
    corpus_file = tmp_path / "long.txt"
    corpus_file.write_text("abcdef https://example.com/full", encoding="utf-8")

    manager = SourceIngestion(
        IngestionConfig(
            adapters=[
                AdapterConfig(
                    adapter_type="corpus_text",
                    source_label="notes",
                    params={"archive_path": str(corpus_file)},
                )
            ],
            max_content_length=6,
        )
    )

    result = manager.poll_once("notes")

    assert result.items[0].content == "abcdef"
    assert result.items[0].linked_urls == ["https://example.com/full"]
