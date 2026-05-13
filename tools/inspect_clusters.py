"""Inspect cluster distribution on the seeded vault."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import numpy as np
from collections import Counter
from phosphene.memory_store import MemoryStore, MemoryStoreConfig

ms = MemoryStore(MemoryStoreConfig(
    vault_path="vault",
    embedding_path="vault/.embeddings",
))

# Load all T1 notes with embeddings
from phosphene.memory_store.types import NoteQuery
notes = ms.query_notes(NoteQuery(tier=1, limit=10000))
print(f"Total T1 notes: {len(notes)}")

# Get embeddings
embeddings = []
texts = []
sources = []
for note in notes:
    if note.embedding is not None:
        embeddings.append(note.embedding)
        texts.append(note.content[:100])
        sources.append(note.source or "?")

if not embeddings:
    print("No embeddings found!")
    sys.exit(1)

emb_matrix = np.array(embeddings)
print(f"Notes with embeddings: {emb_matrix.shape[0]}")
print(f"Embedding dim: {emb_matrix.shape[1]}")

# Run HDBSCAN (same as RAPTOR would)
import hdbscan
clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2, metric="euclidean")
labels = clusterer.fit_predict(emb_matrix)

n_clusters = len(set(labels) - {-1})
n_noise = int(np.sum(labels == -1))
cluster_sizes = Counter(labels)
del cluster_sizes[-1]  # remove noise

print(f"\nClusters: {n_clusters}")
print(f"Noise (unclustered): {n_noise} ({n_noise*100//len(labels)}%)")

# Distribution
if cluster_sizes:
    sizes = sorted(cluster_sizes.values(), reverse=True)
    print(f"\nCluster size distribution:")
    print(f"  Largest:  {sizes[0]}")
    print(f"  Smallest: {sizes[-1]}")
    print(f"  Median:   {sizes[len(sizes)//2]}")
    print(f"  Mean:     {sum(sizes)/len(sizes):.1f}")

    print(f"\nTop 10 clusters by size:")
    for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1])[:10]:
        # Sample a few texts from this cluster
        member_indices = [i for i, l in enumerate(labels) if l == cid]
        sample_texts = [texts[i] for i in member_indices[:3]]
        sample_sources = [sources[i] for i in member_indices[:3]]
        src_dist = Counter(sources[i] for i in member_indices)
        top_src = src_dist.most_common(3)
        print(f"\n  Cluster {cid}: {size} notes")
        print(f"    Sources: {', '.join(f'{s}({n})' for s, n in top_src)}")
        for txt in sample_texts:
            print(f"    - {txt.replace(chr(10), ' ')[:120]}...")
