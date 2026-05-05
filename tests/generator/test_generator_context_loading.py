import json
from dataclasses import dataclass
from datetime import datetime

import pytest

import phosphene.generator.generator as generator_module
from phosphene.gateway import InboundMessage
from phosphene.generator import (
    EmptyPersonalityError,
    FreePlayTrigger,
    GenerationPrompt,
    Generator,
    GeneratorConfig,
)
from phosphene.generator.types import TokenUsage
from phosphene.memory_store import MemoryNote, PersonalityContext


def make_note(note_id: str, *, tier: int = 3, importance: float = 0.0) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"{note_id} body",
        title=note_id,
        importance=importance,
        unresolvedness=0.0,
        links=[],
        tags=[],
        source=None,
        friction_target=None,
        embedding=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        link_count=0,
        decay_deadline=None,
    )


@dataclass
class FakeMemoryStore:
    personality_files: list[MemoryNote]
    query_results: list[MemoryNote] | None = None
    search_results: list[tuple[MemoryNote, float]] | None = None

    def __post_init__(self) -> None:
        self.context_calls = 0
        self.query_calls: list[object] = []
        self.search_calls: list[tuple[object, int | None, int]] = []
        self.get_note_calls: list[str] = []
        self.write_calls = 0

    def get_personality_context(self) -> PersonalityContext:
        self.context_calls += 1
        return PersonalityContext(
            personality_files=list(self.personality_files),
            version_id=f"version-{self.context_calls}",
        )

    def query_notes(self, query: object) -> list[MemoryNote]:
        self.query_calls.append(query)
        return list(self.query_results or [])

    def search_by_embedding(
        self,
        embedding: object,
        *,
        tier: int | None = None,
        limit: int = 10,
    ) -> list[tuple[MemoryNote, float]]:
        self.search_calls.append((embedding, tier, limit))
        return list(self.search_results or [])

    def get_note(self, note_id: str) -> MemoryNote:
        self.get_note_calls.append(note_id)
        return make_note(note_id, tier=1, importance=0.7)

    def store_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def update_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1


def test_snapshot_loads_fresh_tier_three_context_and_preserves_source_ids() -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    store = FakeMemoryStore([personality], query_results=[pattern])
    generator = Generator(store)

    snapshot = generator._load_personality_snapshot(
        {"hour": 12},
        GeneratorConfig(llm_config=object(), skeptical_memory=False),
    )

    assert store.context_calls == 1
    assert snapshot.personality_files == [personality]
    assert snapshot.relevant_patterns == [pattern]
    assert snapshot.contradictions == []
    assert snapshot.ambient_context == {"hour": 12}
    assert generator._source_note_ids(snapshot) == ["personality-1", "pattern-1"]
    assert store.write_calls == 0


def test_snapshot_raises_empty_personality_when_tier_three_context_absent() -> None:
    store = FakeMemoryStore([])

    with pytest.raises(EmptyPersonalityError, match="Tier 3"):
        Generator(store)._load_personality_snapshot(
            {},
            GeneratorConfig(llm_config=object(), skeptical_memory=False),
        )

    assert store.query_calls == []
    assert store.search_calls == []
    assert store.write_calls == 0


def test_public_generation_methods_check_empty_personality_before_llm_phase() -> None:
    store = FakeMemoryStore([])

    with pytest.raises(EmptyPersonalityError):
        Generator(store).generate(
            GenerationPrompt(topic="density"),
            {},
            GeneratorConfig(llm_config=object(), skeptical_memory=False),
        )


def test_tier_two_enrichment_can_use_embedding_search_boundary() -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2)
    embedding = object()
    store = FakeMemoryStore([personality], search_results=[(pattern, 0.91)])

    snapshot = Generator(store)._load_personality_snapshot(
        {},
        GeneratorConfig(llm_config=object(), tier2_pattern_limit=3, skeptical_memory=False),
        topic_embedding=embedding,
    )

    assert snapshot.relevant_patterns == [pattern]
    assert store.search_calls == [(embedding, 2, 3)]
    assert store.query_calls == []
    assert store.write_calls == 0


