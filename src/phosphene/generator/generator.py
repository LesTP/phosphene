"""Generator public entry point."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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


def _llm_config_candidates(config: GeneratorConfig) -> list[object]:
    return [config.llm_config, *list(config.llm_configs_rotation or [])]


def _call_llm_with_config_rotation(
    *,
    messages: list[Mapping[str, str]],
    llm_configs: Sequence[object],
    tier: object,
    failure_message: str,
    llm_complete_callable: _LLMCompleteCallable,
) -> _LLMCompletion:
    last_failure: Exception | None = None
    for llm_config in llm_configs:
        try:
            return _normalize_completion(
                llm_complete_callable(
                    messages=messages,
                    config=llm_config,
                    tier=tier,
                )
            )
        except LLMAPIError as exc:
            if exc.__cause__ is None:
                raise
            last_failure = exc
        except Exception as exc:
            last_failure = exc

    if last_failure is not None:
        raise LLMAPIError(failure_message) from last_failure
    raise LLMAPIError(failure_message)


def _call_generation_llm(
    messages: list[Mapping[str, str]],
    config: GeneratorConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> _LLMCompletion:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    return _call_llm_with_config_rotation(
        messages=messages,
        llm_configs=_llm_config_candidates(config),
        tier=config.generation_tier,
        failure_message="generation LLM call failed",
        llm_complete_callable=llm_complete_callable,
    )


def _call_verification_llm(
    messages: list[Mapping[str, str]],
    config: GeneratorConfig,
    *,
    llm_complete_callable: _LLMCompleteCallable | None = None,
) -> _LLMCompletion:
    if llm_complete_callable is None:
        llm_complete_callable = _toolkit_complete

    return _call_llm_with_config_rotation(
        messages=messages,
        llm_configs=_llm_config_candidates(config),
        tier=config.verification_tier,
        failure_message="verification LLM call failed",
        llm_complete_callable=llm_complete_callable,
    )


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


def _merge_contradictions(
    primary: Sequence[Contradiction],
    fallback: Sequence[Contradiction],
) -> list[Contradiction]:
    merged: list[Contradiction] = []
    seen: set[tuple[str, str, tuple[str, ...], str]] = set()
    for contradiction in [*primary, *fallback]:
        key = (
            contradiction.personality_note_id,
            contradiction.claim_summary,
            tuple(contradiction.counter_evidence_ids),
            contradiction.counter_summary,
        )
        if key not in seen:
            seen.add(key)
            merged.append(contradiction)
    return merged


def _parse_generator_output_payload(
    response_text: str,
    *,
    token_usage: TokenUsage,
    default_output_mode: str,
    default_is_lateral: bool,
    fallback_source_note_ids: list[str],
    fallback_contradictions: Sequence[Contradiction] | None = None,
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

    parsed_contradictions = _parse_contradictions(payload)
    return GeneratorOutput(
        content=_require_string(payload, "content"),
        intent_tag=_require_string(payload, "intent_tag"),
        output_mode=default_output_mode,
        importance_score=_require_probability(payload, "importance_score"),
        is_lateral=is_lateral,
        source_note_ids=source_note_ids,
        contradictions_noted=_merge_contradictions(
            parsed_contradictions,
            list(fallback_contradictions or []),
        ),
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
        "source_note_ids, contradictions_noted. Use the required output_mode "
        "from the user payload and set is_lateral exactly as requested. "
        "contradictions_noted must be a list of objects with personality_note_id, "
        "claim_summary, counter_evidence_ids, and counter_summary."
    )


def _verification_system_message() -> str:
    return (
        "You are the Phosphene skeptical-memory verifier. Return only JSON. "
        "For claim extraction, return {\"claims\":[{\"claim_summary\":\"...\"}]}. "
        "For contradiction checks, return {\"contradictions\":[{\"personality_note_id\":"
        "\"...\",\"claim_summary\":\"...\",\"counter_evidence_ids\":[\"...\"],"
        "\"counter_summary\":\"...\"}]}."
    )


def _build_claim_extraction_messages(note: MemoryNote) -> list[Mapping[str, str]]:
    payload = {
        "task": "extract_personality_claims",
        "personality_file": _note_payload(note),
    }
    return [
        {"role": "system", "content": _verification_system_message()},
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        },
    ]


def _build_contradiction_check_messages(
    *,
    personality_note: MemoryNote,
    claims: Sequence[str],
    recent_notes: Sequence[MemoryNote],
) -> list[Mapping[str, str]]:
    payload = {
        "task": "check_personality_claims_against_recent_tier1",
        "personality_note_id": str(personality_note.note_id),
        "claims": list(claims),
        "recent_tier1_notes": [_note_payload(note) for note in recent_notes],
        "required_output": {
            "contradictions_field": "contradictions",
            "personality_note_id": str(personality_note.note_id),
        },
    }
    return [
        {"role": "system", "content": _verification_system_message()},
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True, separators=(",", ":")),
        },
    ]


def _parse_claim_summaries(response_text: str) -> list[str]:
    payload = _extract_json_object(response_text)
    value = payload.get("claims", [])
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise LLMAPIError("verification LLM response claims must be a list")

    claims: list[str] = []
    for item in value:
        if isinstance(item, str):
            claim = item.strip()
        elif isinstance(item, Mapping):
            claim = _require_string(item, "claim_summary")
        else:
            raise LLMAPIError("verification LLM claim entries must be strings or objects")
        if claim:
            claims.append(claim)
    return claims


def _parse_verification_contradictions(
    response_text: str,
    *,
    personality_note_id: str,
) -> list[Contradiction]:
    payload = _extract_json_object(response_text)
    value = payload.get("contradictions", [])
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        raise LLMAPIError("verification LLM response contradictions must be a list")

    contradictions: list[Contradiction] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise LLMAPIError("verification LLM contradiction entries must be objects")
        note_id = item.get("personality_note_id", personality_note_id)
        if not isinstance(note_id, str) or not note_id.strip():
            raise LLMAPIError("verification LLM contradiction personality_note_id invalid")
        contradictions.append(
            Contradiction(
                personality_note_id=note_id.strip(),
                claim_summary=_require_string(item, "claim_summary"),
                counter_evidence_ids=_parse_string_list(item, "counter_evidence_ids"),
                counter_summary=_require_string(item, "counter_summary"),
            )
        )
    return contradictions


class Generator:
    """Stateless Generator facade.

    Each public generation call loads fresh Memory Store context, builds a
    bounded LLM prompt, parses a typed GeneratorOutput, and performs no writes.
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

        contradictions = self._load_skeptical_contradictions(personality_files, config)

        return PersonalitySnapshot(
            personality_files=personality_files,
            relevant_patterns=self._load_relevant_patterns(
                config,
                topic_embedding=topic_embedding,
            ),
            contradictions=contradictions,
            ambient_context=ambient,
        )

    def _load_skeptical_contradictions(
        self,
        personality_files: Sequence[MemoryNote],
        config: GeneratorConfig,
    ) -> list[Contradiction]:
        if not config.skeptical_memory:
            return []

        recent_notes = self._load_recent_tier1_notes(config)
        if not recent_notes:
            return []

        contradictions: list[Contradiction] = []
        for personality_note in personality_files:
            claims_completion = _call_verification_llm(
                _build_claim_extraction_messages(personality_note),
                config,
            )
            claims = _parse_claim_summaries(claims_completion.content)
            if not claims:
                continue

            contradiction_completion = _call_verification_llm(
                _build_contradiction_check_messages(
                    personality_note=personality_note,
                    claims=claims,
                    recent_notes=recent_notes,
                ),
                config,
            )
            contradictions.extend(
                _parse_verification_contradictions(
                    contradiction_completion.content,
                    personality_note_id=str(personality_note.note_id),
                )
            )
        return contradictions

    def _load_recent_tier1_notes(self, config: GeneratorConfig) -> list[MemoryNote]:
        if not hasattr(self.memory_store, "query_notes"):
            return []

        since = datetime.now(timezone.utc) - timedelta(days=config.skeptical_window_days)
        return list(
            self.memory_store.query_notes(
                NoteQuery(
                    tier=1,
                    since=since,
                    limit=50,
                    order_by="created_at",
                )
            )
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

    def _load_response_context(
        self,
        message: InboundMessage,
        config: GeneratorConfig,
    ) -> list[MemoryNote]:
        limit = config.tier2_pattern_limit or 10
        raw = message.raw if isinstance(message.raw, Mapping) else {}
        embedding = raw.get("embedding", raw.get("content_embedding"))

        if embedding is not None and hasattr(self.memory_store, "search_by_embedding"):
            results = self.memory_store.search_by_embedding(embedding, limit=limit)
            return [note for note, _similarity in results]

        if hasattr(self.memory_store, "query_notes"):
            return list(
                self.memory_store.query_notes(
                    NoteQuery(
                        limit=limit,
                        order_by="importance",
                    )
                )
            )

        return []

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

    def _build_response_generation_messages(
        self,
        *,
        message: InboundMessage,
        snapshot: PersonalitySnapshot,
        relevant_notes: Sequence[MemoryNote],
        config: GeneratorConfig,
    ) -> list[Mapping[str, str]]:
        payload = {
            "task": "response_generation",
            "inbound_message": {
                "content": message.content,
                "platform": message.platform,
                "message_id": message.message_id,
                "sender": message.sender,
                "timestamp": message.timestamp.isoformat(),
                "reply_to": message.reply_to,
                "reactions": list(message.reactions or []),
                "raw": _json_ready(message.raw or {}),
            },
            "max_output_tokens": config.max_output_tokens,
            "ambient_context": _json_ready(snapshot.ambient_context),
            "personality_files": [
                _note_payload(note) for note in snapshot.personality_files
            ],
            "relevant_patterns": [
                _note_payload(note) for note in snapshot.relevant_patterns
            ],
            "relevant_notes": [_note_payload(note) for note in relevant_notes],
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
                "output_mode": "response",
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

    def _build_free_play_generation_messages(
        self,
        *,
        trigger: FreePlayTrigger,
        snapshot: PersonalitySnapshot,
        trigger_notes: Sequence[MemoryNote],
        config: GeneratorConfig,
    ) -> list[Mapping[str, str]]:
        payload = {
            "task": "free_play_generation",
            "trigger_note_ids": list(trigger.trigger_note_ids),
            "budget_tokens": trigger.budget_tokens,
            "affordances": list(trigger.affordances),
            "max_output_tokens": config.max_output_tokens,
            "ambient_context": _json_ready(snapshot.ambient_context),
            "personality_files": [
                _note_payload(note) for note in snapshot.personality_files
            ],
            "relevant_patterns": [
                _note_payload(note) for note in snapshot.relevant_patterns
            ],
            "trigger_notes": [_note_payload(note) for note in trigger_notes],
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
                "output_mode": "free_play",
                "is_lateral": True,
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
            fallback_contradictions=snapshot.contradictions,
        )

    def free_play(
        self,
        trigger: FreePlayTrigger,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        snapshot = self._load_personality_snapshot(ambient, config)
        trigger_notes = self._load_notes_by_id(trigger.trigger_note_ids)
        completion = _call_generation_llm(
            self._build_free_play_generation_messages(
                trigger=trigger,
                snapshot=snapshot,
                trigger_notes=trigger_notes,
                config=config,
            ),
            config,
        )
        return _parse_generator_output_payload(
            completion.content,
            token_usage=completion.token_usage,
            default_output_mode="free_play",
            default_is_lateral=True,
            fallback_source_note_ids=self._source_note_ids_with(snapshot, trigger_notes),
            fallback_contradictions=snapshot.contradictions,
        )

    def respond(
        self,
        message: InboundMessage,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        snapshot = self._load_personality_snapshot(ambient, config)
        relevant_notes = self._load_response_context(message, config)
        completion = _call_generation_llm(
            self._build_response_generation_messages(
                message=message,
                snapshot=snapshot,
                relevant_notes=relevant_notes,
                config=config,
            ),
            config,
        )
        return _parse_generator_output_payload(
            completion.content,
            token_usage=completion.token_usage,
            default_output_mode="response",
            default_is_lateral=False,
            fallback_source_note_ids=self._source_note_ids_with(snapshot, relevant_notes),
            fallback_contradictions=snapshot.contradictions,
            originating_message_id=message.message_id,
        )
