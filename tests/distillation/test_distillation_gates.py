from datetime import datetime, timedelta, timezone

from phosphene.distillation import DistillationConfig, DistillationEngine
from phosphene.distillation.engine import _DistillationRunMetadata


class GateMemoryStore:
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
        raise AssertionError("check_gates must not store notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("check_gates must not update notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("check_gates must not add links")

    def get_personality_context(self) -> object:
        raise AssertionError("check_gates must not load personality context")

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("check_gates must not supersede notes")


def test_check_gates_treats_missing_metadata_as_never_run_and_counts_all_tier1(tmp_path) -> None:
    store = GateMemoryStore(
        tmp_path / "vault",
        tier1_created_at=[datetime(2026, 5, 1, tzinfo=timezone.utc) for _ in range(3)],
    )
    engine = DistillationEngine(store)

    gates = engine.check_gates(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=3,
        )
    )

    assert gates.ready is True
    assert gates.time_gate is True
    assert gates.volume_gate is True
    assert gates.lock_gate is True
    assert gates.t1_to_t2_ready is True
    assert gates.t2_to_t3_ready is False
    assert gates.time_since_last_run is None
    assert gates.tier1_pending == 3
    assert gates.days_since_last_t3 is None
    assert store.queries[0].tier == 1
    assert store.queries[0].since is None
    assert store.queries[1].tier == 2


def test_check_gates_filters_tier1_pending_since_last_t1_to_t2_run(tmp_path) -> None:
    last_t1_run = (datetime.now(timezone.utc) - timedelta(days=3)).replace(
        microsecond=0
    )
    store = GateMemoryStore(
        tmp_path / "vault",
        tier1_created_at=[
            last_t1_run - timedelta(seconds=1),
            last_t1_run,
            last_t1_run + timedelta(seconds=1),
        ],
    )
    engine = DistillationEngine(store)
    engine._write_run_metadata(_DistillationRunMetadata(last_t1_to_t2_run=last_t1_run))

    gates = engine.check_gates(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=2,
        )
    )

    assert gates.tier1_pending == 2
    assert gates.t1_to_t2_ready is True
    assert store.queries[0].since == last_t1_run


def test_check_gates_blocks_ready_when_time_gate_has_not_elapsed(tmp_path) -> None:
    recent_run = datetime.now(timezone.utc) - timedelta(hours=1)
    store = GateMemoryStore(
        tmp_path / "vault",
        tier1_created_at=[recent_run + timedelta(minutes=1) for _ in range(5)],
        tier2_count=1,
    )
    engine = DistillationEngine(store)
    engine._write_run_metadata(
        _DistillationRunMetadata(
            last_t1_to_t2_run=recent_run,
            last_t2_to_t3_run=recent_run,
        )
    )

    gates = engine.check_gates(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=5,
            min_time_between_runs=timedelta(hours=24),
        )
    )

    assert gates.ready is False
    assert gates.time_gate is False
    assert gates.volume_gate is True
    assert gates.t1_to_t2_ready is False
    assert gates.t2_to_t3_ready is False
    assert gates.time_since_last_run < timedelta(hours=24)


def test_check_gates_reports_monthly_t2_to_t3_readiness_when_patterns_exist(tmp_path) -> None:
    last_t3_run = datetime.now(timezone.utc) - timedelta(days=31)
    store = GateMemoryStore(tmp_path / "vault", tier2_count=1)
    engine = DistillationEngine(store)
    engine._write_run_metadata(_DistillationRunMetadata(last_t2_to_t3_run=last_t3_run))

    gates = engine.check_gates(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            min_tier1_volume=5,
            t2_to_t3_cycle_days=30,
        )
    )

    assert gates.ready is True
    assert gates.volume_gate is True
    assert gates.t1_to_t2_ready is False
    assert gates.t2_to_t3_ready is True
    assert gates.tier1_pending == 0
    assert gates.days_since_last_t3 >= 31


def test_check_gates_reports_lock_gate_without_running_when_locked(tmp_path) -> None:
    store = GateMemoryStore(
        tmp_path / "vault",
        tier1_created_at=[datetime.now(timezone.utc) for _ in range(5)],
    )
    engine = DistillationEngine(store)

    with engine._acquire_consolidation_lock():
        gates = engine.check_gates(
            DistillationConfig(
                llm_config=object(),
                embedding_config=object(),
                min_tier1_volume=5,
            )
        )

    assert gates.ready is False
    assert gates.lock_gate is False
    assert gates.time_gate is True
    assert gates.volume_gate is True
    assert gates.t1_to_t2_ready is False
