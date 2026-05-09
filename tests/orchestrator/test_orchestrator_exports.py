import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import phosphene.orchestrator as orchestrator
from phosphene.distillation import (
    DistillationLockError,
    InsufficientDataError,
    NoPatternDataError,
)
from phosphene.gateway import DeliveryResult, InboundMessage
from phosphene.generator import EmptyPersonalityError, GeneratorOutput, RouterConfig
from phosphene.generator.types import TokenUsage
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
from phosphene.orchestrator import orchestrator as orchestrator_module


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


class RecordingMemoryStore(ValidMemoryStore):
    def __init__(self, personality_files: list[object] | None = None) -> None:
        super().__init__()
        self.store_note = self._store_note
        self.get_personality_context = self._get_personality_context
        self.run_decay = self._run_decay
        self.notes: list[object] = []
        self.personality_files = [] if personality_files is None else personality_files
        self.personality_context_calls = 0
        self.decay_calls = 0

    def _store_note(self, note_input: object) -> None:
        self.notes.append(note_input)

    def _get_personality_context(self) -> object:
        self.personality_context_calls += 1
        return SimpleNamespace(personality_files=self.personality_files)

    def _run_decay(self) -> None:
        self.decay_calls += 1


class FakeSourceIngestion:
    def __init__(self, results: list[object]) -> None:
        self.results = results
        self.poll_count = 0

    def poll(self) -> list[object]:
        self.poll_count += 1
        return self.results


class ThrowingSourceIngestion:
    def poll(self) -> list[object]:
        raise RuntimeError("source unavailable")


class FakeAttentionFilter:
    def __init__(self, accepted: list[object]) -> None:
        self.accepted = accepted
        self.calls: list[tuple[list[object], object]] = []

    def filter_content(self, items: list[object], config: object) -> object:
        self.calls.append((items, config))
        return SimpleNamespace(accepted=self.accepted)


class FakeDistillationEngine:
    def __init__(
        self,
        gates: object | None = None,
        *,
        check_error: Exception | None = None,
        t1_error: Exception | None = None,
        t2_error: Exception | None = None,
    ) -> None:
        self.gates = gates
        self.check_error = check_error
        self.t1_error = t1_error
        self.t2_error = t2_error
        self.check_configs: list[object] = []
        self.t1_configs: list[object] = []
        self.t2_configs: list[object] = []

    def check_gates(self, config: object) -> object:
        self.check_configs.append(config)
        if self.check_error is not None:
            raise self.check_error
        return self.gates

    def distill_t1_to_t2(self, config: object) -> None:
        self.t1_configs.append(config)
        if self.t1_error is not None:
            raise self.t1_error

    def distill_t2_to_t3(self, config: object) -> None:
        self.t2_configs.append(config)
        if self.t2_error is not None:
            raise self.t2_error


class FakeGenerator:
    def __init__(
        self,
        output: object | None = None,
        error: Exception | None = None,
    ) -> None:
        self.output = output
        self.error = error
        self.generate_calls: list[tuple[object, object, object]] = []
        self.respond_calls: list[tuple[object, object, object]] = []

    def generate(self, prompt: object, ambient: object, config: object) -> object:
        self.generate_calls.append((prompt, ambient, config))
        if self.error is not None:
            raise self.error
        return self.output

    def respond(self, message: object, ambient: object, config: object) -> object:
        self.respond_calls.append((message, ambient, config))
        if self.error is not None:
            raise self.error
        return self.output


class RoutingGateway(ValidGateway):
    def __init__(
        self,
        delivery_success: bool = True,
        inbound_message: object | None = None,
    ) -> None:
        super().__init__()
        self.config = SimpleNamespace(default_platform="telegram")
        self.delivery_success = delivery_success
        self.inbound_message = inbound_message
        self.sent_messages: list[object] = []
        self.listener_started = False
        self.on_message = lambda message: None
        self.send = self._send

    def _send(self, message: object) -> DeliveryResult:
        self.sent_messages.append(message)
        return DeliveryResult(
            success=self.delivery_success,
            platform=message.platform,
            message_id="msg-1" if self.delivery_success else None,
            error=None if self.delivery_success else "delivery failed",
        )

    def start_listener(self) -> None:
        self.listener_started = True
        if self.inbound_message is not None:
            self.on_message(self.inbound_message)


