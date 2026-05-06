from dataclasses import fields
from datetime import timedelta

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
    memory_store = object()
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
    assert gates.ready is True
    assert promotion.assertion_cache_updated == ["group-1"]
    assert evolution.insights == [insight]
    assert engine.memory_store is memory_store
    assert issubclass(DistillationConfigError, DistillationError)
    assert issubclass(DistillationLockError, DistillationError)
    assert issubclass(InsufficientDataError, DistillationError)
    assert issubclass(NoPatternDataError, DistillationError)
