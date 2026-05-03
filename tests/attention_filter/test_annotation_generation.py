import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping

import numpy as np
import pytest

from phosphene.attention_filter import (
    AttentionFilterConfig,
    ContentItem,
    InvalidScoreError,
)
from phosphene.attention_filter.filter import (
    _CachedClusterReference,
    _FrictionPreparation,
    _GeneratedAnnotation,
    _IncomingAssertion,
    _ItemEvaluation,
    _ItemRetrievalContext,
    _MemoryStructuralEvaluation,
    _SimilarNoteContext,
    _generate_annotation,
    _generate_annotations,
    _parse_annotation_generation_payload,
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


def make_evaluation(content: str = "incoming text") -> _ItemEvaluation:
    item = ContentItem(
        content=content,
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
        cluster_group="cluster-a",
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
    retrieval = _ItemRetrievalContext(
        item=item,
        embedding=np.array([1.0, 0.0]),
        similar_notes=(similar_note,),
    )
    structural = _MemoryStructuralEvaluation(
        scores={"link_density": 0.5, "unresolvedness_affinity": 0.35},
        structure_score=0.425,
        connections=("note-a",),
        friction_target="note-a",
    )
    incoming_assertions = (_IncomingAssertion("Incoming claim.", 0.8),)
    friction_preparation = _FrictionPreparation(
        incoming_assertions=incoming_assertions,
        cached_clusters=(
            _CachedClusterReference(
                cluster_group="cluster-a",
                note_ids=("note-a",),
                max_similarity=0.82,
                assertion_cache_path="tier2/cluster-a.json",
            ),
        ),
    )
    return _ItemEvaluation(
        retrieval=retrieval,
        structural=structural,
        prompt_scores={"precision_surplus": 0.9},
        prompt_score=0.9,
        incoming_assertions=incoming_assertions,
        friction_preparation=friction_preparation,
        composite_score=0.71,
        prompt_weight=0.65,
        structure_weight=0.35,
    )


def test_annotation_generation_constructs_request_and_propagates_tier_and_config() -> None:
    llm_config = object()
    llm_tier = FakeTier("quality")
    calls: list[tuple[list[Mapping[str, str]], object, object]] = []

    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        calls.append((messages, config, tier))
        return '{"annotation": "Retained for precise claims and live friction."}'

    annotation = _generate_annotation(
        make_evaluation(),
        make_config(llm_config=llm_config, llm_tier=llm_tier),
        llm_complete_callable=fake_complete,
    )

    assert annotation == "Retained for precise claims and live friction."
    assert len(calls) == 1
    messages, seen_config, seen_tier = calls[0]
    assert seen_config is llm_config
    assert seen_tier is llm_tier
    assert [message["role"] for message in messages] == ["user"]

    payload = json.loads(messages[0]["content"])
    assert payload["task"] == "generate_attention_filter_annotation"
    assert payload["content_item"]["content"] == "incoming text"
    assert payload["content_item"]["source"] == "rss"
    assert payload["content_item"]["url"] == "https://example.test/item"
    assert payload["content_item"]["linked_urls"] == ["https://example.test/linked"]
    assert payload["scores"]["composite"] == 0.71
    assert payload["scores"]["prompt"] == 0.9
    assert payload["scores"]["structure"] == 0.425
    assert payload["scores"]["prompt_weight"] == 0.65
    assert payload["scores"]["structure_weight"] == 0.35
    assert payload["scores"]["prompt_criteria"] == {"precision_surplus": 0.9}
    assert payload["scores"]["structure_criteria"] == {
        "link_density": 0.5,
        "unresolvedness_affinity": 0.35,
    }
    assert payload["friction"]["target"] == "note-a"
    assert payload["friction"]["incoming_assertions"] == [
        {"text": "Incoming claim.", "confidence": 0.8}
    ]
    assert payload["friction"]["cached_clusters"][0]["cluster_group"] == "cluster-a"
    assert payload["connections"] == ["note-a"]
    assert payload["similar_notes"][0]["note_id"] == "note-a"
    assert payload["similar_notes"][0]["metadata"]["content"] == (
        "A related stored observation."
    )


def test_annotation_parser_normalizes_text() -> None:
    assert (
        _parse_annotation_generation_payload(
            '{"annotation": "  Retained\\nfor\\tprecise   friction.  "}'
        )
        == "Retained for precise friction."
    )


@pytest.mark.parametrize(
    "payload",
    [
        "not-json",
        "[]",
        "{}",
        '{"annotation": 3}',
        '{"annotation": true}',
        '{"annotation": ""}',
        '{"annotation": "   "}',
    ],
)
def test_annotation_parser_rejects_invalid_payloads(payload: str) -> None:
    with pytest.raises(InvalidScoreError):
        _parse_annotation_generation_payload(payload)


def test_annotation_generation_propagates_llm_errors_unchanged() -> None:
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
        _generate_annotation(
            make_evaluation(),
            make_config(),
            llm_complete_callable=fake_complete,
        )

    assert exc_info.value is failure


def test_generate_annotations_wraps_each_accepted_candidate() -> None:
    evaluations = (
        make_evaluation("first"),
        make_evaluation("second"),
    )

    def fake_complete(
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> str:
        content = json.loads(messages[0]["content"])["content_item"]["content"]
        return json.dumps({"annotation": f"Annotation for {content}."})

    generated = _generate_annotations(
        evaluations,
        make_config(),
        llm_complete_callable=fake_complete,
    )

    assert generated == (
        _GeneratedAnnotation(evaluations[0], "Annotation for first."),
        _GeneratedAnnotation(evaluations[1], "Annotation for second."),
    )
