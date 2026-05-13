"""Inspect the RAW Anthropic response on a medium prompt. One API call."""
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
biggest = max((l for l in labels if l >= 0), key=lambda l: sum(1 for x in labels if x == l))
member_indices = [i for i, l in enumerate(labels) if l == biggest]
cluster_texts = [texts[i][:2000] for i in member_indices[:20]]

payload = json.dumps({
    "task": "distill_tier1_cluster_summary",
    "instructions": "Synthesize into pattern description. Plain text only.",
    "observations": cluster_texts,
})
print(f"Prompt size: {len(payload)} chars, ~{len(payload)//4} tokens est")

# Load env
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

# Call API directly (not through toolkit) to see raw response
import anthropic
client = anthropic.Anthropic(api_key=env["ANTHROPIC_API_KEY"])
model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

print(f"Model: {model}")
print(f"Calling API...")

response = client.messages.create(
    model=model,
    system="You are a research assistant. Always produce output.",
    messages=[{"role": "user", "content": payload}],
    max_tokens=4096,
    temperature=0.7,
)

print(f"\n=== RAW RESPONSE ===")
print(f"stop_reason: {response.stop_reason}")
print(f"content blocks: {len(response.content)}")
for i, block in enumerate(response.content):
    print(f"  block[{i}]: type={block.type}, text={repr(block.text[:200]) if hasattr(block, 'text') else 'no text'}")
print(f"usage: input={response.usage.input_tokens}, output={response.usage.output_tokens}")
print(f"model: {response.model}")
