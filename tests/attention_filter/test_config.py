import pytest

from phosphene.attention_filter import (
    AttentionFilterConfig,
    FilterCriterion,
    InvalidScoreError,
    ScoringConfig,
    default_prompt_criteria,
)


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def test_default_prompt_criteria_uses_precision_surplus_only() -> None:
    criteria = default_prompt_criteria()

    assert len(criteria) == 1
    assert criteria[0].name == "precision_surplus"
    assert "precise claim" in criteria[0].description
    assert criteria[0].weight == 1.0


def test_default_prompt_criteria_returns_fresh_list() -> None:
    first = default_prompt_criteria()
    second = default_prompt_criteria()

    first.append(FilterCriterion(name="custom", description="Custom criterion"))

    assert [criterion.name for criterion in second] == ["precision_surplus"]


def test_attention_filter_config_defaults_to_precision_surplus_only() -> None:
    config = make_config()

    assert [criterion.name for criterion in config.prompt_criteria] == ["precision_surplus"]


@pytest.mark.parametrize("acceptance_threshold", [0.0, 1.0])
def test_attention_filter_config_accepts_threshold_boundaries(
    acceptance_threshold: float,
) -> None:
    config = make_config(acceptance_threshold=acceptance_threshold)

    assert config.acceptance_threshold == acceptance_threshold


@pytest.mark.parametrize("acceptance_threshold", [-0.1, 1.1])
def test_attention_filter_config_rejects_acceptance_threshold_outside_unit_interval(
    acceptance_threshold: float,
) -> None:
    with pytest.raises(InvalidScoreError):
        make_config(acceptance_threshold=acceptance_threshold)


@pytest.mark.parametrize("density_crossover", [0.0, -0.1])
def test_attention_filter_config_rejects_non_positive_density_crossover(
    density_crossover: float,
) -> None:
    with pytest.raises(InvalidScoreError):
        make_config(density_crossover=density_crossover)


@pytest.mark.parametrize(
    "field_name",
    [
        "precision_surplus_weight",
        "liminality_weight",
        "friction_weight",
        "unexpected_connection_weight",
        "structural_insight_weight",
        "link_density_weight",
        "cluster_novelty_weight",
        "unresolvedness_affinity_weight",
    ],
)
def test_scoring_config_rejects_negative_weights(field_name: str) -> None:
    with pytest.raises(InvalidScoreError):
        ScoringConfig(**{field_name: -0.1})


@pytest.mark.parametrize("phase2_max_weight", [0.0, 1.0])
def test_scoring_config_accepts_phase2_max_weight_boundaries(
    phase2_max_weight: float,
) -> None:
    config = ScoringConfig(phase2_max_weight=phase2_max_weight)

    assert config.phase2_max_weight == phase2_max_weight


@pytest.mark.parametrize("phase2_max_weight", [-0.1, 1.1])
def test_scoring_config_rejects_phase2_max_weight_outside_unit_interval(
    phase2_max_weight: float,
) -> None:
    with pytest.raises(InvalidScoreError):
        ScoringConfig(phase2_max_weight=phase2_max_weight)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("note_count_threshold", 0),
        ("note_count_threshold", -1),
        ("cluster_count_threshold", 0),
        ("cluster_count_threshold", -1),
    ],
)
def test_scoring_config_rejects_non_positive_triple_gate_thresholds(
    field_name: str, value: int
) -> None:
    with pytest.raises(InvalidScoreError):
        ScoringConfig(**{field_name: value})