def build_modules(
    *,
    memory_store: object | None = None,
    attention_filter: object | None = None,
    source_ingestion: object | None = None,
    distillation_engine: object | None = None,
    generator: object | None = None,
    gateway: object | None = None,
) -> ModuleRefs:
    return ModuleRefs(
        memory_store=ValidMemoryStore() if memory_store is None else memory_store,
        attention_filter=object() if attention_filter is None else attention_filter,
        source_ingestion=object() if source_ingestion is None else source_ingestion,
        distillation_engine=object()
        if distillation_engine is None
        else distillation_engine,
        generator=object() if generator is None else generator,
        gateway=ValidGateway() if gateway is None else gateway,
    )


def build_config(
    *,
    log_path: Path | None = None,
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
        router_config=RouterConfig(),
        log_path=log_path,
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


def test_trigger_decay_calls_run_decay_and_returns_success() -> None:
    memory_store = RecordingMemoryStore()
    instance = MVPOrchestrator(
        build_modules(memory_store=memory_store),
        build_config(),
    )

    result = instance.trigger("decay")

    assert result.task_type == "decay"
    assert result.success is True
    assert result.outputs_delivered == 0
    assert result.error is None
    assert memory_store.decay_calls == 1


def test_trigger_returns_failed_result_when_module_raises() -> None:
    instance = MVPOrchestrator(
        build_modules(source_ingestion=ThrowingSourceIngestion()),
        build_config(),
    )

    result = instance.trigger("ingestion")

    assert result.task_type == "ingestion"
    assert result.success is False
    assert result.outputs_delivered == 0
    assert result.error == "source unavailable"
    assert result.duration_ms >= 0


def test_start_continues_to_next_due_activation_after_module_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingestion = ScheduleEntry(task_type="ingestion", cron="0 * * * *")
    decay = ScheduleEntry(task_type="decay", cron="0 * * * *")
    memory_store = RecordingMemoryStore()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            source_ingestion=ThrowingSourceIngestion(),
        ),
        build_config(schedule=[ingestion, decay]),
    )

    def fake_sleep(seconds: int) -> None:
        assert seconds == 60

    monkeypatch.setattr(orchestrator_module, "sleep", fake_sleep)
    monkeypatch.setattr(
        instance,
        "_next_due_entries",
        lambda now: [ingestion, decay],
    )
    monkeypatch.setattr(instance, "stop", lambda: setattr(instance, "_stop_requested", True))

    original_run_decay = memory_store.run_decay

    def stop_after_decay() -> None:
        original_run_decay()
        instance.stop()

    memory_store.run_decay = stop_after_decay

    instance.start()

    assert memory_store.decay_calls == 1


def test_activation_log_appends_json_lines_after_multiple_activations(
    tmp_path,
) -> None:
    log_path = tmp_path / "activation.jsonl"
    memory_store = RecordingMemoryStore()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            source_ingestion=ThrowingSourceIngestion(),
        ),
        build_config(log_path=log_path),
    )

    failed = instance.trigger("ingestion")
    succeeded = instance.trigger("decay")

    lines = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["task_type"] == "ingestion"
    assert lines[0]["success"] is False
    assert lines[0]["error"] == failed.error
    assert lines[0]["outputs_delivered"] == 0
    assert isinstance(lines[0]["duration_ms"], int)
    assert isinstance(lines[0]["timestamp"], str)
    assert lines[1]["task_type"] == "decay"
    assert lines[1]["success"] is True
    assert lines[1]["error"] is None
    assert lines[1]["outputs_delivered"] == succeeded.outputs_delivered