def test_tier_two_enrichment_can_be_disabled() -> None:
    store = FakeMemoryStore([make_note("personality-1", tier=3)])

    snapshot = Generator(store)._load_personality_snapshot(
        {},
        GeneratorConfig(
            llm_config=object(),
            include_tier2_patterns=False,
            skeptical_memory=False,
        ),
    )

    assert snapshot.relevant_patterns == []
    assert store.query_calls == []
    assert store.search_calls == []


def test_skeptical_memory_extracts_claims_checks_recent_tier1_and_marks_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    personality = make_note("personality-1", tier=3)
    recent = make_note("recent-1", tier=1, importance=0.9)
    store = FakeMemoryStore([personality], query_results=[recent])
    calls: list[dict[str, object]] = []
    captured_generation_payloads: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        messages = kwargs["messages"]
        payload = json.loads(messages[1]["content"])
        task = payload["task"]
        if task == "extract_personality_claims":
            assert payload["personality_file"]["note_id"] == "personality-1"
            return generator_module._LLMCompletion(
                content=json.dumps(
                    {"claims": [{"claim_summary": "I avoid direct contradiction"}]}
                ),
                token_usage=TokenUsage(),
            )
        if task == "check_personality_claims_against_recent_tier1":
            assert payload["personality_note_id"] == "personality-1"
            assert payload["claims"] == ["I avoid direct contradiction"]
            assert payload["recent_tier1_notes"][0]["note_id"] == "recent-1"
            return generator_module._LLMCompletion(
                content=json.dumps(
                    {
                        "contradictions": [
                            {
                                "personality_note_id": "personality-1",
                                "claim_summary": "I avoid direct contradiction",
                                "counter_evidence_ids": ["recent-1"],
                                "counter_summary": "recent note embraces contradiction",
                            }
                        ]
                    }
                ),
                token_usage=TokenUsage(),
            )

        captured_generation_payloads.append(payload)
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated with tension",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.7,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=TokenUsage(),
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(topic="contradiction"),
        {},
        GeneratorConfig(
            llm_config="llm-config",
            generation_tier="quality",
            verification_tier="commodity",
            include_tier2_patterns=False,
        ),
    )

    assert output.content == "generated with tension"
    assert output.contradictions_noted[0].personality_note_id == "personality-1"
    assert output.contradictions_noted[0].counter_evidence_ids == ["recent-1"]
    assert captured_generation_payloads[0]["contradictions"] == [
        {
            "personality_note_id": "personality-1",
            "claim_summary": "I avoid direct contradiction",
            "counter_evidence_ids": ["recent-1"],
            "counter_summary": "recent note embraces contradiction",
        }
    ]
    assert [call["tier"] for call in calls] == ["commodity", "commodity", "quality"]
    assert [call["config"] for call in calls] == ["llm-config"] * 3
    assert len(store.query_calls) == 1
    assert store.query_calls[0].tier == 1
    assert store.query_calls[0].since is not None
    assert store.query_calls[0].limit == 50
    assert store.write_calls == 0


def test_generate_builds_prompted_context_calls_llm_and_preserves_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    store = FakeMemoryStore([personality], query_results=[pattern])
    calls: list[dict[str, object]] = []
    usage = TokenUsage(prompt_tokens=10, completion_tokens=12, total_tokens=22)

    def fake_complete(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated from prompt",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.64,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=usage,
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(topic="density", unresolved_thread_ids=["thread-1"]),
        {"hour": 12},
        GeneratorConfig(
            llm_config="llm-config",
            generation_tier="quality",
            skeptical_memory=False,
        ),
    )

    assert output.content == "generated from prompt"
    assert output.output_mode == "prompted"
    assert output.is_lateral is False
    assert output.source_note_ids == ["personality-1", "pattern-1", "thread-1"]
    assert output.token_usage == usage
    assert output.originating_message_id is None
    assert store.context_calls == 1
    assert len(store.query_calls) == 1
    assert store.get_note_calls == ["thread-1"]
    assert store.write_calls == 0
    assert calls[0]["config"] == "llm-config"
    assert calls[0]["tier"] == "quality"

    messages = calls[0]["messages"]
    assert messages[0]["role"] == "system"
    payload = json.loads(messages[1]["content"])
    assert payload["task"] == "prompted_generation"
    assert payload["topic"] == "density"
    assert payload["topic_selection"] == {
        "source": "explicit_prompt",
        "source_note_ids": [],
    }
    assert payload["ambient_context"] == {"hour": 12}
    assert payload["personality_files"][0]["note_id"] == "personality-1"
    assert payload["relevant_patterns"][0]["note_id"] == "pattern-1"
    assert payload["unresolved_threads"][0]["note_id"] == "thread-1"
    assert payload["required_output"] == {
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
    }


