from pathlib import Path

import numpy as np

from phosphene.memory_store import MemoryStore, MemoryStoreConfig, NoteInput
from phosphene.memory_store.vault import parse_note
from tools.rebuild_t2_crosslinks import rebuild_t2_crosslinks


def make_store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "vault" / ".embeddings"),
        )
    )


def test_rebuild_t2_crosslinks_dry_run_preserves_files(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    source_id = store.store_note(NoteInput(tier=1, content="source", title="source"))
    alpha_id = store.store_note(
        NoteInput(
            tier=2,
            content="alpha",
            title="alpha",
            links=[source_id],
            embedding=np.array([1.0, 0.0]),
            cluster_group="alpha",
        )
    )
    beta_id = store.store_note(
        NoteInput(
            tier=2,
            content="beta",
            title="beta",
            links=[alpha_id],
            embedding=np.array([0.99, 0.1]),
            cluster_group="beta",
        )
    )
    gamma_id = store.store_note(
        NoteInput(
            tier=2,
            content="gamma",
            title="gamma",
            links=[alpha_id],
            embedding=np.array([0.0, 1.0]),
            cluster_group="gamma",
        )
    )
    before = (tmp_path / "vault" / "tier2" / f"{beta_id}.md").read_text()

    report = rebuild_t2_crosslinks(
        vault_path=tmp_path / "vault",
        threshold=0.95,
        max_links=15,
        dry_run=True,
    )

    assert report.tier2_count == 3
    assert report.rewritten_count == 2
    assert report.stripped_t2_link_count == 2
    assert report.preserved_non_t2_link_count == 1
    assert report.added_t2_link_count == 2
    assert report.t2_link_distribution == {0: 1, 1: 2}
    assert (tmp_path / "vault" / "tier2" / f"{beta_id}.md").read_text() == before
    assert gamma_id != alpha_id


def test_rebuild_t2_crosslinks_write_strips_t2_links_and_adds_similar_peers(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    source_id = store.store_note(NoteInput(tier=1, content="source", title="source"))
    alpha_id = store.store_note(
        NoteInput(
            tier=2,
            content="alpha",
            title="alpha",
            links=[source_id],
            embedding=np.array([1.0, 0.0]),
            cluster_group="alpha",
        )
    )
    beta_id = store.store_note(
        NoteInput(
            tier=2,
            content="beta",
            title="beta",
            links=[alpha_id],
            embedding=np.array([0.99, 0.1]),
            cluster_group="beta",
        )
    )
    gamma_id = store.store_note(
        NoteInput(
            tier=2,
            content="gamma",
            title="gamma",
            links=[alpha_id, source_id],
            embedding=np.array([0.0, 1.0]),
            cluster_group="gamma",
        )
    )

    report = rebuild_t2_crosslinks(
        vault_path=tmp_path / "vault",
        threshold=0.95,
        max_links=15,
        dry_run=False,
    )

    assert report.dry_run is False
    reloaded = MemoryStore(
        MemoryStoreConfig(
            vault_path=str(tmp_path / "vault"),
            embedding_path=str(tmp_path / "vault" / ".embeddings"),
        )
    )
    alpha = reloaded.get_note(alpha_id)
    beta = reloaded.get_note(beta_id)
    gamma = reloaded.get_note(gamma_id)
    assert alpha is not None
    assert beta is not None
    assert gamma is not None
    assert alpha.links == [source_id, beta_id]
    assert beta.links == [alpha_id]
    assert gamma.links == [source_id]
    assert alpha.link_count == 3
    assert beta.link_count == 2
    assert gamma.link_count == 1
    alpha_file = parse_note(
        (tmp_path / "vault" / "tier2" / f"{alpha_id}.md").read_text()
    )
    assert alpha_file.link_count == 2