def test_activation_log_is_not_written_when_log_path_missing(tmp_path) -> None:
    instance = MVPOrchestrator(
        build_modules(memory_store=RecordingMemoryStore()),
        build_config(),
    )

    result = instance.trigger("decay")

    assert result.success is True
    assert list(tmp_path.iterdir()) == []


def test_trigger_ingestion_polls_filters_and_stores_accepted_fragments() -> None:
    item_a = SimpleNamespace(content="first", source="rss")
    item_b = SimpleNamespace(content="second", source="telegram")
    fragment = SimpleNamespace(
        content="A precise fragment worth retaining.",
        annotation="Retain this fragment",
        importance_score=0.72,
        unresolvedness=0.61,
        retention_criteria=["precision_surplus", "friction"],
        friction_target="unresolved claim",
        connections=["note-1", "note-2"],
        source="rss",
        embedding=object(),
    )
    memory_store = RecordingMemoryStore()
    source_ingestion = FakeSourceIngestion(
        [
            SimpleNamespace(items=[item_a], adapter_label="rss"),
            SimpleNamespace(items=[item_b], adapter_label="telegram"),
        ]
    )
    attention_filter = FakeAttentionFilter([fragment])
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            attention_filter=attention_filter,
            source_ingestion=source_ingestion,
        ),
        config,
    )

    result = instance.trigger("ingestion")

    assert result.task_type == "ingestion"
    assert result.success is True
    assert result.outputs_delivered == 0
    assert source_ingestion.poll_count == 1
    assert attention_filter.calls == [([item_a, item_b], config.attention_filter_config)]
    assert len(memory_store.notes) == 1
    note = memory_store.notes[0]
    assert note.tier == 1
    assert note.content == fragment.content
    assert note.title == "Retain this fragment"
    assert note.importance == 0.72
    assert note.unresolvedness == 0.61
    assert note.tags == ["precision_surplus", "friction"]
    assert note.links == ["note-1", "note-2"]
    assert note.source == "rss"
    assert note.friction_target == "unresolved claim"
    assert note.embedding is fragment.embedding


def test_trigger_ingestion_with_no_items_skips_filter_and_store() -> None:
    memory_store = RecordingMemoryStore()
    source_ingestion = FakeSourceIngestion([SimpleNamespace(items=[], adapter_label="rss")])
    attention_filter = FakeAttentionFilter([])
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            attention_filter=attention_filter,
            source_ingestion=source_ingestion,
        ),
        build_config(),
    )

    result = instance.trigger("ingestion")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert source_ingestion.poll_count == 1
    assert attention_filter.calls == []
    assert memory_store.notes == []


def test_ingestion_note_title_falls_back_to_content_and_truncates() -> None:
    long_content = " ".join(["word"] * 40)
    fragment = SimpleNamespace(
        content=long_content,
        annotation="",
        importance_score=0.5,
        unresolvedness=0.9,
        retention_criteria=[],
        friction_target=None,
        connections=[],
        source="rss",
        embedding=None,
    )
    memory_store = RecordingMemoryStore()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            attention_filter=FakeAttentionFilter([fragment]),
            source_ingestion=FakeSourceIngestion([SimpleNamespace(items=[object()])]),
        ),
        build_config(),
    )

    instance.trigger("ingestion")

    note = memory_store.notes[0]
    assert note.title == long_content[:150]
    assert note.unresolvedness == 0.0


def test_trigger_distillation_skips_when_gates_not_ready() -> None:
    gates = SimpleNamespace(ready=False, t1_to_t2_ready=False, t2_to_t3_ready=False)
    engine = FakeDistillationEngine(gates)
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(distillation_engine=engine),
        config,
    )

    result = instance.trigger("distillation")

    assert result.task_type == "distillation"
    assert result.success is True
    assert result.outputs_delivered == 0
    assert engine.check_configs == [config.distillation_config]
    assert engine.t1_configs == []
    assert engine.t2_configs == []


