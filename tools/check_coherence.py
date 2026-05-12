"""Check coherence scores for all clusters in the 200-note vault."""
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
embeddings = [n.embedding for n in notes if n.embedding is not None]
emb = np.array(embeddings)
print(f"Notes: {len(emb)}")

import umap, hdbscan
reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)

cluster_ids = sorted(set(l for l in labels if l >= 0))
print(f"Clusters: {len(cluster_ids)}")
print(f"Noise: {sum(1 for l in labels if l == -1)}")

# Compute coherence (mean pairwise cosine sim) for each cluster
# Use ORIGINAL embeddings (384-dim), not UMAP-reduced
print(f"\nCoherence scores (mean pairwise cosine sim on 384-dim embeddings):")
print(f"{'Cluster':>8} {'Size':>6} {'Coherence':>10} {'Pass 0.4?':>10} {'Pass 0.3?':>10}")
print("-" * 50)

coherences = []
for cid in cluster_ids:
    indices = [i for i, l in enumerate(labels) if l == cid]
    cluster_embs = emb[indices]
    
    # Mean pairwise cosine similarity
    norms = np.linalg.norm(cluster_embs, axis=1, keepdims=True)
    normed = cluster_embs / (norms + 1e-10)
    sim_matrix = normed @ normed.T
    n = len(indices)
    if n < 2:
        coherence = 1.0
    else:
        # Upper triangle mean
        mask = np.triu(np.ones((n, n), dtype=bool), k=1)
        coherence = float(sim_matrix[mask].mean())
    
    pass_04 = "YES" if coherence >= 0.4 else "no"
    pass_03 = "YES" if coherence >= 0.3 else "no"
    coherences.append((cid, len(indices), coherence))
    print(f"{cid:>8} {len(indices):>6} {coherence:>10.3f} {pass_04:>10} {pass_03:>10}")

print(f"\nSummary:")
print(f"  Pass at 0.4: {sum(1 for _, _, c in coherences if c >= 0.4)} / {len(coherences)}")
print(f"  Pass at 0.3: {sum(1 for _, _, c in coherences if c >= 0.3)} / {len(coherences)}")
print(f"  Pass at 0.2: {sum(1 for _, _, c in coherences if c >= 0.2)} / {len(coherences)}")
print(f"  Min coherence: {min(c for _, _, c in coherences):.3f}")
print(f"  Max coherence: {max(c for _, _, c in coherences):.3f}")
print(f"  Mean coherence: {np.mean([c for _, _, c in coherences]):.3f}")
