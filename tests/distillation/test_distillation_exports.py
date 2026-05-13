from dataclasses import fields
from datetime import timedelta

import pytest

import phosphene.distillation as distillation
from phosphene.distillation import (
    CriteriaAdjustment,
    DistillationConfig,
    DistillationConfigError,
    DistillationEngine,
    DistillationError,
    DistillationLockError,
    EvolutionResult,
    GateStatus,
    InsufficientDataError,
    NoPatternDataError,
    ReflectionInsight,
    SupersessionRecord,
    TierPromotionResult,
)
from phosphene.distillation.types import ModelTier


class FakeMemoryStore:
    vault_path = "/tmp/phosphene-test-vault"

    def query_notes(self, *_args: object, **_kwargs: object) -> list[object]:
        return []

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        return "note-id"

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        return object()

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        return None

    def get_personality_context(self) -> object:
        return object()

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        return object()


def test_package_exports_arch_public_api() -> None:
    expected_exports = {
        "CriteriaAdjustment",
        "DistillationConfig",
        "DistillationConfigError",
        "DistillationEngine",
        "DistillationError",
        "DistillationLockError",
        "EvolutionResult",
        "GateStatus",
        "InsufficientDataError",
        "NoPatternDataError",
        "ReflectionInsight",
        "SupersessionRecord",
        "TierPromotionResult",
    }

    assert set(distillation.__all__) == expected_exports
    for exported_name in expected_exports:
        assert getattr(distillation, exported_name) is not None


def test_arch_dataclass_field_names_match_contract() -> None:
    assert [field.name for field in fields(DistillationConfig)] == [
        "llm_config",
        "llm_configs_rotation",
        "reflection_tier",
        "evolution_tier",
        "embedding_config",
        "clustering_config",
        "min_time_between_runs",
        "min_tier1_volume",
        "t2_to_t3_cycle_days",
        "inertia_per_cycle",
        "max_inertia",
        "max_compression_ratio",
        "incorporate_feedback",
        "min_cluster_coherence",
        "cross_link_threshold",
        "max_cross_links",
    ]
    assert [field.name for field in fields(GateStatus)] == [
        "ready",
        "time_gate",
        "volume_gate",
        "lock_gate",
        "t1_to_t2_ready",
        "t2_to_t3_ready",
        "time_since_last_run",
        "tier1_pending",
        "days_since_last_t3",
    ]
    assert [field.name for field in fields(TierPromotionResult)] == [
        "new_cluster_ids",
        "updated_cluster_ids",
        "promoted_count",
        "noise_count",
        "incoherent_cluster_count",
        "cluster_tree_depth",
        "feedback_processed",
        "assertion_cache_updated",
    ]
    assert [field.name for field in fields(ReflectionInsight)] == [
        "content",
        "source_pattern_ids",
        "insight_type",
        "confidence",
    ]
    assert [field.name for field in fields(SupersessionRecord)] == [
        "old_note_id",
        "new_note_id",
        "change_summary",
    ]
    assert [field.name for field in fields(CriteriaAdjustment)] == [
        "criterion_name",
        "old_weight",
        "new_weight",
        "evidence",
    ]
    assert [field.name for field in fields(EvolutionResult)] == [
        "insights",
        "superseded",
        "unchanged_ids",
        "criteria_adjustments",
        "compression_ratio",
    ]


def test_engine_exposes_arch_public_methods() -> None:
    engine = DistillationEngine(memory_store=FakeMemoryStore())

    assert callable(engine.check_gates)
    assert callable(engine.distill_t1_to_t2)
    assert callable(engine.distill_t2_to_t3)


