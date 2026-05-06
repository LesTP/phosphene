"""Distillation engine public constructor and private state helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from phosphene.distillation.errors import DistillationConfigError

_REQUIRED_MEMORY_STORE_METHODS = (
    "query_notes",
    "store_note",
    "update_note",
    "add_links",
    "get_personality_context",
    "supersede",
)
_METADATA_DIRECTORY = ".phosphene"
_RUN_METADATA_FILENAME = "distillation_runs.json"
_LAST_T1_TO_T2_KEY = "last_t1_to_t2_run"
_LAST_T2_TO_T3_KEY = "last_t2_to_t3_run"


@dataclass(frozen=True)
class _DistillationRunMetadata:
    last_t1_to_t2_run: datetime | None = None
    last_t2_to_t3_run: datetime | None = None


class DistillationEngine:
    """Coordinate tier promotion through a Memory Store.

    Phase 1 starts with the constructor-only public shell. Gate evaluation,
    metadata, locking, and synthesis operations are added in subsequent steps.
    """

    def __init__(self, memory_store):
        _validate_memory_store(memory_store)
        self.memory_store = memory_store
        self._run_metadata_path = (
            Path(memory_store.vault_path) / _METADATA_DIRECTORY / _RUN_METADATA_FILENAME
        )

    def _read_run_metadata(self) -> _DistillationRunMetadata:
        if not self._run_metadata_path.exists():
            return _DistillationRunMetadata()

        try:
            payload = json.loads(self._run_metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return _DistillationRunMetadata()

        if not isinstance(payload, dict):
            return _DistillationRunMetadata()

        return _DistillationRunMetadata(
            last_t1_to_t2_run=_parse_metadata_datetime(payload.get(_LAST_T1_TO_T2_KEY)),
            last_t2_to_t3_run=_parse_metadata_datetime(payload.get(_LAST_T2_TO_T3_KEY)),
        )

    def _write_run_metadata(self, metadata: _DistillationRunMetadata) -> None:
        self._run_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            _LAST_T1_TO_T2_KEY: _format_metadata_datetime(metadata.last_t1_to_t2_run),
            _LAST_T2_TO_T3_KEY: _format_metadata_datetime(metadata.last_t2_to_t3_run),
        }
        temp_path = self._run_metadata_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(self._run_metadata_path)


def _validate_memory_store(memory_store: object) -> None:
    if memory_store is None:
        raise DistillationConfigError("memory_store is required")

    for method_name in _REQUIRED_MEMORY_STORE_METHODS:
        method = getattr(memory_store, method_name, None)
        if not isinstance(method, Callable):
            raise DistillationConfigError(f"memory_store must provide {method_name}()")

    if getattr(memory_store, "vault_path", None) is None:
        raise DistillationConfigError("memory_store must expose vault_path")


def _parse_metadata_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _format_metadata_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat(timespec="seconds")
