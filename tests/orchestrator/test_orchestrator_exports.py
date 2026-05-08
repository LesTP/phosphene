from dataclasses import fields
from datetime import datetime, timezone

import pytest

import phosphene.orchestrator as orchestrator
from phosphene.orchestrator import (
    ActivationResult,
    ConfigError,
    MVPOrchestrator,
    MVPOrchestratorConfig,
    ModuleRefs,
    OrchestratorError,
    ScheduleEntry,
    UnknownTaskTypeError,
)


class CallableProbe:
    def __init__(self) -> None:
        self.called = False

    def __call__(self, *args: object, **kwargs: object) -> None:
        self.called = True
        raise AssertionError("validation must not call module methods")


class ValidMemoryStore:
    def __init__(self) -> None:
        self.store_note = CallableProbe()
        self.get_density_metrics = CallableProbe()
        self.get_personality_context = CallableProbe()
        self.run_decay = CallableProbe()


class ValidGateway:
    def __init__(self) -> None:
        self.send = CallableProbe()


def build_modules(
    *,
    memory_store: object | None = None,
    gateway: object | None = None,
) -> ModuleRefs:
    return ModuleRefs(
        memory_store=ValidMemoryStore() if memory_store is None else memory_store,
        attention_filter=object(),
        source_ingestion=object(),
        distillation_engine=object(),
        generator=object(),
        gateway=ValidGateway() if gateway is None else gateway,
    )


def build_config(
    *,
    schedule: list[ScheduleEntry] | None = None,
) -> MVPOrchestratorConfig:
    return MVPOrchestratorConfig(
        schedule=schedule
        if schedule is not None
        else [ScheduleEntry(task_type="ingestion", cron="0 */4 * * *")],
        generation_prompt=object(),
        attention_filter_config=object(),
        distillation_config=object(),
        generator_config=object(),
        router_config=object(),
    )


def test_package_exports_arch_public_api() -> None:
    expected_exports = {
        "ActivationResult",
        "ConfigError",
        "MVPOrchestrator",
        "MVPOrchestratorConfig",
        "ModuleRefs",
        "OrchestratorError",
        "ScheduleEntry",
        "UnknownTaskTypeError",
    }

    assert set(orchestrator.__all__) == expected_exports
    for exported_name in expected_exports:
        assert getattr(orchestrator, exported_name) is not None


def test_arch_dataclass_field_names_match_contract() -> None:
    assert [field.name for field in fields(MVPOrchestratorConfig)] == [
        "schedule",
        "generation_prompt",
        "attention_filter_config",
        "distillation_config",
        "generator_config",
        "router_config",
        "log_path",
    ]
    assert [field.name for field in fields(ScheduleEntry)] == [
        "task_type",
        "cron",
        "enabled",
    ]
    assert [field.name for field in fields(ActivationResult)] == [
        "task_type",
        "success",
        "outputs_delivered",
        "error",
        "duration_ms",
        "timestamp",
    ]
    assert [field.name for field in fields(ModuleRefs)] == [
        "memory_store",
        "attention_filter",
        "source_ingestion",
        "distillation_engine",
        "generator",
        "gateway",
    ]


def test_arch_dataclasses_construct_with_expected_defaults() -> None:
    entry = ScheduleEntry(task_type="ingestion", cron="0 */4 * * *")
    before = datetime.now(timezone.utc)
    result = ActivationResult(
        task_type="ingestion",
        success=True,
        outputs_delivered=0,
    )
    after = datetime.now(timezone.utc)

    assert entry.enabled is True
    assert result.error is None
    assert result.duration_ms == 0
    assert before <= result.timestamp <= after
    assert issubclass(ConfigError, OrchestratorError)
    assert issubclass(UnknownTaskTypeError, OrchestratorError)


def test_constructor_stores_modules_and_config_after_validation() -> None:
    modules = build_modules()
    config = build_config()

    instance = MVPOrchestrator(modules, config)

    assert instance.modules is modules
    assert instance.config is config


def test_constructor_rejects_empty_schedule() -> None:
    with pytest.raises(ConfigError, match="schedule must be non-empty"):
        MVPOrchestrator(build_modules(), build_config(schedule=[]))


def test_constructor_rejects_unknown_task_type() -> None:
    config = build_config(schedule=[ScheduleEntry(task_type="respond", cron="0 */4 * * *")])

    with pytest.raises(ConfigError, match="unknown schedule task_type"):
        MVPOrchestrator(build_modules(), config)


def test_constructor_rejects_invalid_cron_expression() -> None:
    config = build_config(schedule=[ScheduleEntry(task_type="ingestion", cron="0 0 0")])

    with pytest.raises(ConfigError, match="must have 5 fields"):
        MVPOrchestrator(build_modules(), config)

    config = build_config(
        schedule=[ScheduleEntry(task_type="ingestion", cron="not cron here * *")]
    )

    with pytest.raises(ConfigError, match="invalid schedule cron"):
        MVPOrchestrator(build_modules(), config)


def test_constructor_rejects_missing_module_ref() -> None:
    modules = build_modules()
    modules.gateway = None

    with pytest.raises(ConfigError, match="modules.gateway is required"):
        MVPOrchestrator(modules, build_config())


def test_constructor_rejects_missing_memory_store_methods() -> None:
    class MissingDensityMetrics:
        store_note = CallableProbe()
        get_personality_context = CallableProbe()
        run_decay = CallableProbe()

    with pytest.raises(ConfigError, match="get_density_metrics"):
        MVPOrchestrator(build_modules(memory_store=MissingDensityMetrics()), build_config())


def test_constructor_rejects_missing_gateway_send() -> None:
    with pytest.raises(ConfigError, match="modules.gateway must provide send"):
        MVPOrchestrator(build_modules(gateway=object()), build_config())


def test_constructor_validation_does_not_call_module_methods() -> None:
    modules = build_modules()

    MVPOrchestrator(modules, build_config())

    memory_store = modules.memory_store
    assert memory_store.store_note.called is False
    assert memory_store.get_density_metrics.called is False
    assert memory_store.get_personality_context.called is False
    assert memory_store.run_decay.called is False
    assert modules.gateway.send.called is False