def test_trigger_distillation_dispatches_ready_promotions() -> None:
    gates = SimpleNamespace(ready=True, t1_to_t2_ready=True, t2_to_t3_ready=True)
    engine = FakeDistillationEngine(gates)
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(distillation_engine=engine),
        config,
    )

    result = instance.trigger("distillation")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert engine.check_configs == [config.distillation_config]
    assert engine.t1_configs == [config.distillation_config]
    assert engine.t2_configs == [config.distillation_config]


@pytest.mark.parametrize(
    "error",
    [
        DistillationLockError("locked"),
        InsufficientDataError("not enough tier 1"),
        NoPatternDataError("no tier 2 patterns"),
    ],
)
def test_trigger_distillation_treats_expected_exceptions_as_skip(error: Exception) -> None:
    engine = FakeDistillationEngine(
        SimpleNamespace(ready=True, t1_to_t2_ready=True, t2_to_t3_ready=False),
        t1_error=error,
    )
    instance = MVPOrchestrator(
        build_modules(distillation_engine=engine),
        build_config(),
    )

    result = instance.trigger("distillation")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert result.error is None


def make_generator_output(content: str = "generated output") -> GeneratorOutput:
    return GeneratorOutput(
        content=content,
        intent_tag="synthesis",
        output_mode="prompted",
        importance_score=0.5,
        is_lateral=False,
        source_note_ids=["personality-1"],
        contradictions_noted=[],
        token_usage=TokenUsage(),
    )


def test_trigger_generation_skips_bootstrap_without_generator_call() -> None:
    memory_store = RecordingMemoryStore(personality_files=[])
    generator = FakeGenerator(make_generator_output())
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=RoutingGateway(),
        ),
        build_config(),
    )

    result = instance.trigger("generation")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert memory_store.personality_context_calls == 1
    assert generator.generate_calls == []


def test_trigger_generation_catches_empty_personality_error_as_bootstrap_skip() -> None:
    memory_store = RecordingMemoryStore(personality_files=[object()])
    generator = FakeGenerator(error=EmptyPersonalityError("empty"))
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=RoutingGateway(),
        ),
        build_config(),
    )

    result = instance.trigger("generation")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert result.error is None


def test_trigger_generation_routes_output_and_counts_successful_delivery() -> None:
    memory_store = RecordingMemoryStore(personality_files=[object()])
    output = make_generator_output("send this")
    generator = FakeGenerator(output)
    gateway = RoutingGateway()
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=gateway,
        ),
        config,
    )

    result = instance.trigger("generation")

    assert result.success is True
    assert result.outputs_delivered == 1
    assert generator.generate_calls == [
        (config.generation_prompt, {}, config.generator_config)
    ]
    assert len(gateway.sent_messages) == 1
    assert gateway.sent_messages[0].content == "send this"


def test_bootstrap_transitions_to_generation_after_distillation_produces_personality() -> None:
    item = SimpleNamespace(content="seed fragment", source="corpus")
    fragment = SimpleNamespace(
        content="A seed fragment with enough charge to keep.",
        annotation="Seed fragment",
        importance_score=0.8,
        unresolvedness=0.4,
        retention_criteria=["seed"],
        friction_target="open question",
        connections=[],
        source="corpus",
        embedding=None,
    )
    memory_store = RecordingMemoryStore(personality_files=[])

    class BootstrapDistillationEngine(FakeDistillationEngine):
        def distill_t2_to_t3(self, config: object) -> None:
            super().distill_t2_to_t3(config)
            memory_store.personality_files.append(object())

    gates = SimpleNamespace(ready=True, t1_to_t2_ready=True, t2_to_t3_ready=True)
    engine = BootstrapDistillationEngine(gates)
    generator = FakeGenerator(make_generator_output("now active"))
    gateway = RoutingGateway()
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            source_ingestion=FakeSourceIngestion([SimpleNamespace(items=[item])]),
            attention_filter=FakeAttentionFilter([fragment]),
            distillation_engine=engine,
            generator=generator,
            gateway=gateway,
        ),
        config,
    )

    bootstrap_generation = instance.trigger("generation")
    ingestion = instance.trigger("ingestion")
    distillation = instance.trigger("distillation")
    active_generation = instance.trigger("generation")

    assert bootstrap_generation.success is True
    assert bootstrap_generation.outputs_delivered == 0
    assert ingestion.success is True
    assert len(memory_store.notes) == 1
    assert distillation.success is True
    assert engine.t1_configs == [config.distillation_config]
    assert engine.t2_configs == [config.distillation_config]
    assert active_generation.success is True
    assert active_generation.outputs_delivered == 1
    assert generator.generate_calls == [
        (config.generation_prompt, {}, config.generator_config)
    ]
    assert len(gateway.sent_messages) == 1
    assert gateway.sent_messages[0].content == "now active"