def test_generate_selects_absent_topic_from_unresolved_thread_before_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMemoryStore([make_note("personality-1", tier=3)])
    captured_payloads: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> object:
        messages = kwargs["messages"]
        captured_payloads.append(json.loads(messages[1]["content"]))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated from unresolved",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=TokenUsage(),
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(unresolved_thread_ids=["thread-1"]),
        {},
        GeneratorConfig(llm_config=object(), skeptical_memory=False),
    )

    assert output.source_note_ids == ["personality-1", "thread-1"]
    assert store.context_calls == 1
    assert store.get_note_calls == ["thread-1"]
    assert store.write_calls == 0
    assert captured_payloads[0]["topic"] == "thread-1: thread-1 body"
    assert captured_payloads[0]["topic_selection"] == {
        "source": "unresolved_thread",
        "source_note_ids": ["thread-1"],
    }


def test_generate_selects_absent_topic_from_high_importance_tier_two_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    low_pattern = make_note("low-pattern", tier=2, importance=0.2)
    high_pattern = make_note("high-pattern", tier=2, importance=0.9)
    store = FakeMemoryStore(
        [make_note("personality-1", tier=3)],
        query_results=[low_pattern, high_pattern],
    )
    captured_payloads: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> object:
        messages = kwargs["messages"]
        captured_payloads.append(json.loads(messages[1]["content"]))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated from pattern",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=TokenUsage(),
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(),
        {},
        GeneratorConfig(llm_config=object(), skeptical_memory=False),
    )

    assert output.source_note_ids == ["personality-1", "low-pattern", "high-pattern"]
    assert store.context_calls == 1
    assert len(store.query_calls) == 1
    assert store.get_note_calls == []
    assert store.write_calls == 0
    assert captured_payloads[0]["topic"] == "high-pattern: high-pattern body"
    assert captured_payloads[0]["topic_selection"] == {
        "source": "tier2_pattern",
        "source_note_ids": ["high-pattern"],
    }


def test_generate_absent_topic_without_bootstrap_material_still_requires_personality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeMemoryStore([make_note("personality-1", tier=3)])
    captured_payloads: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> object:
        messages = kwargs["messages"]
        captured_payloads.append(json.loads(messages[1]["content"]))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated from personality only",
                    "intent_tag": "synthesis",
                    "output_mode": "prompted",
                    "importance_score": 0.5,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=TokenUsage(),
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).generate(
        GenerationPrompt(),
        {},
        GeneratorConfig(
            llm_config=object(),
            include_tier2_patterns=False,
            skeptical_memory=False,
        ),
    )

    assert output.source_note_ids == ["personality-1"]
    assert store.context_calls == 1
    assert store.query_calls == []
    assert store.get_note_calls == []
    assert store.write_calls == 0
    assert captured_payloads[0]["topic"] is None
    assert captured_payloads[0]["topic_selection"] == {
        "source": "no_bootstrap_material",
        "source_note_ids": [],
    }


