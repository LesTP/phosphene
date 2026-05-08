"""MVP Orchestrator lifecycle shell."""

from __future__ import annotations

from datetime import datetime, timezone

from croniter import croniter

from phosphene.orchestrator.errors import ConfigError
from phosphene.orchestrator.types import ModuleRefs, MVPOrchestratorConfig, ScheduleEntry


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
