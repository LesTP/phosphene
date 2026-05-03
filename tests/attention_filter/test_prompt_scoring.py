import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping

import pytest

from phosphene.attention_filter import (
    AttentionFilterConfig,
    ContentItem,
    FilterCriterion,
    InvalidScoreError,
)
from phosphene.attention_filter.filter import (
    _ItemRetrievalContext,
    _SimilarNoteContext,
    _parse_prompt_score_payload,
    _score_prompt_criteria,
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
        content="The essay makes a precise claim with concrete evidence.",
        source="rss",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        url="https://example.test/item",
        linked_urls=["https://example.test/linked"],
    )
    note = FakeNote(
        note_id="note-a",
        unresolvedness=0.7,
        title="Prior note",
        tags=["precision"],
        source="corpus",
        content="A related stored observation.",
    )
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


def test_prompt_scoring_constructs_request_and_propagates_tier_and_config() -> None:
    llm_config = object()
    llm_tier = FakeTier("quality")
    calls: list[tuple[list[Mapping[str, str]], object, object]] = []
    criteria = [
        FilterCriterion(
            name="precision_surplus",
            description="Score precision.",
            weight=2.0,
        )
    ]

    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        calls.append((messages, config, tier))
        return '{"scores": {"precision_surplus": 0.75}}'

    scores = _score_prompt_criteria(
        make_context(),
        make_config(
            prompt_criteria=criteria,
            llm_config=llm_config,
            llm_tier=llm_tier,
        ),
        llm_complete_callable=fake_complete,
    )

    assert scores == {"precision_surplus": 0.75}
    assert len(calls) == 1
    messages, seen_config, seen_tier = calls[0]
    assert seen_config is llm_config
    assert seen_tier is llm_tier
    assert [message["role"] for message in messages] == ["user"]

    payload = json.loads(messages[0]["content"])
    assert payload["task"] == "score_attention_filter_prompt_criteria"
    assert payload["criteria"] == [
        {
            "name": "precision_surplus",
            "description": "Score precision.",
            "weight": 2.0,
        }
    ]
    assert payload["content_item"]["content"].startswith("The essay makes")
    assert payload["content_item"]["source"] == "rss"
    assert payload["content_item"]["url"] == "https://example.test/item"
    assert payload["content_item"]["linked_urls"] == ["https://example.test/linked"]
    assert payload["similar_notes"][0]["note_id"] == "note-a"
    assert payload["similar_notes"][0]["similarity"] == 0.82
    assert payload["similar_notes"][0]["metadata"]["content"] == (
        "A related stored observation."
    )


def test_prompt_scoring_parses_multiple_scores() -> None:
    criteria = [
        FilterCriterion(name="precision_surplus", description="Precision"),
        FilterCriterion(name="custom", description="Custom"),
    ]

    scores = _parse_prompt_score_payload(
        '{"scores": {"precision_surplus": 1, "custom": 0.25}}',
        criteria,
    )

    assert scores == {"precision_surplus": 1.0, "custom": 0.25}


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        "{}",
        '{"scores": []}',
        '{"scores": {"precision_surplus": "high"}}',
        '{"scores": {"precision_surplus": true}}',
        '{"scores": {"precision_surplus": -0.1}}',
        '{"scores": {"precision_surplus": 1.1}}',
        '{"scores": {"other": 0.5}}',
    ],
)
def test_prompt_scoring_rejects_invalid_payloads(payload: str) -> None:
    with pytest.raises(InvalidScoreError):
        _parse_prompt_score_payload(
            payload,
            [FilterCriterion(name="precision_surplus", description="Precision")],
        )


def test_prompt_scoring_propagates_llm_errors_unchanged() -> None:
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
        _score_prompt_criteria(
            make_context(),
            make_config(),
            llm_complete_callable=fake_complete,
        )

    assert exc_info.value is failure


def test_prompt_scoring_skips_llm_when_no_criteria() -> None:
    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        raise AssertionError("LLM should not be called")

    scores = _score_prompt_criteria(
        make_context(),
        make_config(prompt_criteria=[]),
        llm_complete_callable=fake_complete,
    )

    assert scores == {}
