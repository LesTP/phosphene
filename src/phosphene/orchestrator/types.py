"""Dataclasses for the MVP Orchestrator public API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from phosphene.attention_filter import AttentionFilterConfig
from phosphene.distillation import DistillationConfig
from phosphene.generator import GenerationPrompt, GeneratorConfig, RouterConfig


@dataclass
class ScheduleEntry:
    task_type: str
    cron: str
    enabled: bool = True


@dataclass
class MVPOrchestratorConfig:
    schedule: list[ScheduleEntry]
    generation_prompt: GenerationPrompt
    attention_filter_config: AttentionFilterConfig
    distillation_config: DistillationConfig
    generator_config: GeneratorConfig
    router_config: RouterConfig
    log_path: Path | None = None


@dataclass
class ActivationResult:
    task_type: str
    success: bool
    outputs_delivered: int
    error: str | None = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ModuleRefs:
    memory_store: Any
    attention_filter: Any
    source_ingestion: Any
    distillation_engine: Any
    generator: Any
    gateway: Any
