from datetime import datetime, timedelta, timezone
import json

import phosphene.distillation as distillation
from phosphene.distillation import (
    DistillationConfig,
    DistillationConfigError,
    DistillationEngine,
    DistillationError,
    DistillationLockError,
    InsufficientDataError,
    NoPatternDataError,
)
from phosphene.distillation.engine import _DistillationRunMetadata


class CallableSentinel:
    def __call__(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("foundation must not call toolkit services")


class FoundationMemoryStore:
    def __init__(
        self,
        vault_path,
        *,
        tier1_created_at: list[datetime] | None = None,
        tier2_count: int = 0,
    ) -> None:
        self.vault_path = vault_path
        self.tier1_created_at = tier1_created_at or []
        self.tier2_count = tier2_count
        self.queries = []
        self.write_calls: list[str] = []

    def query_notes(self, query):
        self.queries.append(query)
        if query.tier == 1:
            notes = [
                object()
                for created_at in self.tier1_created_at
                if query.since is None or created_at >= query.since
            ]
        elif query.tier == 2:
            notes = [object() for _ in range(self.tier2_count)]
        else:
            notes = []
        return notes[: query.limit]

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        self.write_calls.append("store_note")
        raise AssertionError("foundation must not store Memory Store notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("update_note")
        raise AssertionError("foundation must not update Memory Store notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("add_links")
        raise AssertionError("foundation must not add Memory Store links")

    def get_personality_context(self) -> object:
        self.write_calls.append("get_personality_context")
        raise AssertionError("foundation must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("supersede")
        raise AssertionError("foundation must not supersede Memory Store notes")


def test_foundation_checks_gates_without_toolkit_calls_or_memory_store_writes(tmp_path) -> None:
    last_t1_run = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        microsecond=0
    )
    store = FoundationMemoryStore(
        tmp_path / "vault",
        tier1_created_at=[
            last_t1_run - timedelta(seconds=1),
            last_t1_run,
            last_t1_run + timedelta(seconds=1),
        ],
        tier2_count=1,
    )
    engine = DistillationEngine(store)
    engine._write_run_metadata(
        _DistillationRunMetadata(last_t1_to_t2_run=last_t1_run)
    )

    gates = engine.check_gates(
        DistillationConfig(
            llm_config=CallableSentinel(),
            embedding_config=CallableSentinel(),
            clustering_config=CallableSentinel(),
            llm_configs_rotation=[CallableSentinel()],
            min_tier1_volume=2,
        )
    )

    assert gates.ready is True
    assert gates.t1_to_t2_ready is True
    assert gates.tier1_pending == 2
    assert [query.tier for query in store.queries] == [1, 2]
    assert store.queries[0].since == last_t1_run
    assert store.write_calls == []
    assert json.loads(engine._run_metadata_path.read_text(encoding="utf-8")) == {
        "last_t1_to_t2_run": last_t1_run.isoformat(timespec="seconds"),
        "last_t2_to_t3_run": None,
    }


def test_foundation_public_error_exports_share_distillation_base_class() -> None:
    exported_errors = {
        "DistillationConfigError": DistillationConfigError,
        "DistillationError": DistillationError,
        "DistillationLockError": DistillationLockError,
        "InsufficientDataError": InsufficientDataError,
        "NoPatternDataError": NoPatternDataError,
    }

    assert exported_errors.keys() <= set(distillation.__all__)
    for exported_name, exported_type in exported_errors.items():
        assert getattr(distillation, exported_name) is exported_type

    assert issubclass(DistillationConfigError, DistillationError)
    assert issubclass(DistillationLockError, DistillationError)
    assert issubclass(InsufficientDataError, DistillationError)
    assert issubclass(NoPatternDataError, DistillationError)
