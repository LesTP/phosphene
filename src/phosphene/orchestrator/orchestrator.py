"""MVP Orchestrator lifecycle shell."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep
from typing import Callable

import yaml
from croniter import croniter

from phosphene.distillation import (
    DistillationLockError,
    InsufficientDataError,
    NoPatternDataError,
)
from phosphene.generator import EmptyPersonalityError, route
from phosphene.memory_store import NoteInput
from phosphene.orchestrator.errors import ConfigError, UnknownTaskTypeError
from phosphene.orchestrator.types import (
    ActivationResult,
    ModuleRefs,
    MVPOrchestratorConfig,
    ScheduleEntry,
)


ALLOWED_TASK_TYPES = frozenset({"ingestion", "generation", "distillation", "decay"})

_MODULE_REF_FIELDS = (
    "memory_store",
    "attention_filter",
    "source_ingestion",
    "distillation_engine",
    "generator",
    "gateway",
)

_MEMORY_STORE_METHODS = (
    "store_note",
    "get_density_metrics",
    "get_personality_context",
    "run_decay",
)


class MVPOrchestrator:
    """MVP Orchestrator contract and lifecycle entry point."""

    def __init__(
        self,
        modules: ModuleRefs,
        config: MVPOrchestratorConfig,
    ) -> None:
        self._validate_config(config)
        self._validate_modules(modules)
        self.modules = modules
        self.config = config
        self._last_check_by_entry_index: dict[int, datetime] = {}
        self._stop_requested = False

    def start(self) -> None:
        """Block in the sleep-poll lifecycle loop until stop is requested."""
        self._stop_requested = False
        self._start_gateway_listener()

        while not self._stop_requested:
            sleep(60)
            if self._stop_requested:
                break

            due_entries = self._next_due_entries(datetime.now(timezone.utc))
            for entry in due_entries:
                self._run_activation(entry.task_type)
                if self._stop_requested:
                    break

    def stop(self) -> None:
        """Signal the lifecycle loop to exit after the current activation."""
        self._stop_requested = True

    def trigger(self, task_type: str) -> ActivationResult:
        """Run a single activation synchronously for testing and operations."""
        return self._run_activation(task_type)

    def _next_due_entries(self, now: datetime) -> list[ScheduleEntry]:
        """Return enabled schedule entries that fired since their last check."""
        normalized_now = _normalize_datetime(now)
        due_entries: list[ScheduleEntry] = []

        for index, entry in enumerate(self.config.schedule):
            previous_check = self._last_check_by_entry_index.get(index)
            self._last_check_by_entry_index[index] = normalized_now

            if previous_check is None or not entry.enabled:
                continue

            normalized_previous_check = _normalize_datetime(previous_check)
            next_fire = croniter(entry.cron, normalized_previous_check).get_next(datetime)
            if _normalize_datetime(next_fire) <= normalized_now:
                due_entries.append(entry)

        return due_entries

    def _run_activation(self, task_type: str) -> ActivationResult:
        """Dispatch an activation through its MVP implementation."""
        if task_type not in ALLOWED_TASK_TYPES:
            raise UnknownTaskTypeError(f"unknown task type: {task_type}")

        if task_type == "ingestion":
            return self._run_isolated_activation(task_type, self._run_ingestion)
        if task_type == "distillation":
            return self._run_isolated_activation(task_type, self._run_distillation)
        if task_type == "generation":
            return self._run_isolated_activation(task_type, self._run_generation)
        if task_type == "decay":
            return self._run_isolated_activation(task_type, self._run_decay)

        return ActivationResult(
            task_type=task_type,
            success=True,
            outputs_delivered=0,
        )

    def _run_isolated_activation(
        self,
        task_type: str,
        runner: Callable[[], ActivationResult],
    ) -> ActivationResult:
        started_at = perf_counter()
        try:
            result = runner()
        except Exception as exc:
            result = ActivationResult(
                task_type=task_type,
                success=False,
                outputs_delivered=0,
                error=str(exc),
                duration_ms=_elapsed_ms(started_at),
            )
            return self._finalize_activation_result(result)

        result.duration_ms = _elapsed_ms(started_at)
        return self._finalize_activation_result(result)

    def _finalize_activation_result(self, result: ActivationResult) -> ActivationResult:
        try:
            self._append_activation_log(result)
        except Exception as exc:
            return ActivationResult(
                task_type=result.task_type,
                success=False,
                outputs_delivered=result.outputs_delivered,
                error=f"activation log failed: {exc}",
                duration_ms=result.duration_ms,
                timestamp=result.timestamp,
            )
        return result

    def _append_activation_log(self, result: ActivationResult) -> None:
        if self.config.log_path is None:
            return

        log_path = self.config.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(_activation_result_to_json(result), sort_keys=True) + "\n"
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"

        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=log_path.parent,
            delete=False,
        ) as temp_file:
            temp_file.write(existing)
            temp_file.write(line)
            temp_name = temp_file.name

        os.replace(temp_name, log_path)

    def _run_ingestion(self) -> ActivationResult:
        results = self.modules.source_ingestion.poll()
        items = [item for result in results for item in result.items]

        if not items:
            return ActivationResult(
                task_type="ingestion",
                success=True,
                outputs_delivered=0,
            )

        filter_result = self.modules.attention_filter.filter_content(
            items,
            self.config.attention_filter_config,
        )

        for fragment in filter_result.accepted:
            self.modules.memory_store.store_note(_note_input_from_fragment(fragment))

        return ActivationResult(
            task_type="ingestion",
            success=True,
            outputs_delivered=0,
        )

    def _run_distillation(self) -> ActivationResult:
        try:
            gates = self.modules.distillation_engine.check_gates(
                self.config.distillation_config
            )
            if not gates.ready:
                return ActivationResult(
                    task_type="distillation",
                    success=True,
                    outputs_delivered=0,
                )

            if gates.t1_to_t2_ready:
                self.modules.distillation_engine.distill_t1_to_t2(
                    self.config.distillation_config
                )

            if gates.t2_to_t3_ready:
                self.modules.distillation_engine.distill_t2_to_t3(
                    self.config.distillation_config
                )
        except (DistillationLockError, InsufficientDataError, NoPatternDataError):
            return ActivationResult(
                task_type="distillation",
                success=True,
                outputs_delivered=0,
            )

        return ActivationResult(
            task_type="distillation",
            success=True,
            outputs_delivered=0,
        )

    def _run_generation(self) -> ActivationResult:
        try:
            context = self.modules.memory_store.get_personality_context()
            if not context.personality_files:
                return ActivationResult(
                    task_type="generation",
                    success=True,
                    outputs_delivered=0,
                )

            output = self.modules.generator.generate(
                self.config.generation_prompt,
                {},
                self.config.generator_config,
            )
            output_path = _save_generation_output(
                self.modules.memory_store,
                output,
                _personality_file_ids(context.personality_files),
            )
        except EmptyPersonalityError:
            return ActivationResult(
                task_type="generation",
                success=True,
                outputs_delivered=0,
            )

        delivery = route(output, self.config.router_config, self.modules.gateway)
        delivery_success = delivery is not None and delivery.success
        _update_generation_delivery_success(output_path, delivery_success)
        delivered = 1 if delivery_success else 0

        return ActivationResult(
            task_type="generation",
            success=True,
            outputs_delivered=delivered,
        )

    def _run_decay(self) -> ActivationResult:
        self.modules.memory_store.run_decay()
        return ActivationResult(
            task_type="decay",
            success=True,
            outputs_delivered=0,
        )

    def _run_respond(self, message: object) -> ActivationResult:
        return self._run_isolated_activation(
            "respond",
            lambda: self._run_respond_inner(message),
        )

    def _run_respond_inner(self, message: object) -> ActivationResult:
        try:
            context = self.modules.memory_store.get_personality_context()
            if not context.personality_files:
                return ActivationResult(
                    task_type="respond",
                    success=True,
                    outputs_delivered=0,
                )

            output = self.modules.generator.respond(
                message,
                {},
                self.config.generator_config,
            )
        except EmptyPersonalityError:
            return ActivationResult(
                task_type="respond",
                success=True,
                outputs_delivered=0,
            )

        delivery = route(output, self.config.router_config, self.modules.gateway)
        delivered = 1 if delivery is not None and delivery.success else 0

        return ActivationResult(
            task_type="respond",
            success=True,
            outputs_delivered=delivered,
        )

    def _start_gateway_listener(self) -> None:
        start_listener = getattr(self.modules.gateway, "start_listener", None)
        if not callable(start_listener):
            return

        if hasattr(self.modules.gateway, "on_message"):
            self.modules.gateway.on_message = self._run_respond

        start_listener()

    @staticmethod
    def _validate_config(config: MVPOrchestratorConfig) -> None:
        if not config.schedule:
            raise ConfigError("schedule must be non-empty")

        for index, entry in enumerate(config.schedule):
            if entry.task_type not in ALLOWED_TASK_TYPES:
                raise ConfigError(
                    f"unknown schedule task_type at index {index}: {entry.task_type}"
                )
            if len(entry.cron.split()) != 5:
                raise ConfigError(f"schedule cron at index {index} must have 5 fields")
            if not croniter.is_valid(entry.cron):
                raise ConfigError(f"invalid schedule cron at index {index}: {entry.cron}")

    @staticmethod
    def _validate_modules(modules: ModuleRefs) -> None:
        for field_name in _MODULE_REF_FIELDS:
            module = getattr(modules, field_name)
            if module is None:
                raise ConfigError(f"modules.{field_name} is required")

        memory_store = modules.memory_store
        for method_name in _MEMORY_STORE_METHODS:
            method = getattr(memory_store, method_name, None)
            if not callable(method):
                raise ConfigError(f"modules.memory_store must provide {method_name}()")

        gateway_send = getattr(modules.gateway, "send", None)
        if not callable(gateway_send):
            raise ConfigError("modules.gateway must provide send()")


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _activation_result_to_json(result: ActivationResult) -> dict[str, object]:
    return {
        "task_type": result.task_type,
        "success": result.success,
        "outputs_delivered": result.outputs_delivered,
        "error": result.error,
        "duration_ms": result.duration_ms,
        "timestamp": result.timestamp.isoformat(),
    }


def _note_input_from_fragment(fragment: object) -> NoteInput:
    friction_target = getattr(fragment, "friction_target", None)
    unresolvedness = (
        float(getattr(fragment, "unresolvedness", 0.0)) if friction_target else 0.0
    )

    return NoteInput(
        tier=1,
        content=getattr(fragment, "content"),
        title=_fragment_title(fragment),
        importance=float(getattr(fragment, "importance_score", 0.0)),
        unresolvedness=unresolvedness,
        links=list(getattr(fragment, "connections", [])),
        tags=list(getattr(fragment, "retention_criteria", [])),
        source=getattr(fragment, "source", None),
        friction_target=friction_target,
        embedding=getattr(fragment, "embedding", None),
    )


def _fragment_title(fragment: object) -> str:
    annotation = getattr(fragment, "annotation", "")
    content = getattr(fragment, "content")
    title_source = annotation or content
    title = " ".join(title_source.split())
    return title[:150] if title else "Untitled"


def _save_generation_output(
    memory_store: object,
    output: object,
    personality_file_ids: list[str],
) -> Path:
    vault_path = getattr(memory_store, "vault_path")
    created_at = datetime.now(timezone.utc)
    outputs_path = vault_path / "outputs"
    outputs_path.mkdir(parents=True, exist_ok=True)

    output_path = outputs_path / _generation_output_filename(output, created_at)
    output_path.write_text(
        _serialize_generation_output(
            output,
            personality_file_ids=personality_file_ids,
            delivery_success=False,
            created_at=created_at,
        ),
        encoding="utf-8",
    )
    return output_path


def _personality_file_ids(personality_files: list[object]) -> list[str]:
    return [
        note_id
        for note_id in (getattr(note, "note_id", None) for note in personality_files)
        if note_id is not None
    ]


def _update_generation_delivery_success(output_path: Path, delivery_success: bool) -> None:
    text = output_path.read_text(encoding="utf-8")
    metadata, body = _split_markdown_frontmatter(text)
    metadata["delivery_success"] = delivery_success
    output_path.write_text(_serialize_frontmatter(metadata, body), encoding="utf-8")


def _generation_output_filename(output: object, created_at: datetime) -> str:
    content = getattr(output, "content")
    slug = _slugify_output_content(content)
    timestamp = created_at.strftime("%Y%m%d%H%M%S")
    digest = hashlib.sha1(
        f"{content}\0{created_at.isoformat()}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{slug}-{timestamp}-{digest}.md"


def _serialize_generation_output(
    output: object,
    *,
    personality_file_ids: list[str],
    delivery_success: bool,
    created_at: datetime,
) -> str:
    metadata = {
        "intent_tag": getattr(output, "intent_tag"),
        "output_mode": getattr(output, "output_mode"),
        "importance_score": getattr(output, "importance_score"),
        "delivery_success": delivery_success,
        "personality_file_ids": personality_file_ids,
        "created_at": created_at.isoformat(timespec="seconds"),
    }
    return _serialize_frontmatter(metadata, getattr(output, "content"))


def _serialize_frontmatter(metadata: dict[str, object], body: str) -> str:
    frontmatter = yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
    )
    return f"---\n{frontmatter}---\n{body}"


def _split_markdown_frontmatter(text: str) -> tuple[dict[str, object], str]:
    frontmatter, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(frontmatter) or {}, body


def _slugify_output_content(content: str) -> str:
    words = re.findall(r"[\w]+", content.lower())
    slug = "-".join(words)[:60].strip("-")
    return slug or "output"