def test_arch_dataclasses_construct_with_expected_defaults() -> None:
    config = DistillationConfig(llm_config=object(), embedding_config=object())
    gates = GateStatus(
        ready=True,
        time_gate=True,
        volume_gate=True,
        lock_gate=True,
        t1_to_t2_ready=True,
        t2_to_t3_ready=False,
        time_since_last_run=timedelta(days=2),
        tier1_pending=25,
        days_since_last_t3=None,
    )
    promotion = TierPromotionResult(
        new_cluster_ids=["cluster-1"],
        updated_cluster_ids=[],
        promoted_count=20,
        noise_count=2,
        incoherent_cluster_count=1,
        cluster_tree_depth=2,
        feedback_processed=3,
        assertion_cache_updated=["group-1"],
    )
    insight = ReflectionInsight(
        content="A recurring tension is visible.",
        source_pattern_ids=["pattern-1"],
        insight_type="recurring_tension",
        confidence=0.8,
    )
    supersession = SupersessionRecord(
        old_note_id="personality-old",
        new_note_id="personality-new",
        change_summary="Resolved a contradiction.",
    )
    adjustment = CriteriaAdjustment(
        criterion_name="friction",
        old_weight=1.0,
        new_weight=1.2,
        evidence="Friction-led outputs retained attention.",
    )
    evolution = EvolutionResult(
        insights=[insight],
        superseded=[supersession],
        unchanged_ids=["personality-stable"],
        criteria_adjustments=[adjustment],
        compression_ratio=0.25,
    )
    memory_store = FakeMemoryStore()
    engine = DistillationEngine(memory_store=memory_store)

    assert config.llm_configs_rotation is None
    assert config.reflection_tier == ModelTier.QUALITY
    assert config.evolution_tier == ModelTier.QUALITY
    assert config.clustering_config is None
    assert config.min_time_between_runs == timedelta(hours=24)
    assert config.min_tier1_volume == 20
    assert config.t2_to_t3_cycle_days == 30
    assert config.inertia_per_cycle == 0.25
    assert config.max_inertia == 3.0
    assert config.max_compression_ratio == 0.5
    assert config.incorporate_feedback is True
    assert config.min_cluster_coherence == 0.4
    assert config.cross_link_threshold == 0.45
    assert config.max_cross_links == 15
    assert gates.ready is True
    assert promotion.assertion_cache_updated == ["group-1"]
    assert evolution.insights == [insight]
    assert engine.memory_store is memory_store
    assert issubclass(DistillationConfigError, DistillationError)
    assert issubclass(DistillationLockError, DistillationError)
    assert issubclass(InsufficientDataError, DistillationError)
    assert issubclass(NoPatternDataError, DistillationError)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("llm_config", None, "llm_config is required"),
        ("embedding_config", None, "embedding_config is required"),
        ("min_time_between_runs", timedelta(seconds=-1), "min_time_between_runs must be non-negative"),
        ("min_tier1_volume", 0, "min_tier1_volume must be positive"),
        ("t2_to_t3_cycle_days", 0, "t2_to_t3_cycle_days must be positive"),
        ("inertia_per_cycle", -0.1, "inertia_per_cycle must be non-negative"),
        ("max_inertia", 0.9, "max_inertia must be at least 1.0"),
        ("max_compression_ratio", 1.1, r"max_compression_ratio must be in \[0.0, 1.0\]"),
        ("min_cluster_coherence", -0.1, r"min_cluster_coherence must be in \[0.0, 1.0\]"),
        ("cross_link_threshold", 1.1, r"cross_link_threshold must be in \[0.0, 1.0\]"),
        ("max_cross_links", -1, "max_cross_links must be non-negative"),
    ],
)
def test_distillation_config_validates_thresholds_and_required_toolkit_configs(
    field_name: str,
    value: object,
    message: str,
) -> None:
    kwargs = {"llm_config": object(), "embedding_config": object(), field_name: value}

    with pytest.raises(DistillationConfigError, match=message):
        DistillationConfig(**kwargs)


def test_distillation_config_validates_rotation_entries_without_toolkit_calls() -> None:
    with pytest.raises(
        DistillationConfigError,
        match=r"llm_configs_rotation\[1\] is required",
    ):
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            llm_configs_rotation=[object(), None],
        )


def test_engine_validates_memory_store_dependency_shape() -> None:
    with pytest.raises(DistillationConfigError, match="memory_store is required"):
        DistillationEngine(memory_store=None)

    with pytest.raises(DistillationConfigError, match=r"memory_store must provide query_notes\(\)"):
        DistillationEngine(memory_store=object())


def test_engine_requires_memory_store_vault_path_for_distillation_metadata() -> None:
    class MissingVaultPath(FakeMemoryStore):
        vault_path = None

    with pytest.raises(DistillationConfigError, match="memory_store must expose vault_path"):
        DistillationEngine(memory_store=MissingVaultPath())


def test_distill_t2_to_t3_requires_pattern_data_without_side_effects() -> None:
    engine = DistillationEngine(memory_store=FakeMemoryStore())
    config = DistillationConfig(llm_config=object(), embedding_config=object())

    with pytest.raises(
        NoPatternDataError,
        match="requires at least one Tier 2 pattern note",
    ):
        engine.distill_t2_to_t3(config)
