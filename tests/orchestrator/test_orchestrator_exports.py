from dataclasses import fields
from datetime import datetime, timezone

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


class ExplodingModule:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"constructor must not inspect module attribute {name}")


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


def test_constructor_stores_modules_and_config_without_validation() -> None:
    module = ExplodingModule()
    modules = ModuleRefs(
        memory_store=module,
        attention_filter=module,
        source_ingestion=module,
        distillation_engine=module,
        generator=module,
        gateway=module,
    )
    config = MVPOrchestratorConfig(
        schedule=[],
        generation_prompt=object(),
        attention_filter_config=object(),
        distillation_config=object(),
        generator_config=object(),
        router_config=object(),
    )

    instance = MVPOrchestrator(modules, config)

    assert instance.modules is modules
    assert instance.config is config
