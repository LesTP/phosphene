import pytest

from phosphene.attention_filter import (
    ScoringConfig,
    compute_phase2_composite,
    score_cluster_novelty,
    score_friction,
    score_liminality,
    score_link_density,
    score_structural_insight,
    score_unexpected_connection,
    score_unresolvedness_affinity,
)


def test_scoring_config_defaults_match_arch_contract() -> None:
    config = ScoringConfig()

    assert config.precision_surplus_weight == 1.0
    assert config.liminality_weight == 1.0
    assert config.friction_weight == 1.0
    assert config.unexpected_connection_weight == 1.0
    assert config.structural_insight_weight == 1.0
    assert config.link_density_weight == 1.0
    assert config.cluster_novelty_weight == 1.0
    assert config.unresolvedness_affinity_weight == 1.0
    assert config.link_density_sim_threshold == 0.4
    assert config.gap_factor_exponent == 2.0
    assert config.assertion_alignment_threshold == 0.5
    assert config.note_count_threshold == 50
    assert config.cluster_count_threshold == 3
    assert config.phase2_max_weight == 0.7


@pytest.mark.parametrize(
    ("similarities", "expected"),
    [
        ([], 0.0),
        ([0.8], 0.0),
        ([0.8, 0.8], 1.0),
        ([1.0, 0.0], 0.0),
    ],
)
def test_score_liminality_boundaries(similarities: list[float], expected: float) -> None:
    assert score_liminality(similarities) == pytest.approx(expected)


def test_score_liminality_uses_gap_factor_exponent() -> None:
    assert score_liminality([0.8, 0.4], gap_factor_exponent=2.0) == pytest.approx(0.8)


@pytest.mark.parametrize(
    ("topical_sim", "assertion_alignment", "expected"),
    [
        (1.0, 0.0, 1.0),
        (1.0, 1.0, 0.0),
        (0.8, 0.25, 0.6),
        (2.0, -1.0, 1.0),
    ],
)
def test_score_friction_clamps_and_multiplies_misalignment(
    topical_sim: float, assertion_alignment: float, expected: float
) -> None:
    assert score_friction(topical_sim, assertion_alignment) == pytest.approx(expected)


def test_score_unexpected_connection_handles_degenerate_inputs() -> None:
    assert score_unexpected_connection([], {}) == 0.0
    assert score_unexpected_connection([0.8], {}) == 0.0


def test_score_unexpected_connection_uses_mapping_or_matrix_pairwise_distances() -> None:
    similarities = [0.9, 0.7, 0.2]

    assert score_unexpected_connection(similarities, {(0, 1): 0.1}) == pytest.approx(0.63)
    assert score_unexpected_connection(
        similarities,
        [
            [1.0, 0.1, 0.5],
            [0.1, 1.0, 0.2],
            [0.5, 0.2, 1.0],
        ],
    ) == pytest.approx(0.63)


@pytest.mark.parametrize(
    ("similarity", "expected"),
    [(-0.5, 0.0), (0.4, 0.4), (1.5, 1.0)],
)
def test_score_structural_insight_passes_through_clamped_similarity(
    similarity: float, expected: float
) -> None:
    assert score_structural_insight(similarity) == expected


def test_score_link_density_counts_above_threshold_and_normalizes() -> None:
    assert score_link_density([0.1, 0.41, 0.8], threshold=0.4) == pytest.approx(2 / 3)
    assert score_link_density(
        [0.1, 0.41, 0.8], threshold=0.4, similarity_candidates=5
    ) == pytest.approx(0.4)


def test_score_link_density_handles_empty_or_zero_candidate_lists() -> None:
    assert score_link_density([], threshold=0.4) == 0.0
    assert score_link_density([0.8], threshold=0.4, similarity_candidates=0) == 0.0


@pytest.mark.parametrize(
    ("similarities", "expected"),
    [([], 1.0), ([1.0], 0.0), ([0.2, 0.6], 0.4), ([1.5], 0.0), ([-0.2], 1.0)],
)
def test_score_cluster_novelty_is_one_minus_max_centroid_similarity(
    similarities: list[float], expected: float
) -> None:
    assert score_cluster_novelty(similarities) == pytest.approx(expected)


def test_score_unresolvedness_affinity_sums_clamped_weighted_pairs() -> None:
    assert score_unresolvedness_affinity([0.5, 0.25], [0.4, 0.8]) == pytest.approx(0.4)
    assert score_unresolvedness_affinity([1.0, 1.0], [0.8, 0.8]) == 1.0
    assert score_unresolvedness_affinity([0.9], []) == 0.0


def test_compute_phase2_composite_uses_non_uniform_weights() -> None:
    config = ScoringConfig(
        liminality_weight=2.0,
        friction_weight=1.0,
        unexpected_connection_weight=0.0,
        structural_insight_weight=0.0,
        link_density_weight=0.0,
        cluster_novelty_weight=0.0,
        unresolvedness_affinity_weight=0.0,
    )

    assert compute_phase2_composite(
        {"liminality": 0.2, "friction": 0.8, "unexpected_connection": 1.0},
        config,
    ) == pytest.approx(0.4)


def test_compute_phase2_composite_ignores_missing_scores_and_zero_total_weight() -> None:
    assert compute_phase2_composite({}, ScoringConfig()) == 0.0
    assert compute_phase2_composite(
        {"liminality": 1.0},
        ScoringConfig(liminality_weight=0.0),
    ) == 0.0
