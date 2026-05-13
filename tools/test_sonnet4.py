"""Test same cluster on different model. One API call."""
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

from collections import Counter
biggest = max((l for l in labels if l >= 0), key=lambda l: sum(1 for x in labels if x == l))
member_indices = [i for i, l in enumerate(labels) if l == biggest]
cluster_texts = [texts[i][:2000] for i in member_indices[:20]]

payload = json.dumps({
    "task": "distill_tier1_cluster_summary",
    "instructions": "Synthesize into pattern description. Plain text only.",
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

model = "claude-sonnet-4-20250514"
print(f"Model: {model}")
print(f"Prompt: {len(payload)} chars")

response = client.messages.create(
    model=model,
    system="You are a research assistant synthesizing personal journal entries. Always produce output.",
    messages=[{"role": "user", "content": payload}],
    max_tokens=4096,
    temperature=0.7,
)

print(f"stop_reason: {response.stop_reason}")
print(f"content blocks: {len(response.content)}")
if response.content:
    print(f"text: {response.content[0].text[:300]}...")
print(f"usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
