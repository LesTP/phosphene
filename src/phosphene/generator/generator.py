"""Generator public entry point."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from phosphene.gateway import InboundMessage
from phosphene.generator.errors import EmptyPersonalityError, LLMAPIError
from phosphene.generator.types import (
    AmbientContext,
    Contradiction,
    FreePlayTrigger,
    GenerationPrompt,
    GeneratorConfig,
    GeneratorOutput,
    PersonalitySnapshot,
    TokenUsage,
)
from phosphene.memory_store import MemoryNote, NoteQuery


class _LLMCompleteCallable(Protocol):
    def __call__(
        self,
        *,
        messages: list[Mapping[str, str]],
        config: object,
        tier: object,
    ) -> object: ...


@dataclass(frozen=True)
class _LLMCompletion:
    content: str
    token_usage: TokenUsage


def _zero_token_usage() -> TokenUsage:
    return TokenUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0)


def _coerce_token_usage(raw_usage: object | None) -> TokenUsage:
    if raw_usage is None:
        return _zero_token_usage()
    if isinstance(raw_usage, TokenUsage):
        return raw_usage

    return TokenUsage(
        prompt_tokens=int(getattr(raw_usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(raw_usage, "completion_tokens", 0) or 0),
        total_tokens=int(getattr(raw_usage, "total_tokens", 0) or 0),
    )


def _normalize_completion(raw_completion: object) -> _LLMCompletion:
    if isinstance(raw_completion, str):
        return _LLMCompletion(raw_completion, _zero_token_usage())

    content = getattr(raw_completion, "content", None)
    if not isinstance(content, str):
        raise LLMAPIError("LLM response must contain content text")

    return _LLMCompletion(
        content=content,
        token_usage=_coerce_token_usage(
            getattr(raw_completion, "token_usage", getattr(raw_completion, "usage", None))
        ),
    )


def _toolkit_complete(
    *,
    messages: list[Mapping[str, str]],
    config: object,
    tier: object,
) -> _LLMCompletion:
    try:
        from toolkit.llm_client import Message, complete

        toolkit_messages = [
            Message(role=message["role"], content=message["content"]) for message in messages
        ]
        return _normalize_completion(
            complete(messages=toolkit_messages, config=config, tier=tier)
        )
    except LLMAPIError:
        raise
    except Exception as exc:
        raise LLMAPIError("generation LLM call failed") from exc


def _call_generation_llm(
    messages: list[Mapping[str, str]],
    config: GeneratorConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> _LLMCompletion:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    try:
        return _normalize_completion(
            llm_complete_callable(
                messages=messages,
                config=config.llm_config,
                tier=config.generation_tier,
            )
        )
    except LLMAPIError:
        raise
    except Exception as exc:
        raise LLMAPIError("generation LLM call failed") from exc


def _extract_json_object(response_text: str) -> Mapping[str, object]:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise LLMAPIError("generation LLM response must be valid JSON") from exc

    if not isinstance(payload, Mapping):
        raise LLMAPIError("generation LLM response must be a JSON object")

    return payload


def _require_string(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise LLMAPIError(f"generation LLM response missing {field_name} string")
    value = value.strip()
    if not value:
        raise LLMAPIError(f"generation LLM response {field_name} must be non-empty")
    return value


def _require_probability(payload: Mapping[str, object], field_name: str) -> float:
    value = payload.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LLMAPIError(f"generation LLM response missing {field_name} number")
    if value < 0.0 or value > 1.0:
        raise LLMAPIError(f"generation LLM response {field_name} must be in [0.0, 1.0]")
    return float(value)


def _parse_string_list(payload: Mapping[str, object], field_name: str) -> list[str]:
    value = payload.get(field_name, [])
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise LLMAPIError(f"generation LLM response {field_name} must be a list")

    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise LLMAPIError(f"generation LLM response {field_name} entries must be strings")
        normalized = item.strip()
        if normalized:
            parsed.append(normalized)
    return parsed


def _parse_contradictions(payload: Mapping[str, object]) -> list[Contradiction]:
    value = payload.get("contradictions_noted", [])
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise LLMAPIError("generation LLM response contradictions_noted must be a list")

    contradictions: list[Contradiction] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise LLMAPIError("generation LLM contradiction entries must be objects")
        contradictions.append(
            Contradiction(
                personality_note_id=_require_string(item, "personality_note_id"),
                claim_summary=_require_string(item, "claim_summary"),
                counter_evidence_ids=_parse_string_list(item, "counter_evidence_ids"),
                counter_summary=_require_string(item, "counter_summary"),
            )
        )
    return contradictions


def _parse_generator_output_payload(
    response_text: str,
    *,
    token_usage: TokenUsage,
    default_output_mode: str,
    default_is_lateral: bool,
    fallback_source_note_ids: list[str],
    originating_message_id: str | None = None,
) -> GeneratorOutput:
    payload = _extract_json_object(response_text)
    output_mode = payload.get("output_mode", default_output_mode)
    is_lateral = payload.get("is_lateral", default_is_lateral)
    if output_mode != default_output_mode:
        raise LLMAPIError("generation LLM response output_mode does not match request")
    if not isinstance(is_lateral, bool):
        raise LLMAPIError("generation LLM response is_lateral must be boolean")

    source_note_ids = _parse_string_list(payload, "source_note_ids")
    if not source_note_ids:
        source_note_ids = list(fallback_source_note_ids)

    return GeneratorOutput(
        content=_require_string(payload, "content"),
        intent_tag=_require_string(payload, "intent_tag"),
        output_mode=default_output_mode,
        importance_score=_require_probability(payload, "importance_score"),
        is_lateral=is_lateral,
        source_note_ids=source_note_ids,
        contradictions_noted=_parse_contradictions(payload),
        token_usage=token_usage,
        originating_message_id=originating_message_id,
    )


class Generator:
    """Stateless Generator facade.

    LLM-backed generation behavior is introduced in a later phase; this phase
    establishes the public constructor and method surface.
    """

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def _load_personality_snapshot(
        self,
        ambient: AmbientContext,
        config: GeneratorConfig,
        *,
        topic_embedding: object | None = None,
    ) -> PersonalitySnapshot:
        context = self.memory_store.get_personality_context()
        personality_files = list(context.personality_files)
        if not personality_files:
            raise EmptyPersonalityError("no Tier 3 personality context exists")

        return PersonalitySnapshot(
            personality_files=personality_files,
            relevant_patterns=self._load_relevant_patterns(
                config,
                topic_embedding=topic_embedding,
            ),
            contradictions=[],
            ambient_context=ambient,
        )

    def _load_relevant_patterns(
        self,
        config: GeneratorConfig,
        *,
        topic_embedding: object | None = None,
    ) -> list[MemoryNote]:
        if not config.include_tier2_patterns or config.tier2_pattern_limit == 0:
            return []

        if topic_embedding is not None and hasattr(self.memory_store, "search_by_embedding"):
            results = self.memory_store.search_by_embedding(
                topic_embedding,
                tier=2,
                limit=config.tier2_pattern_limit,
            )
            return [note for note, _similarity in results]

        if hasattr(self.memory_store, "query_notes"):
            return list(
                self.memory_store.query_notes(
                    NoteQuery(
                        tier=2,
                        limit=config.tier2_pattern_limit,
                        order_by="importance",
                    )
                )
            )

        return []

    @staticmethod
    def _source_note_ids(snapshot: PersonalitySnapshot) -> list[str]:
        notes = [*snapshot.personality_files, *snapshot.relevant_patterns]
        return [str(note.note_id) for note in notes]

    def generate(
        self,
        prompt: GenerationPrompt,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def free_play(
        self,
        trigger: FreePlayTrigger,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def respond(
        self,
        message: InboundMessage,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")
