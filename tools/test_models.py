"""Test the failing cluster with different models."""
import sys, os, json
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

import numpy as np
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteQuery

ms = MemoryStore(MemoryStoreConfig(vault_path="vault", embedding_path="vault/.embeddings"))
notes = ms.query_notes(NoteQuery(tier=1, limit=200))

embeddings = [n.embedding for n in notes if n.embedding is not None]
texts = [n.content for n in notes if n.embedding is not None]
emb = np.array(embeddings)

import umap, hdbscan
reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)

# Get the largest cluster
from collections import Counter
cluster_sizes = Counter(l for l in labels if l >= 0)
biggest_cid = max(cluster_sizes, key=cluster_sizes.get)
member_indices = [i for i, l in enumerate(labels) if l == biggest_cid]
cluster_texts = [texts[i][:2000] for i in member_indices[:50]]

payload = json.dumps({
    "task": "distill_tier1_cluster_summary",
    "instructions": "Synthesize these observations into one coherent pattern description. Return plain text.",
    "observations": cluster_texts,
}, sort_keys=True)

system_prompt = (
    "You are a research assistant synthesizing personal journal entries. "
    "The content may be multilingual. Always produce a synthesis."
)

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

from toolkit.llm_client import AnthropicProvider
provider = AnthropicProvider(api_key=env["ANTHROPIC_API_KEY"])

models = [
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-20250514",
    "claude-haiku-3-5-20241022",
]

import time
for model in models:
    print(f"\nModel: {model}")
    time.sleep(30)  # rate limit
    try:
        response = provider.call(
            model=model, system_prompt=system_prompt,
            user_prompt=payload, max_tokens=4096, temperature=0.7,
        )
        print(f"  OK: {response.text[:200]}...")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")