def test_end_to_end_content_path_ingests_distills_generates_and_routes_output() -> None:
    rss_item = SimpleNamespace(content="rss item", source="rss")
    telegram_item = SimpleNamespace(content="telegram item", source="telegram")
    fragment = SimpleNamespace(
        content="Filtered material that should enter memory.",
        annotation="Filtered material",
        importance_score=0.74,
        unresolvedness=0.2,
        retention_criteria=["precision_surplus"],
        friction_target=None,
        connections=["note-prior"],
        source="rss",
        embedding=None,
    )
    memory_store = RecordingMemoryStore(personality_files=[object()])
    source_ingestion = FakeSourceIngestion(
        [
            SimpleNamespace(items=[rss_item], adapter_label="rss"),
            SimpleNamespace(items=[telegram_item], adapter_label="telegram"),
        ]
    )
    attention_filter = FakeAttentionFilter([fragment])
    gates = SimpleNamespace(ready=True, t1_to_t2_ready=True, t2_to_t3_ready=True)
    engine = FakeDistillationEngine(gates)
    generator = FakeGenerator(make_generator_output("mvp output"))
    gateway = RoutingGateway()
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            source_ingestion=source_ingestion,
            attention_filter=attention_filter,
            distillation_engine=engine,
            generator=generator,
            gateway=gateway,
        ),
        config,
    )

    ingestion = instance.trigger("ingestion")
    distillation = instance.trigger("distillation")
    generation = instance.trigger("generation")

    assert ingestion.success is True
    assert source_ingestion.poll_count == 1
    assert attention_filter.calls == [
        ([rss_item, telegram_item], config.attention_filter_config)
    ]
    assert len(memory_store.notes) == 1
    assert memory_store.notes[0].content == fragment.content
    assert memory_store.notes[0].links == ["note-prior"]
    assert distillation.success is True
    assert engine.check_configs == [config.distillation_config]
    assert engine.t1_configs == [config.distillation_config]
    assert engine.t2_configs == [config.distillation_config]
    assert generation.success is True
    assert generation.outputs_delivered == 1
    assert generator.generate_calls == [
        (config.generation_prompt, {}, config.generator_config)
    ]
    assert len(gateway.sent_messages) == 1
    assert gateway.sent_messages[0].content == "mvp output"


