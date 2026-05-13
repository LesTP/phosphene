"""Compute prompt sizes for all clusters - NO API CALLS, just math."""
import sys, os, json
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
notes = ms.query_notes(NoteQuery(tier=1, limit=300))
embeddings = [n.embedding for n in notes if n.embedding is not None]
texts = [n.content for n in notes if n.embedding is not None]
emb = np.array(embeddings)
print(f"Notes: {len(emb)}")

import umap, hdbscan
reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)
cluster_sizes = Counter(l for l in labels if l >= 0)
print(f"Clusters: {len(cluster_sizes)}")

# For each cluster, compute what the prompt would look like at different caps
configs = [
    ("50obs x 2000chars (original)", 50, 2000),
    ("20obs x 1000chars (current)", 20, 1000),
    ("10obs x 500chars (conservative)", 10, 500),
]

for label, max_obs, max_chars in configs:
    print(f"\n--- {label} ---")
    prompt_sizes = []
    for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1]):
        member_indices = [i for i, l in enumerate(labels) if l == cid]
        cluster_texts = [texts[i] for i in member_indices]
        obs = [t[:max_chars] for t in cluster_texts[:max_obs]]
        payload = json.dumps({
            "task": "distill_tier1_cluster_summary",
            "instructions": "Synthesize into pattern description.",
            "observations": obs,
        })
        prompt_sizes.append((cid, size, len(payload), len(payload)//4))

    sizes_chars = [s[2] for s in prompt_sizes]
    sizes_tokens = [s[3] for s in prompt_sizes]
    print(f"  Prompt sizes (chars): min={min(sizes_chars)}, max={max(sizes_chars)}, mean={sum(sizes_chars)//len(sizes_chars)}")
    print(f"  Prompt sizes (tokens est): min={min(sizes_tokens)}, max={max(sizes_tokens)}, mean={sum(sizes_tokens)//len(sizes_tokens)}")
    print(f"  Over 10K chars: {sum(1 for s in sizes_chars if s > 10000)}/{len(sizes_chars)}")
    print(f"  Over 20K chars: {sum(1 for s in sizes_chars if s > 20000)}/{len(sizes_chars)}")
    
    # Show the biggest prompts
    prompt_sizes.sort(key=lambda x: -x[2])
    print(f"  Top 5 largest:")
    for cid, csize, chars, toks in prompt_sizes[:5]:
        print(f"    C{cid} ({csize} notes): {chars} chars ~{toks} tokens")
