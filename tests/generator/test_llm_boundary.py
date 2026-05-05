import json
from dataclasses import dataclass

import pytest

from phosphene.generator import GeneratorConfig, LLMAPIError
from phosphene.generator.generator import (
    _call_generation_llm,
    _parse_generator_output_payload,
)
from phosphene.generator.types import TokenUsage


@dataclass
class FakeLLMResponse:
    content: str
    token_usage: TokenUsage


def valid_payload(
    *,
    output_mode: str = "prompted",
    is_lateral: bool = False,
    source_note_ids: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "content": "generated text",
            "intent_tag": "synthesis",
            "output_mode": output_mode,
            "importance_score": 0.72,
            "is_lateral": is_lateral,
            "source_note_ids": (
                source_note_ids if source_note_ids is not None else ["note-1"]
            ),
            "contradictions_noted": [
                {
                    "personality_note_id": "personality-1",
                    "claim_summary": "old claim",
                    "counter_evidence_ids": ["evidence-1"],
                    "counter_summary": "new evidence",
                }
            ],
        }
    )


def test_call_generation_llm_uses_generation_tier_and_preserves_token_usage() -> None:
    usage = TokenUsage(prompt_tokens=3, completion_tokens=5, total_tokens=8)
    calls = []

    def fake_complete(**kwargs: object) -> FakeLLMResponse:
        calls.append(kwargs)
        return FakeLLMResponse(content='{"content": "ok"}', token_usage=usage)

    completion = _call_generation_llm(
        [{"role": "user", "content": "{}"}],
        GeneratorConfig(llm_config="config", generation_tier="quality"),
        llm_complete_callable=fake_complete,
    )

    assert completion.content == '{"content": "ok"}'
    assert completion.token_usage == usage
    assert calls == [
        {
            "messages": [{"role": "user", "content": "{}"}],
            "config": "config",
            "tier": "quality",
        }
    ]


def test_call_generation_llm_maps_provider_failures_to_llm_api_error() -> None:
    class ProviderFailure(Exception):
        pass

    def fake_complete(**_kwargs: object) -> object:
        raise ProviderFailure("provider unavailable")

    with pytest.raises(LLMAPIError, match="generation LLM call failed") as exc_info:
        _call_generation_llm(
            [{"role": "user", "content": "{}"}],
            GeneratorConfig(llm_config=object()),
            llm_complete_callable=fake_complete,
        )

    assert isinstance(exc_info.value.__cause__, ProviderFailure)


def test_parse_generator_output_payload_preserves_usage_and_bounded_fields() -> None:
    usage = TokenUsage(prompt_tokens=7, completion_tokens=11, total_tokens=18)

    output = _parse_generator_output_payload(
        valid_payload(),
        token_usage=usage,
        default_output_mode="prompted",
        default_is_lateral=False,
        fallback_source_note_ids=["fallback-1"],
    )

    assert output.content == "generated text"
    assert output.intent_tag == "synthesis"
    assert output.output_mode == "prompted"
    assert output.importance_score == 0.72
    assert output.is_lateral is False
    assert output.source_note_ids == ["note-1"]
    assert output.contradictions_noted[0].counter_evidence_ids == ["evidence-1"]
    assert output.token_usage == usage


def test_parse_generator_output_payload_uses_fallback_source_notes_when_absent() -> None:
    output = _parse_generator_output_payload(
        valid_payload(output_mode="free_play", is_lateral=True, source_note_ids=[]),
        token_usage=TokenUsage(),
        default_output_mode="free_play",
        default_is_lateral=True,
        fallback_source_note_ids=["personality-1", "trigger-1"],
    )

    assert output.output_mode == "free_play"
    assert output.is_lateral is True
    assert output.source_note_ids == ["personality-1", "trigger-1"]


@pytest.mark.parametrize(
    ("response_text", "match"),
    [
        ("not-json", "valid JSON"),
        ("[]", "JSON object"),
        (
            json.dumps(
                {
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                }
            ),
            "content",
        ),
        (
            json.dumps(
                {
                    "content": "x",
                    "intent_tag": "synthesis",
                    "output_mode": "response",
                    "importance_score": 0.5,
                    "is_lateral": False,
                }
            ),
            "output_mode",
        ),
        (
            json.dumps(
                {
                    "content": "x",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 2.0,
                    "is_lateral": False,
                }
            ),
            "importance_score",
        ),
        (
            json.dumps(
                {
                    "content": "x",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": "no",
                }
            ),
            "is_lateral",
        ),
        (
            json.dumps(
                {
                    "content": "x",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                    "contradictions_noted": [{}],
                }
            ),
            "personality_note_id",
        ),
    ],
)
def test_parse_generator_output_payload_rejects_malformed_missing_or_invalid_output(
    response_text: str,
    match: str,
) -> None:
    with pytest.raises(LLMAPIError, match=match):
        _parse_generator_output_payload(
            response_text,
            token_usage=TokenUsage(),
            default_output_mode="prompted",
            default_is_lateral=False,
            fallback_source_note_ids=["fallback-1"],
        )