def test_respond_builds_response_context_calls_llm_and_preserves_threading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    relevant = make_note("relevant-1", tier=1, importance=0.7)
    store = FakeMemoryStore(
        [personality],
        query_results=[pattern],
        search_results=[(relevant, 0.86)],
    )
    calls: list[dict[str, object]] = []
    usage = TokenUsage(prompt_tokens=9, completion_tokens=13, total_tokens=22)

    def fake_complete(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated response",
                    "intent_tag": "question",
                    "output_mode": "response",
                    "importance_score": 0.62,
                    "is_lateral": False,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=usage,
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)
    inbound = InboundMessage(
        content="What changed about density?",
        platform="telegram",
        message_id="inbound-42",
        sender="human",
        timestamp=datetime(2026, 5, 5, 12, 30),
        reply_to="previous-1",
        reactions=["curious"],
        raw={"embedding": [0.1, 0.2, 0.3], "chat_id": "chat-1"},
    )

    output = Generator(store).respond(
        inbound,
        {"hour": 12},
        GeneratorConfig(
            llm_config="llm-config",
            generation_tier="quality",
            skeptical_memory=False,
        ),
    )

    assert output.content == "generated response"
    assert output.output_mode == "response"
    assert output.is_lateral is False
    assert output.source_note_ids == ["personality-1", "pattern-1", "relevant-1"]
    assert output.token_usage == usage
    assert output.originating_message_id == "inbound-42"
    assert store.context_calls == 1
    assert len(store.query_calls) == 1
    assert store.search_calls == [([0.1, 0.2, 0.3], None, 10)]
    assert store.write_calls == 0
    assert calls[0]["config"] == "llm-config"
    assert calls[0]["tier"] == "quality"

    messages = calls[0]["messages"]
    assert messages[0]["role"] == "system"
    payload = json.loads(messages[1]["content"])
    assert payload["task"] == "response_generation"
    assert payload["ambient_context"] == {"hour": 12}
    assert payload["inbound_message"] == {
        "content": "What changed about density?",
        "platform": "telegram",
        "message_id": "inbound-42",
        "sender": "human",
        "timestamp": "2026-05-05T12:30:00",
        "reply_to": "previous-1",
        "reactions": ["curious"],
        "raw": {"embedding": [0.1, 0.2, 0.3], "chat_id": "chat-1"},
    }
    assert payload["personality_files"][0]["note_id"] == "personality-1"
    assert payload["relevant_patterns"][0]["note_id"] == "pattern-1"
    assert payload["relevant_notes"][0]["note_id"] == "relevant-1"
    assert payload["required_output"] == {
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
    }


def test_free_play_loads_triggers_calls_llm_and_marks_lateral(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    store = FakeMemoryStore([personality], query_results=[pattern])
    calls: list[dict[str, object]] = []
    usage = TokenUsage(prompt_tokens=8, completion_tokens=14, total_tokens=22)

    def fake_complete(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return generator_module._LLMCompletion(
            content=json.dumps(
                {
                    "content": "generated lateral move",
                    "intent_tag": "provocation",
                    "output_mode": "free_play",
                    "importance_score": 0.67,
                    "is_lateral": True,
                    "source_note_ids": [],
                    "contradictions_noted": [],
                }
            ),
            token_usage=usage,
        )

    monkeypatch.setattr(generator_module, "_toolkit_complete", fake_complete)

    output = Generator(store).free_play(
        FreePlayTrigger(
            trigger_note_ids=["trigger-1", "trigger-2"],
            budget_tokens=1200,
            affordances=["surface_contradiction", "pose_question"],
        ),
        {"hour": 22},
        GeneratorConfig(
            llm_config="llm-config",
            generation_tier="quality",
            skeptical_memory=False,
        ),
    )

    assert output.content == "generated lateral move"
    assert output.output_mode == "free_play"
    assert output.is_lateral is True
    assert output.source_note_ids == [
        "personality-1",
        "pattern-1",
        "trigger-1",
        "trigger-2",
    ]
    assert output.token_usage == usage
    assert output.originating_message_id is None
    assert store.context_calls == 1
    assert len(store.query_calls) == 1
    assert store.get_note_calls == ["trigger-1", "trigger-2"]
    assert store.write_calls == 0
    assert calls[0]["config"] == "llm-config"
    assert calls[0]["tier"] == "quality"

    messages = calls[0]["messages"]
    assert messages[0]["role"] == "system"
    payload = json.loads(messages[1]["content"])
    assert payload["task"] == "free_play_generation"
    assert payload["trigger_note_ids"] == ["trigger-1", "trigger-2"]
    assert payload["budget_tokens"] == 1200
    assert payload["affordances"] == ["surface_contradiction", "pose_question"]
    assert payload["ambient_context"] == {"hour": 22}
    assert payload["personality_files"][0]["note_id"] == "personality-1"
    assert payload["relevant_patterns"][0]["note_id"] == "pattern-1"
    assert [note["note_id"] for note in payload["trigger_notes"]] == [
        "trigger-1",
        "trigger-2",
    ]
    assert payload["required_output"] == {
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
    }