def test_restart_reconstructs_schedule_and_uses_persisted_memory_state() -> None:
    schedule = [ScheduleEntry(task_type="ingestion", cron="0 * * * *")]
    fragment = SimpleNamespace(
        content="Material stored before restart.",
        annotation="Stored before restart",
        importance_score=0.7,
        unresolvedness=0.0,
        retention_criteria=[],
        friction_target=None,
        connections=[],
        source="rss",
        embedding=None,
    )
    memory_store = RecordingMemoryStore(personality_files=[])
    config = build_config(schedule=schedule)
    first = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            source_ingestion=FakeSourceIngestion([SimpleNamespace(items=[object()])]),
            attention_filter=FakeAttentionFilter([fragment]),
        ),
        config,
    )

    first._next_due_entries(datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc))
    assert first._next_due_entries(
        datetime(2026, 5, 9, 13, 1, tzinfo=timezone.utc)
    ) == schedule

    ingestion = first.trigger("ingestion")
    memory_store.personality_files.append(object())
    memory_store.distillation_metadata = {"last_run_id": "distill-1"}

    gateway = RoutingGateway()
    generator = FakeGenerator(make_generator_output("after restart"))
    second = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=gateway,
        ),
        config,
    )

    first_check_after_restart = second._next_due_entries(
        datetime(2026, 5, 9, 14, 1, tzinfo=timezone.utc)
    )
    generation = second.trigger("generation")

    assert ingestion.success is True
    assert len(memory_store.notes) == 1
    assert memory_store.notes[0].content == fragment.content
    assert memory_store.distillation_metadata == {"last_run_id": "distill-1"}
    assert first_check_after_restart == []
    assert second.config.schedule == schedule
    assert generation.success is True
    assert generation.outputs_delivered == 1
    assert generator.generate_calls == [
        (config.generation_prompt, {}, config.generator_config)
    ]
    assert len(gateway.sent_messages) == 1
    assert gateway.sent_messages[0].content == "after restart"


def test_trigger_generation_treats_delivery_failure_as_zero_delivered() -> None:
    memory_store = RecordingMemoryStore(personality_files=[object()])
    gateway = RoutingGateway(delivery_success=False)
    config = build_config()
    config.router_config = RouterConfig(intent_routing={"synthesis": "telegram"})
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=FakeGenerator(make_generator_output()),
            gateway=gateway,
        ),
        config,
    )

    result = instance.trigger("generation")

    assert result.success is True
    assert result.outputs_delivered == 0
    assert len(gateway.sent_messages) == 1


def test_run_respond_skips_bootstrap_without_generator_call() -> None:
    memory_store = RecordingMemoryStore(personality_files=[])
    generator = FakeGenerator(make_generator_output())
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=RoutingGateway(),
        ),
        build_config(),
    )

    result = instance._run_respond(object())

    assert result.task_type == "respond"
    assert result.success is True
    assert result.outputs_delivered == 0
    assert generator.respond_calls == []


def test_start_listener_dispatches_inbound_message_to_respond(monkeypatch) -> None:
    message = InboundMessage(
        content="hello",
        platform="telegram",
        message_id="in-1",
        sender="human",
        timestamp=datetime(2026, 5, 8, 12, 0),
    )
    memory_store = RecordingMemoryStore(personality_files=[object()])
    generator = FakeGenerator(make_generator_output("reply"))
    gateway = RoutingGateway(inbound_message=message)
    config = build_config()
    instance = MVPOrchestrator(
        build_modules(
            memory_store=memory_store,
            generator=generator,
            gateway=gateway,
        ),
        config,
    )

    def fake_sleep(seconds: int) -> None:
        instance.stop()

    monkeypatch.setattr(orchestrator_module, "sleep", fake_sleep)

    instance.start()

    assert gateway.listener_started is True
    assert generator.respond_calls == [(message, {}, config.generator_config)]
    assert len(gateway.sent_messages) == 1
    assert gateway.sent_messages[0].content == "reply"


def test_run_respond_catches_empty_personality_error_as_bootstrap_drop() -> None:
    instance = MVPOrchestrator(
        build_modules(
            memory_store=RecordingMemoryStore(personality_files=[object()]),
            generator=FakeGenerator(error=EmptyPersonalityError("empty")),
            gateway=RoutingGateway(),
        ),
        build_config(),
    )

    result = instance._run_respond(object())

    assert result.success is True
    assert result.outputs_delivered == 0
    assert result.error is None


def test_trigger_rejects_unknown_task_type() -> None:
    instance = MVPOrchestrator(build_modules(), build_config())

    with pytest.raises(UnknownTaskTypeError, match="unknown task type"):
        instance.trigger("respond")


