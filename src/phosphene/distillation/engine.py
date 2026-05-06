"""Distillation engine public constructor and private state helpers."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any

from phosphene.distillation.errors import DistillationConfigError, DistillationLockError
from phosphene.distillation.types import (
    DistillationConfig,
    EvolutionResult,
    GateStatus,
    TierPromotionResult,
)
from phosphene.memory_store import NoteQuery

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
_UNBOUNDED_QUERY_LIMIT = 1_000_000


@dataclass(frozen=True)
class _DistillationRunMetadata:
    last_t1_to_t2_run: datetime | None = None
    last_t2_to_t3_run: datetime | None = None


class DistillationEngine:
    """Coordinate tier promotion through a Memory Store.

    Phase 1 exposes the ARCH public shell plus gate evaluation, metadata, and
    locking. Live synthesis operations are implemented in later phases.
    """

    def __init__(self, memory_store):
        _validate_memory_store(memory_store)
        self.memory_store = memory_store
        self._run_metadata_path = (
            Path(memory_store.vault_path) / _METADATA_DIRECTORY / _RUN_METADATA_FILENAME
        )
        self._consolidation_lock = Lock()

    @contextmanager
    def _acquire_consolidation_lock(self):
        acquired = self._consolidation_lock.acquire(blocking=False)
        if not acquired:
            raise DistillationLockError("another distillation run is already active")

        try:
            yield
        finally:
            self._consolidation_lock.release()

    def _is_consolidation_locked(self) -> bool:
        acquired = self._consolidation_lock.acquire(blocking=False)
        if acquired:
            self._consolidation_lock.release()
            return False
        return True

    def check_gates(self, config: DistillationConfig) -> GateStatus:
        """Report whether either distillation path is eligible to run."""
        metadata = self._read_run_metadata()
        now = datetime.now(timezone.utc)
        last_run = _latest_datetime(
            metadata.last_t1_to_t2_run,
            metadata.last_t2_to_t3_run,
        )

        time_since_last_run = _elapsed_since(last_run, now)
        time_gate = (
            time_since_last_run is None
            or time_since_last_run >= config.min_time_between_runs
        )
        lock_gate = not self._is_consolidation_locked()

        tier1_pending = len(
            self.memory_store.query_notes(
                NoteQuery(
                    tier=1,
                    since=metadata.last_t1_to_t2_run,
                    limit=_UNBOUNDED_QUERY_LIMIT,
                )
            )
        )
        tier2_notes = self.memory_store.query_notes(NoteQuery(tier=2, limit=1))
        days_since_last_t3 = _days_since(metadata.last_t2_to_t3_run, now)

        t1_volume_gate = tier1_pending >= config.min_tier1_volume
        t3_cycle_gate = (
            days_since_last_t3 is None
            or days_since_last_t3 >= config.t2_to_t3_cycle_days
        )
        t2_volume_gate = bool(tier2_notes) and t3_cycle_gate
        volume_gate = t1_volume_gate or t2_volume_gate

        t1_to_t2_ready = time_gate and lock_gate and t1_volume_gate
        t2_to_t3_ready = time_gate and lock_gate and t2_volume_gate

        return GateStatus(
            ready=t1_to_t2_ready or t2_to_t3_ready,
            time_gate=time_gate,
            volume_gate=volume_gate,
            lock_gate=lock_gate,
            t1_to_t2_ready=t1_to_t2_ready,
            t2_to_t3_ready=t2_to_t3_ready,
            time_since_last_run=time_since_last_run,
            tier1_pending=tier1_pending,
            days_since_last_t3=days_since_last_t3,
        )

    def distill_t1_to_t2(
        self,
        config: DistillationConfig,
    ) -> TierPromotionResult:
        """Promote Tier 1 notes into Tier 2 clusters.

        RAPTOR clustering and assertion-cache writes are deferred to Phase 2.
        """
        raise NotImplementedError("T1 to T2 distillation is implemented in Phase 2")

    def distill_t2_to_t3(
        self,
        config: DistillationConfig,
    ) -> EvolutionResult:
        """Evolve Tier 2 patterns into Tier 3 personality files.

        Reflect-evolve synthesis and supersession are deferred to Phase 3.
        """
        raise NotImplementedError("T2 to T3 distillation is implemented in Phase 3")

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


def _latest_datetime(*values: datetime | None) -> datetime | None:
    datetimes = [_ensure_aware(value) for value in values if value is not None]
    if not datetimes:
        return None
    return max(datetimes)


def _elapsed_since(value: datetime | None, now: datetime) -> timedelta | None:
    if value is None:
        return None
    return now - _ensure_aware(value)


def _days_since(value: datetime | None, now: datetime) -> int | None:
    elapsed = _elapsed_since(value, now)
    if elapsed is None:
        return None
    return elapsed.days


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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
