from dataclasses import fields
from datetime import datetime

import numpy as np

import phosphene.attention_filter as attention_filter
from phosphene.attention_filter import (
    AnnotatedFragment,
    AttentionFilter,
    AttentionFilterConfig,
    AttentionFilterError,
    ContentItem,
    FilterCriterion,
    FilterResult,
    InvalidScoreError,
    ScoringConfig,
)
from phosphene.memory_store import DensityMetrics


def test_package_exports_arch_public_api() -> None:
    expected_exports = {
        "AnnotatedFragment",
        "AttentionFilter",
        "AttentionFilterConfig",
        "AttentionFilterError",
        "ContentItem",
        "FilterCriterion",
        "FilterResult",
        "InvalidScoreError",
        "ScoringConfig",
        "compute_phase2_composite",
        "compute_blend_weights",
        "default_prompt_criteria",
        "phase2_is_active",
        "score_cluster_novelty",
        "score_friction",
        "score_liminality",
        "score_link_density",
        "score_structural_insight",
        "score_unexpected_connection",
        "score_unresolvedness_affinity",
    }

    assert set(attention_filter.__all__) == expected_exports
    for exported_name in expected_exports:
        assert getattr(attention_filter, exported_name) is not None


def test_arch_dataclass_field_names_match_contract() -> None:
    assert [field.name for field in fields(ContentItem)] == [
        "content",
        "source",
        "timestamp",
        "url",
        "linked_urls",
    ]
    assert [field.name for field in fields(FilterCriterion)] == [
        "name",
        "description",
        "weight",
    ]
    assert [field.name for field in fields(ScoringConfig)] == [
        "precision_surplus_weight",
        "liminality_weight",
        "friction_weight",
        "unexpected_connection_weight",
        "structural_insight_weight",
        "link_density_weight",
        "cluster_novelty_weight",
        "unresolvedness_affinity_weight",
        "link_density_sim_threshold",
        "gap_factor_exponent",
        "assertion_alignment_threshold",
        "note_count_threshold",
        "cluster_count_threshold",
        "phase2_max_weight",
    ]
    assert [field.name for field in fields(AttentionFilterConfig)] == [
        "prompt_criteria",
        "llm_config",
        "embedding_config",
        "scoring",
        "acceptance_threshold",
        "auto_accept_sources",
        "density_crossover",
        "similarity_candidates",
        "llm_tier",
        "assertion_extraction_tier",
    ]
    assert [field.name for field in fields(AnnotatedFragment)] == [
        "content",
        "annotation",
        "importance_score",
        "unresolvedness",
        "retention_criteria",
        "prompt_score",
        "structure_score",
        "friction_target",
        "connections",
        "source",
        "timestamp",
        "url",
        "linked_urls",
        "embedding",
    ]
    assert [field.name for field in fields(FilterResult)] == [
        "accepted",
        "rejected_count",
        "total_count",
        "prompt_weight",
        "structure_weight",
        "density_snapshot",
    ]


def test_arch_dataclasses_construct_with_expected_defaults() -> None:
    timestamp = datetime(2026, 1, 1)
    item = ContentItem(content="text", source="rss", timestamp=timestamp)
    criterion = FilterCriterion(name="precision_surplus", description="desc")
    fragment = AnnotatedFragment(
        content="text",
        annotation="why retained",
        importance_score=0.8,
        unresolvedness=0.2,
        retention_criteria=["precision_surplus"],
        prompt_score=0.8,
        structure_score=0.0,
        friction_target=None,
        connections=["note-1"],
        source="rss",
        timestamp=timestamp,
        url=None,
        linked_urls=[],
        embedding=np.array([0.1, 0.2]),
    )
    result = FilterResult(
        accepted=[fragment],
        rejected_count=0,
        total_count=1,
        prompt_weight=1.0,
        structure_weight=0.0,
        density_snapshot=DensityMetrics(
            note_count=0,
            tier_counts={1: 0, 2: 0, 3: 0},
            mean_link_degree=0.0,
            cluster_count=0,
            unresolved_count=0,
            max_unresolvedness=0.0,
        ),
    )

    assert item.url is None
    assert item.linked_urls == []
    assert criterion.weight == 1.0
    assert result.accepted == [fragment]
    assert isinstance(AttentionFilter(memory_store=object()), AttentionFilter)
    assert issubclass(InvalidScoreError, AttentionFilterError)
