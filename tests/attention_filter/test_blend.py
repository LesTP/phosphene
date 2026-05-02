import pytest

from phosphene.attention_filter import (
    AttentionFilterConfig,
    ScoringConfig,
    compute_blend_weights,
    phase2_is_active,
)
from phosphene.memory_store import DensityMetrics


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def metrics(
    *,
    note_count: int = 50,
    cluster_count: int = 3,
    mean_link_degree: float = 1.5,
) -> DensityMetrics:
    return DensityMetrics(
        note_count=note_count,
        tier_counts={1: note_count, 2: 0, 3: 0},
        mean_link_degree=mean_link_degree,
        cluster_count=cluster_count,
        unresolved_count=0,
        max_unresolvedness=0.0,
    )


def test_empty_memory_fails_gate_and_uses_pure_prompt() -> None:
    config = make_config()
    empty = metrics(note_count=0, cluster_count=0, mean_link_degree=0.0)

    assert phase2_is_active(empty, config) is False
    assert compute_blend_weights(empty, config) == (1.0, 0.0)


@pytest.mark.parametrize(
    "density",
    [
        metrics(note_count=49),
        metrics(cluster_count=2),
        metrics(mean_link_degree=1.49),
    ],
)
def test_triple_gate_requires_all_thresholds(density: DensityMetrics) -> None:
    assert phase2_is_active(density, make_config()) is False


def test_exactly_at_triple_gate_threshold_activates_with_zero_structure_weight() -> None:
    config = make_config()
    density = metrics()

    assert phase2_is_active(density, config) is True
    assert compute_blend_weights(density, config) == (1.0, 0.0)


def test_blend_ramps_linearly_between_half_and_double_crossover() -> None:
    config = make_config()
    density = metrics(mean_link_degree=3.75)

    assert compute_blend_weights(density, config) == pytest.approx((0.65, 0.35))


def test_high_density_hits_phase2_max_weight_cap() -> None:
    config = make_config(scoring=ScoringConfig(phase2_max_weight=0.8))
    density = metrics(mean_link_degree=99.0)

    assert compute_blend_weights(density, config) == pytest.approx((0.2, 0.8))


def test_custom_density_crossover_sets_gate_and_ramp_points() -> None:
    config = make_config(density_crossover=4.0)

    assert phase2_is_active(metrics(mean_link_degree=1.99), config) is False
    assert compute_blend_weights(metrics(mean_link_degree=5.0), config) == pytest.approx(
        (0.65, 0.35)
    )
