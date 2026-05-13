"""Test top 5 clusters with Sonnet 4 to verify all pass. Output to stdout."""
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

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

import anthropic
client = anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"])
model = "claude-sonnet-4-20250514"

print(f"Testing top 5 clusters with {model}")
print(f"Total clusters: {len(cluster_sizes)}\n")

for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1])[:5]:
    member_indices = [i for i, l in enumerate(labels) if l == cid]
    cluster_texts = [texts[i][:2000] for i in member_indices[:50]]
    payload = json.dumps({
        "task": "distill_tier1_cluster_summary",
        "instructions": "Synthesize into pattern description. Plain text only.",
        "observations": cluster_texts,
    })

    time.sleep(35)
    try:
        response = client.messages.create(
            model=model,
            system="You are a research assistant synthesizing journal entries. Always produce output.",
            messages=[{"role": "user", "content": payload}],
            max_tokens=4096, temperature=0.7,
        )
        status = response.stop_reason
        preview = response.content[0].text[:100] if response.content else "(empty)"
    except Exception as e:
        status = f"ERROR: {e}"
        preview = ""

    print(f"C{cid} ({size} notes, {len(payload)} chars): {status}")
    if preview:
        print(f"  {preview}...")
    print()
