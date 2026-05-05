"""Dataclasses for the Generator + Output Router public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from phosphene.generator.errors import GeneratorConfigError
from phosphene.memory_store import MemoryNote

try:
    from toolkit.llm_client import LLMConfig, ModelTier, TokenUsage
except ImportError:
    LLMConfig = Any

    @dataclass
    class TokenUsage:
        """Fallback token usage shape for import-time compatibility without toolkit."""

        prompt_tokens: int = 0
        completion_tokens: int = 0
        total_tokens: int = 0

    class ModelTier(str, Enum):
        """Fallback model tiers for import-time compatibility without toolkit."""

        DEFAULT = "default"
        COMMODITY = "commodity"
        QUALITY = "quality"


AmbientContext = Any


def _require_positive_int(value: int, field_name: str) -> None:
    if value <= 0:
        raise GeneratorConfigError(f"{field_name} must be positive")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if value < 0:
        raise GeneratorConfigError(f"{field_name} must be non-negative")


def _require_probability(value: float, field_name: str) -> None:
    if value < 0.0 or value > 1.0:
        raise GeneratorConfigError(f"{field_name} must be in [0.0, 1.0]")


@dataclass
class GeneratorConfig:
    llm_config: LLMConfig
    llm_configs_rotation: list[LLMConfig] | None = None
    generation_tier: ModelTier = ModelTier.QUALITY
    verification_tier: ModelTier = ModelTier.DEFAULT
    max_output_tokens: int = 2000
    include_tier2_patterns: bool = True
    tier2_pattern_limit: int = 10
    skeptical_memory: bool = True
    skeptical_window_days: int = 14

    def __post_init__(self) -> None:
        _require_positive_int(self.max_output_tokens, "max_output_tokens")
        _require_non_negative_int(self.tier2_pattern_limit, "tier2_pattern_limit")
        _require_positive_int(self.skeptical_window_days, "skeptical_window_days")


@dataclass
class GenerationPrompt:
    topic: str | None = None
    unresolved_thread_ids: list[str] | None = None
    budget_tokens: int = 4000

    def __post_init__(self) -> None:
        _require_positive_int(self.budget_tokens, "budget_tokens")


@dataclass
class FreePlayTrigger:
    trigger_note_ids: list[str]
    budget_tokens: int = 2000
    affordances: list[str] = field(
        default_factory=lambda: [
            "synthesize_across_threads",
            "surface_contradiction",
            "pose_question",
            "reframe_existing_claim",
            "connect_unlinked_material",
        ]
    )

    def __post_init__(self) -> None:
        if not self.trigger_note_ids:
            raise GeneratorConfigError("trigger_note_ids must not be empty")
        _require_positive_int(self.budget_tokens, "budget_tokens")


@dataclass
class Contradiction:
    personality_note_id: str
    claim_summary: str
    counter_evidence_ids: list[str]
    counter_summary: str


@dataclass
class GeneratorOutput:
    content: str
    intent_tag: str
    output_mode: str
    importance_score: float
    is_lateral: bool
    source_note_ids: list[str]
    contradictions_noted: list[Contradiction]
    token_usage: TokenUsage
    originating_message_id: str | None = None

    def __post_init__(self) -> None:
        _require_probability(self.importance_score, "importance_score")


@dataclass
class PersonalitySnapshot:
    personality_files: list[MemoryNote]
    relevant_patterns: list[MemoryNote]
    contradictions: list[Contradiction]
    ambient_context: AmbientContext


@dataclass
class LengthThresholds:
    short_max: int = 500
    medium_max: int = 3000

    def __post_init__(self) -> None:
        _require_positive_int(self.short_max, "short_max")
        _require_positive_int(self.medium_max, "medium_max")
        if self.short_max > self.medium_max:
            raise GeneratorConfigError("short_max must be less than or equal to medium_max")


@dataclass
class RouterConfig:
    length_thresholds: LengthThresholds = field(default_factory=LengthThresholds)
    intent_routing: dict[str, str] = field(
        default_factory=lambda: {
            "internal_note": "log",
            "log_surfacing": "log",
            "subscription_proposal": "log",
        }
    )

    def __post_init__(self) -> None:
        invalid_targets = [
            target
            for target in self.intent_routing.values()
            if target != "log" and not target
        ]
        if invalid_targets:
            raise GeneratorConfigError("intent_routing targets must be 'log' or a platform name")
