from phosphene.attention_filter import AttentionFilter, AttentionFilterConfig, ScoringConfig
from phosphene.memory_store import DensityMetrics


class FakeMemoryStore:
    def __init__(self, metrics: DensityMetrics) -> None:
        self.metrics = metrics
        self.density_calls = 0

    def get_density_metrics(self) -> DensityMetrics:
        self.density_calls += 1
        return self.metrics


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
    mean_link_degree: float = 3.75,
) -> DensityMetrics:
    return DensityMetrics(
        note_count=note_count,
        tier_counts={1: note_count, 2: 0, 3: 0},
        mean_link_degree=mean_link_degree,
        cluster_count=cluster_count,
        unresolved_count=2,
        max_unresolvedness=0.8,
    )


def test_filter_content_empty_batch_returns_density_snapshot_and_blend_weights() -> None:
    density = metrics()
    store = FakeMemoryStore(density)
    config = make_config(scoring=ScoringConfig(phase2_max_weight=0.8))

    result = AttentionFilter(store).filter_content([], config)

    assert store.density_calls == 1
    assert result.accepted == []
    assert result.rejected_count == 0
    assert result.total_count == 0
    assert result.prompt_weight == 0.6
    assert result.structure_weight == 0.4
    assert result.density_snapshot is density
