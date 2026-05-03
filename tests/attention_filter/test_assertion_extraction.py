import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping

import pytest

from phosphene.attention_filter import (
    AttentionFilterConfig,
    ContentItem,
    InvalidScoreError,
)
from phosphene.attention_filter.filter import (
    _ItemRetrievalContext,
    _SimilarNoteContext,
    _extract_incoming_assertions,
    _parse_assertion_extraction_payload,
)


@dataclass
class FakeTier:
    name: str


@dataclass
class FakeNote:
    note_id: str
    unresolvedness: float
    tier: int = 1
    title: str = "title"
    importance: float = 0.0
    link_count: int = 0
    tags: list[str] = field(default_factory=list)
    source: str | None = None
    friction_target: str | None = None
    cluster_group: str | None = None
    content: str = "prior note content"


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def make_context() -> _ItemRetrievalContext:
    item = ContentItem(
        content="Local-first tools fail when synchronization is treated as storage.",
        source="rss",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        url="https://example.test/item",
        linked_urls=["https://example.test/linked"],
    )
    note = FakeNote(note_id="note-a", unresolvedness=0.7)
    similar_note = _SimilarNoteContext(
        note_id=note.note_id,
        similarity=0.82,
        unresolvedness=note.unresolvedness,
        metadata={
            "tier": note.tier,
            "title": note.title,
            "importance": note.importance,
            "link_count": note.link_count,
            "tags": note.tags,
            "source": note.source,
            "friction_target": note.friction_target,
            "cluster_group": note.cluster_group,
            "content": note.content,
        },
    )
    return _ItemRetrievalContext(
        item=item,
        embedding=object(),
        similar_notes=(similar_note,),
    )


def test_assertion_extraction_constructs_request_and_propagates_tier_and_config() -> None:
    llm_config = object()
    assertion_tier = FakeTier("commodity")
    calls: list[tuple[list[Mapping[str, str]], object, object]] = []

    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        calls.append((messages, config, tier))
        return '{"assertions": [{"text": "Sync is not storage.", "confidence": 0.8}]}'

    assertions = _extract_incoming_assertions(
        make_context(),
        make_config(
            llm_config=llm_config,
            assertion_extraction_tier=assertion_tier,
        ),
        llm_complete_callable=fake_complete,
    )

    assert len(assertions) == 1
    assert assertions[0].text == "Sync is not storage."
    assert assertions[0].confidence == pytest.approx(0.8)
    assert len(calls) == 1
    messages, seen_config, seen_tier = calls[0]
    assert seen_config is llm_config
    assert seen_tier is assertion_tier
    assert [message["role"] for message in messages] == ["user"]

    payload = json.loads(messages[0]["content"])
    assert payload["task"] == "extract_attention_filter_incoming_assertions"
    assert payload["content_item"]["content"].startswith("Local-first tools")
    assert payload["content_item"]["source"] == "rss"
    assert payload["content_item"]["url"] == "https://example.test/item"
    assert payload["content_item"]["linked_urls"] == ["https://example.test/linked"]


def test_assertion_extraction_handles_empty_and_noisy_extraction() -> None:
    assertions = _parse_assertion_extraction_payload(
        json.dumps(
            {
                "assertions": [
                    {"text": "  First claim.  ", "confidence": 1},
                    {"text": ""},
                    {"claim": "Claim alias is normalized.", "confidence": 0.25},
                    {"text": "   "},
                ]
            }
        )
    )

    assert [assertion.text for assertion in assertions] == [
        "First claim.",
        "Claim alias is normalized.",
    ]
    assert [assertion.confidence for assertion in assertions] == [1.0, 0.25]
    assert _parse_assertion_extraction_payload('{"assertions": []}') == ()


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        "{}",
        '{"assertions": {}}',
        '{"assertions": ["claim"]}',
        '{"assertions": [{"text": 3}]}',
        '{"assertions": [{"text": "claim", "confidence": "high"}]}',
        '{"assertions": [{"text": "claim", "confidence": true}]}',
        '{"assertions": [{"text": "claim", "confidence": -0.1}]}',
        '{"assertions": [{"text": "claim", "confidence": 1.1}]}',
    ],
)
def test_assertion_extraction_rejects_invalid_payloads(payload: str) -> None:
    with pytest.raises(InvalidScoreError):
        _parse_assertion_extraction_payload(payload)


def test_assertion_extraction_propagates_llm_errors_unchanged() -> None:
    class LLMFailure(Exception):
        pass

    failure = LLMFailure("provider unavailable")

    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        raise failure

    with pytest.raises(LLMFailure) as exc_info:
        _extract_incoming_assertions(
            make_context(),
            make_config(),
            llm_complete_callable=fake_complete,
        )

    assert exc_info.value is failure
