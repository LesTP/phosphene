"""Test Sonnet 4.6 and Haiku 4.5 on the bilingual cluster."""
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
notes = ms.query_notes(NoteQuery(tier=1, limit=200))
embeddings = [n.embedding for n in notes if n.embedding is not None]
texts = [n.content for n in notes if n.embedding is not None]
emb = np.array(embeddings)

import umap, hdbscan
reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)

# Get the LARGEST cluster (the bilingual one that 4.5 refused)
cluster_sizes = Counter(l for l in labels if l >= 0)
cid = max(cluster_sizes, key=cluster_sizes.get)
member_indices = [i for i, l in enumerate(labels) if l == cid]
cluster_texts = [texts[i][:2000] for i in member_indices[:50]]

payload = json.dumps({
    "task": "distill_tier1_cluster_summary",
    "instructions": "Synthesize into pattern description. Preserve tensions. Plain text only.",
    "observations": cluster_texts,
})

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

import anthropic
client = anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"])
system = "You are a research assistant synthesizing personal journal entries. Always produce a synthesis."

print(f"Cluster {cid}: {len(cluster_texts)} texts, {len(payload)} chars\n")

models = [
    ("claude-sonnet-4-6", "Sonnet 4.6"),
    ("claude-haiku-4-5-20251001", "Haiku 4.5"),
]

for model_id, label in models:
    time.sleep(35)
    try:
        response = client.messages.create(
            model=model_id, system=system,
            messages=[{"role": "user", "content": payload}],
            max_tokens=4096, temperature=0.7,
        )
        print(f"=== {label} ({model_id}) ===")
        print(f"stop_reason: {response.stop_reason}")
        print(f"tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}")
        if response.content:
            print(f"\n{response.content[0].text}\n")
        else:
            print("(empty)\n")
    except Exception as e:
        print(f"=== {label}: FAILED: {type(e).__name__}: {e} ===\n")
