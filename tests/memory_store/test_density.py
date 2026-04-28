from pathlib import Path

import pytest

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(MemoryStoreConfig(vault_path=str(tmp_path / "vault")))


def store_note(
    store: MemoryStore,
    title: str,
    *,
    tier: int = 1,
    links: list[str] | None = None,
    unresolvedness: float = 0.0,
    cluster_group: str | None = None,
) -> str:
    return store.store_note(
        NoteInput(
            tier=tier,
            content=f"{title} body",
            title=title,
            links=list(links or []),
            unresolvedness=unresolvedness,
            cluster_group=cluster_group,
        )
    )


def test_empty_vault_returns_zero_density_with_all_tier_keys(tmp_path: Path) -> None:
    store = make_store(tmp_path)

    metrics = store.get_density_metrics()

    assert metrics.note_count == 0
    assert metrics.tier_counts == {1: 0, 2: 0, 3: 0}
    assert metrics.mean_link_degree == 0.0
    assert metrics.cluster_count == 0
    assert metrics.unresolved_count == 0
    assert metrics.max_unresolvedness == 0.0


def test_tier_counts_reflect_mixed_tier_vault(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "one", tier=1)
    store_note(store, "two a", tier=2)
    store_note(store, "two b", tier=2)
    store_note(store, "three", tier=3)

    assert store.get_density_metrics().tier_counts == {1: 1, 2: 2, 3: 1}


def test_mean_link_degree_averages_inbound_plus_outbound(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    target_id = store_note(store, "b")
    source_a_id = store_note(store, "a", links=[target_id])
    source_c_id = store_note(store, "c", links=[source_a_id])
    store_note(store, "d")

    metrics = store.get_density_metrics()

    assert metrics.note_count == 4
    assert metrics.mean_link_degree == pytest.approx(1.0)


def test_cluster_count_uses_distinct_tier_two_non_null_groups(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "tier one cluster", tier=1, cluster_group="ignored")
    store_note(store, "tier two alpha", tier=2, cluster_group="alpha")
    store_note(store, "tier two alpha duplicate", tier=2, cluster_group="alpha")
    store_note(store, "tier two beta", tier=2, cluster_group="beta")
    store_note(store, "tier two none", tier=2)
    store_note(store, "tier three cluster", tier=3, cluster_group="ignored")

    assert store.get_density_metrics().cluster_count == 2


def test_unresolved_count_uses_strict_threshold(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "below", unresolvedness=0.49)
    store_note(store, "exact", unresolvedness=0.5)
    store_note(store, "above", unresolvedness=0.51)

    assert store.get_density_metrics().unresolved_count == 1


def test_max_unresolvedness_returns_highest_score_across_tiers(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store_note(store, "tier one", tier=1, unresolvedness=0.2)
    store_note(store, "tier two", tier=2, unresolvedness=0.9)
    store_note(store, "tier three", tier=3, unresolvedness=0.7)

    assert store.get_density_metrics().max_unresolvedness == 0.9


def test_density_metrics_reflect_store_and_add_links_without_rebuild(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store_note(store, "source")
    target_id = store_note(store, "target", tier=2, cluster_group="cluster-a")

    stored_metrics = store.get_density_metrics()
    assert stored_metrics.note_count == 2
    assert stored_metrics.tier_counts == {1: 1, 2: 1, 3: 0}
    assert stored_metrics.cluster_count == 1

    store.add_links(source_id, [target_id])

    linked_metrics = store.get_density_metrics()
    assert linked_metrics.note_count == 2
    assert linked_metrics.mean_link_degree == pytest.approx(1.0)
