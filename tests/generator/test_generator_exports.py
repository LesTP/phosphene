from dataclasses import fields
from datetime import datetime

import pytest

import phosphene.generator as generator
from phosphene.generator import (
    Contradiction,
    EmptyPersonalityError,
    FreePlayTrigger,
    GenerationPrompt,
    Generator,
    GeneratorConfig,
    GeneratorConfigError,
    GeneratorError,
    GeneratorOutput,
    LLMAPIError,
    LengthThresholds,
    PersonalitySnapshot,
    RouterConfig,
)
from phosphene.generator.types import ModelTier, TokenUsage
from phosphene.memory_store import MemoryNote


def test_package_exports_arch_public_api() -> None:
    expected_exports = {
        "Contradiction",
        "EmptyPersonalityError",
        "FreePlayTrigger",
        "GenerationPrompt",
        "Generator",
        "GeneratorConfig",
        "GeneratorConfigError",
        "GeneratorError",
        "GeneratorOutput",
        "LLMAPIError",
        "LengthThresholds",
        "PersonalitySnapshot",
        "RouterConfig",
        "route",
    }

    assert set(generator.__all__) == expected_exports
    for exported_name in expected_exports:
        assert getattr(generator, exported_name) is not None


def test_arch_dataclass_field_names_match_contract() -> None:
    assert [field.name for field in fields(GeneratorConfig)] == [
        "llm_config",
        "llm_configs_rotation",
        "generation_tier",
        "verification_tier",
        "max_output_tokens",
        "include_tier2_patterns",
        "tier2_pattern_limit",
        "skeptical_memory",
        "skeptical_window_days",
    ]
    assert [field.name for field in fields(GenerationPrompt)] == [
        "topic",
        "unresolved_thread_ids",
        "budget_tokens",
    ]
    assert [field.name for field in fields(FreePlayTrigger)] == [
        "trigger_note_ids",
        "budget_tokens",
        "affordances",
    ]
    assert [field.name for field in fields(GeneratorOutput)] == [
        "content",
        "intent_tag",
        "output_mode",
        "importance_score",
        "is_lateral",
        "source_note_ids",
        "contradictions_noted",
        "token_usage",
        "originating_message_id",
    ]
    assert [field.name for field in fields(Contradiction)] == [
        "personality_note_id",
        "claim_summary",
        "counter_evidence_ids",
        "counter_summary",
    ]
    assert [field.name for field in fields(PersonalitySnapshot)] == [
        "personality_files",
        "relevant_patterns",
        "contradictions",
        "ambient_context",
    ]
    assert [field.name for field in fields(RouterConfig)] == [
        "length_thresholds",
        "intent_routing",
    ]
    assert [field.name for field in fields(LengthThresholds)] == [
        "short_max",
        "medium_max",
    ]


def test_arch_dataclasses_construct_with_expected_defaults() -> None:
    config = GeneratorConfig(llm_config=object())
    prompt = GenerationPrompt()
    trigger = FreePlayTrigger(trigger_note_ids=["note-1"])
    contradiction = Contradiction(
        personality_note_id="personality-1",
        claim_summary="claim",
        counter_evidence_ids=["note-2"],
        counter_summary="counter",
    )
    output = GeneratorOutput(
        content="generated",
        intent_tag="synthesis",
        output_mode="prompted",
        importance_score=0.75,
        is_lateral=False,
        source_note_ids=["personality-1"],
        contradictions_noted=[contradiction],
        token_usage=TokenUsage(),
    )
    note = MemoryNote(
        note_id="personality-1",
        tier=3,
        content="voice",
        title="Personality",
        importance=1.0,
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
    snapshot = PersonalitySnapshot(
        personality_files=[note],
        relevant_patterns=[],
        contradictions=[contradiction],
        ambient_context={"hour": 12},
    )
    router_config = RouterConfig()

    assert config.llm_configs_rotation is None
    assert config.generation_tier == ModelTier.QUALITY
    assert config.verification_tier == ModelTier.DEFAULT
    assert config.max_output_tokens == 2000
    assert config.include_tier2_patterns is True
    assert config.tier2_pattern_limit == 10
    assert config.skeptical_memory is True
    assert config.skeptical_window_days == 14
    assert prompt.topic is None
    assert prompt.unresolved_thread_ids is None
    assert prompt.budget_tokens == 4000
    assert trigger.budget_tokens == 2000
    assert trigger.affordances == [
        "synthesize_across_threads",
        "surface_contradiction",
        "pose_question",
        "reframe_existing_claim",
        "connect_unlinked_material",
    ]
    assert output.originating_message_id is None
    assert snapshot.personality_files == [note]
    assert router_config.length_thresholds == LengthThresholds()
    assert router_config.intent_routing == {
        "internal_note": "log",
        "log_surfacing": "log",
        "subscription_proposal": "log",
    }
    assert isinstance(Generator(memory_store=object()), Generator)
    assert issubclass(GeneratorConfigError, GeneratorError)
    assert issubclass(EmptyPersonalityError, GeneratorError)
    assert issubclass(LLMAPIError, GeneratorError)


@pytest.mark.parametrize(
    ("factory", "match"),
    [
        (lambda: GeneratorConfig(llm_config=object(), max_output_tokens=0), "max_output_tokens"),
        (lambda: GeneratorConfig(llm_config=object(), tier2_pattern_limit=-1), "tier2_pattern_limit"),
        (lambda: GeneratorConfig(llm_config=object(), skeptical_window_days=0), "skeptical_window_days"),
        (lambda: GenerationPrompt(budget_tokens=0), "budget_tokens"),
        (lambda: FreePlayTrigger(trigger_note_ids=[]), "trigger_note_ids"),
        (lambda: FreePlayTrigger(trigger_note_ids=["n"], budget_tokens=0), "budget_tokens"),
        (lambda: LengthThresholds(short_max=0), "short_max"),
        (lambda: LengthThresholds(medium_max=0), "medium_max"),
        (lambda: LengthThresholds(short_max=10, medium_max=5), "short_max"),
    ],
)
def test_config_validation_rejects_obvious_invalid_values(factory, match: str) -> None:
    with pytest.raises(GeneratorConfigError, match=match):
        factory()
