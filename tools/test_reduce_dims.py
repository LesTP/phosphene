"""Compare clustering with and without UMAP reduce_dims."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import numpy as np
from collections import Counter
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteQuery

ms = MemoryStore(MemoryStoreConfig(vault_path="vault", embedding_path="vault/.embeddings"))
notes = ms.query_notes(NoteQuery(tier=1, limit=10000))

embeddings = []
texts = []
for note in notes:
    if note.embedding is not None:
        embeddings.append(note.embedding)
        texts.append(note.content[:80])

emb = np.array(embeddings)
print(f"Notes: {len(emb)}, dim: {emb.shape[1]}\n")

import hdbscan

configs = [
    ("Baseline (no UMAP)", None),
    ("reduce_dims=15", 15),
    ("reduce_dims=10", 10),
    ("reduce_dims=20", 20),
    ("reduce_dims=5", 5),
]

for label, rdims in configs:
    data = emb
    if rdims is not None:
        try:
            import umap
            reducer = umap.UMAP(n_components=rdims, random_state=42)
            data = reducer.fit_transform(data)
        except ImportError:
            print(f"{label}: UMAP not installed, skipping")
            continue

    clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2, metric="euclidean")
    labels = clusterer.fit_predict(data)

    n_clusters = len(set(labels) - {-1})
    n_noise = int(np.sum(labels == -1))
    sizes = sorted(Counter(l for l in labels if l >= 0).values(), reverse=True) if n_clusters else []

    print(f"{label}:")
    print(f"  Clusters: {n_clusters}, Noise: {n_noise} ({n_noise*100//len(labels)}%)")
    if sizes:
        print(f"  Largest: {sizes[0]}, Top 5: {sizes[:5]}")
        print(f"  Median: {sizes[len(sizes)//2]}, Mean: {sum(sizes)/len(sizes):.1f}")
    print()
