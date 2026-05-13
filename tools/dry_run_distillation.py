"""Dry-run distillation: cluster T1 notes, report costs, no LLM calls.

Runs on chronological subsets to preview what each batch would produce.
"""
import sys, os, json
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import numpy as np
from collections import Counter
from pathlib import Path
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteQuery

ms = MemoryStore(MemoryStoreConfig(vault_path="vault", embedding_path="vault/.embeddings"))
notes = ms.query_notes(NoteQuery(tier=1, limit=10000))

# Sort by timestamp
from datetime import datetime, timezone
def sort_key(n):
    ts = n.created_at if hasattr(n, "created_at") else None
    if ts and hasattr(ts, "year") and ts.year < 2026:
        return (0, ts)
    return (1, datetime.min.replace(tzinfo=timezone.utc))

notes_with_emb = [(n, n.embedding) for n in notes if n.embedding is not None]
notes_with_emb.sort(key=lambda x: sort_key(x[0]))
print(f"Total T1 notes with embeddings: {len(notes_with_emb)}")

import umap, hdbscan

# Test on cumulative batches: first 200, first 400, first 800, all
batch_sizes = [200, 400, 800, len(notes_with_emb)]
total_clusters = 0
total_est_cost = 0.0

for batch_size in batch_sizes:
    subset = notes_with_emb[:batch_size]
    emb = np.array([e for _, e in subset])
    
    # UMAP + HDBSCAN
    reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
    labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)
    
    cluster_sizes = Counter(l for l in labels if l >= 0)
    n_clusters = len(cluster_sizes)
    n_noise = int(np.sum(labels == -1))
    sizes = sorted(cluster_sizes.values(), reverse=True) if cluster_sizes else []
    
    # Estimate LLM cost: ~$0.01 per cluster summary + ~$0.005 per assertion cache
    est_cost = n_clusters * 0.015
    total_est_cost += est_cost
    
    # Time to process at 30s throttle
    est_minutes = (n_clusters * 30) / 60
    
    print(f"\n{'='*60}")
    print(f"Batch: first {batch_size} notes")
    print(f"  Clusters: {n_clusters}, Noise: {n_noise} ({n_noise*100//len(labels)}%)")
    if sizes:
        print(f"  Sizes: {sizes[:10]}{'...' if len(sizes) > 10 else ''}")
        print(f"  Largest: {sizes[0]}, Median: {sizes[len(sizes)//2]}")
    print(f"  Est. LLM cost: ${est_cost:.2f} ({n_clusters} clusters × $0.015)")
    print(f"  Est. time at 30s throttle: {est_minutes:.0f} min")

print(f"\n{'='*60}")
print(f"TOTAL estimated cost for chronological distillation: ${total_est_cost:.2f}")
print(f"(Sum of all batch rounds — each round clusters everything up to that point)")
