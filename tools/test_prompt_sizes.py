"""Test cluster summaries at different prompt sizes to find the threshold."""
import sys, os, json, time
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

import umap, hdbscan
reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)
cluster_sizes = Counter(l for l in labels if l >= 0)

# Load config
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

from toolkit.llm_client import LLMConfig, Message, complete
config = LLMConfig(
    provider="anthropic", api_key=env["ANTHROPIC_API_KEY"],
    models={"default": env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")},
)

system = Message(role="system", content=(
    "You are a research assistant synthesizing personal journal entries. "
    "Always produce a synthesis."
))

# Test different prompt sizes on the top 3 clusters
results = []
for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1])[:3]:
    member_indices = [i for i, l in enumerate(labels) if l == cid]
    cluster_texts = [texts[i] for i in member_indices]

    # Test at different obs counts and char limits
    for max_obs, max_chars in [(5, 500), (10, 500), (10, 1000), (20, 1000), (20, 2000), (30, 2000)]:
        obs = [t[:max_chars] for t in cluster_texts[:max_obs]]
        payload = json.dumps({
            "task": "distill_tier1_cluster_summary",
            "instructions": "Synthesize into one pattern description. Plain text only.",
            "observations": obs,
        }, sort_keys=True)
        
        prompt_chars = len(payload)
        prompt_tokens_est = prompt_chars // 4

        time.sleep(35)  # rate limit
        try:
            response = complete(
                messages=[system, Message(role="user", content=payload)],
                config=config,
            )
            status = f"OK ({len(response.content)} chars)"
        except Exception as e:
            status = f"FAIL: {type(e).__name__}"

        print(f"C{cid}({size}): {max_obs}obs x {max_chars}chars = {prompt_chars}chars ~{prompt_tokens_est}tok -> {status}")
        results.append((cid, max_obs, max_chars, prompt_chars, status))

print("\n--- Summary ---")
for cid, obs, chars, total, status in results:
    print(f"  C{cid}: {obs}x{chars} ({total} chars) -> {status}")
