"""Generator public entry point."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class _TopicSelection:
    topic: str | None
    source: str
    source_note_ids: list[str]


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


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_json_ready(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def _note_payload(note: MemoryNote) -> dict[str, object]:
    return {
        "note_id": str(note.note_id),
        "tier": note.tier,
        "title": note.title,
        "content": note.content,
        "importance": note.importance,
        "unresolvedness": note.unresolvedness,
        "links": list(note.links),
        "tags": list(note.tags),
        "source": note.source,
        "friction_target": note.friction_target,
        "attractor_relevance": note.attractor_relevance,
        "cluster_group": note.cluster_group,
        "link_count": note.link_count,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }


def _bootstrap_topic_from_note(note: MemoryNote) -> str:
    title = note.title.strip()
    content = " ".join(note.content.split())
    if len(content) > 180:
        content = f"{content[:177]}..."
    if title and content:
        return f"{title}: {content}"
    if title:
        return title
    if content:
        return content
    return str(note.note_id)


def _system_message() -> str:
    return (
        "You are the Phosphene Generator. Produce original text grounded only in "
        "the supplied personality files, relevant patterns, unresolved threads, "
        "and ambient context. Return a single JSON object with these fields: "
        "content, intent_tag, output_mode, importance_score, is_lateral, "
        "source_note_ids, contradictions_noted. For prompted generation, "
        'output_mode must be "prompted" and is_lateral must be false. '
        "contradictions_noted must be a list of objects with personality_note_id, "
        "claim_summary, counter_evidence_ids, and counter_summary."
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

    @staticmethod
    def _source_note_ids_with(
        snapshot: PersonalitySnapshot,
        extra_notes: Sequence[MemoryNote],
    ) -> list[str]:
        source_ids: list[str] = []
        for note in [*snapshot.personality_files, *snapshot.relevant_patterns, *extra_notes]:
            note_id = str(note.note_id)
            if note_id not in source_ids:
                source_ids.append(note_id)
        return source_ids

    def _load_notes_by_id(self, note_ids: Sequence[str] | None) -> list[MemoryNote]:
        if not note_ids or not hasattr(self.memory_store, "get_note"):
            return []

        notes: list[MemoryNote] = []
        for note_id in note_ids:
            notes.append(self.memory_store.get_note(note_id))
        return notes

    def _build_prompted_generation_messages(
        self,
        *,
        prompt: GenerationPrompt,
        topic_selection: _TopicSelection,
        snapshot: PersonalitySnapshot,
        unresolved_notes: Sequence[MemoryNote],
        config: GeneratorConfig,
    ) -> list[Mapping[str, str]]:
        payload = {
            "task": "prompted_generation",
            "topic": topic_selection.topic,
            "topic_selection": {
                "source": topic_selection.source,
                "source_note_ids": list(topic_selection.source_note_ids),
            },
            "budget_tokens": prompt.budget_tokens,
            "max_output_tokens": config.max_output_tokens,
            "ambient_context": _json_ready(snapshot.ambient_context),
            "personality_files": [
                _note_payload(note) for note in snapshot.personality_files
            ],
            "relevant_patterns": [
                _note_payload(note) for note in snapshot.relevant_patterns
            ],
            "unresolved_threads": [_note_payload(note) for note in unresolved_notes],
            "contradictions": [
                {
                    "personality_note_id": contradiction.personality_note_id,
                    "claim_summary": contradiction.claim_summary,
                    "counter_evidence_ids": list(contradiction.counter_evidence_ids),
                    "counter_summary": contradiction.counter_summary,
                }
                for contradiction in snapshot.contradictions
            ],
            "required_output": {
                "output_mode": "prompted",
                "is_lateral": False,
                "intent_tag_options": [
                    "synthesis",
                    "provocation",
                    "question",
                    "aesthetic",
                    "internal_note",
                    "log_surfacing",
                    "subscription_proposal",
                ],
            },
        }
        return [
            {"role": "system", "content": _system_message()},
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            },
        ]

    def _select_prompt_topic(
        self,
        prompt: GenerationPrompt,
        snapshot: PersonalitySnapshot,
        unresolved_notes: Sequence[MemoryNote],
    ) -> _TopicSelection:
        if prompt.topic is not None and prompt.topic.strip():
            return _TopicSelection(
                topic=prompt.topic.strip(),
                source="explicit_prompt",
                source_note_ids=[],
            )

        if unresolved_notes:
            note = unresolved_notes[0]
            return _TopicSelection(
                topic=_bootstrap_topic_from_note(note),
                source="unresolved_thread",
                source_note_ids=[str(note.note_id)],
            )

        if snapshot.relevant_patterns:
            note = sorted(
                snapshot.relevant_patterns,
                key=lambda candidate: (
                    candidate.importance,
                    candidate.updated_at,
                    str(candidate.note_id),
                ),
                reverse=True,
            )[0]
            return _TopicSelection(
                topic=_bootstrap_topic_from_note(note),
                source="tier2_pattern",
                source_note_ids=[str(note.note_id)],
            )

        return _TopicSelection(
            topic=None,
            source="no_bootstrap_material",
            source_note_ids=[],
        )

    def generate(
        self,
        prompt: GenerationPrompt,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        snapshot = self._load_personality_snapshot(ambient, config)
        unresolved_notes = self._load_notes_by_id(prompt.unresolved_thread_ids)
        topic_selection = self._select_prompt_topic(prompt, snapshot, unresolved_notes)
        completion = _call_generation_llm(
            self._build_prompted_generation_messages(
                prompt=prompt,
                topic_selection=topic_selection,
                snapshot=snapshot,
                unresolved_notes=unresolved_notes,
                config=config,
            ),
            config,
        )
        return _parse_generator_output_payload(
            completion.content,
            token_usage=completion.token_usage,
            default_output_mode="prompted",
            default_is_lateral=False,
            fallback_source_note_ids=self._source_note_ids_with(snapshot, unresolved_notes),
        )

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