def test_start_sleep_poll_dispatches_due_entries_sequentially(monkeypatch: pytest.MonkeyPatch) -> None:
    ingestion = ScheduleEntry(task_type="ingestion", cron="0 * * * *")
    decay = ScheduleEntry(task_type="decay", cron="0 * * * *")
    instance = MVPOrchestrator(
        build_modules(),
        build_config(schedule=[ingestion, decay]),
    )
    dispatched: list[str] = []

    def fake_sleep(seconds: int) -> None:
        assert seconds == 60

    def fake_next_due_entries(now: datetime) -> list[ScheduleEntry]:
        assert now.tzinfo is not None
        return [ingestion, decay]

    def fake_run_activation(task_type: str) -> ActivationResult:
        dispatched.append(task_type)
        if task_type == "decay":
            instance.stop()
        return ActivationResult(task_type=task_type, success=True, outputs_delivered=0)

    monkeypatch.setattr(orchestrator_module, "sleep", fake_sleep)
    monkeypatch.setattr(instance, "_next_due_entries", fake_next_due_entries)
    monkeypatch.setattr(instance, "_run_activation", fake_run_activation)

    instance.start()

    assert dispatched == ["ingestion", "decay"]


def test_stop_before_poll_exits_start_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    instance = MVPOrchestrator(build_modules(), build_config())

    def fake_sleep(seconds: int) -> None:
        assert seconds == 60
        instance.stop()

    monkeypatch.setattr(orchestrator_module, "sleep", fake_sleep)
    monkeypatch.setattr(
        instance,
        "_next_due_entries",
        lambda now: pytest.fail("stop after sleep should exit before polling"),
    )

    instance.start()


def test_next_due_entries_initializes_without_returning_due_entries() -> None:
    instance = MVPOrchestrator(
        build_modules(),
        build_config(
            schedule=[
                ScheduleEntry(task_type="ingestion", cron="0 * * * *"),
                ScheduleEntry(task_type="generation", cron="30 * * * *"),
            ]
        ),
    )

    due = instance._next_due_entries(datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc))

    assert due == []


def test_next_due_entries_returns_entries_that_fired_since_last_check() -> None:
    ingestion = ScheduleEntry(task_type="ingestion", cron="0 * * * *")
    generation = ScheduleEntry(task_type="generation", cron="30 * * * *")
    instance = MVPOrchestrator(
        build_modules(),
        build_config(schedule=[ingestion, generation]),
    )

    instance._next_due_entries(datetime(2026, 5, 8, 12, 1, tzinfo=timezone.utc))
    due = instance._next_due_entries(datetime(2026, 5, 8, 12, 31, tzinfo=timezone.utc))

    assert due == [generation]


def test_next_due_entries_tracks_each_schedule_entry_independently() -> None:
    hourly_ingestion = ScheduleEntry(task_type="ingestion", cron="0 * * * *")
    daily_decay = ScheduleEntry(task_type="decay", cron="0 3 * * *")
    instance = MVPOrchestrator(
        build_modules(),
        build_config(schedule=[hourly_ingestion, daily_decay]),
    )

    instance._next_due_entries(datetime(2026, 5, 8, 2, 58, tzinfo=timezone.utc))
    due = instance._next_due_entries(datetime(2026, 5, 8, 3, 1, tzinfo=timezone.utc))

    assert due == [hourly_ingestion, daily_decay]


def test_next_due_entries_ignores_disabled_entries() -> None:
    enabled_entry = ScheduleEntry(task_type="ingestion", cron="0 * * * *")
    disabled_entry = ScheduleEntry(
        task_type="distillation",
        cron="0 * * * *",
        enabled=False,
    )
    instance = MVPOrchestrator(
        build_modules(),
        build_config(schedule=[enabled_entry, disabled_entry]),
    )

    instance._next_due_entries(datetime(2026, 5, 8, 11, 30, tzinfo=timezone.utc))
    due = instance._next_due_entries(datetime(2026, 5, 8, 12, 1, tzinfo=timezone.utc))

    assert due == [enabled_entry]
