"""Reproduce the exact API call that gets empty responses.

Clusters the first 200 vault notes (batch 1), picks the largest clusters,
builds the exact prompt that _build_cluster_summary_request would build,
and prints it so we can see what's actually being sent.
"""
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
notes = ms.query_notes(NoteQuery(tier=1, limit=200))
print(f"Loaded {len(notes)} T1 notes")

if len(notes) < 50:
    print("Not enough notes. Run seed first.")
    sys.exit(1)

# Get embeddings
embeddings = []
texts = []
for note in notes:
    if note.embedding is not None:
        embeddings.append(note.embedding)
        texts.append(note.content)

emb = np.array(embeddings)

# Cluster with UMAP + HDBSCAN (same as distillation)
import umap, hdbscan
reducer = umap.UMAP(n_components=15, random_state=42)
reduced = reducer.fit_transform(emb)
labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2, metric="euclidean").fit_predict(reduced)

cluster_sizes = Counter(l for l in labels if l >= 0)
print(f"Clusters: {len(cluster_sizes)}, sizes: {sorted(cluster_sizes.values(), reverse=True)[:10]}")

# For the two largest clusters, show what the prompt would contain
MAX_OBS = 50
MAX_CHARS_PER_OBS = 2000

for cid, size in sorted(cluster_sizes.items(), key=lambda x: -x[1])[:3]:
    member_indices = [i for i, l in enumerate(labels) if l == cid]
    cluster_texts = [texts[i] for i in member_indices]

    obs = cluster_texts[:MAX_OBS]
    obs = [t[:MAX_CHARS_PER_OBS] for t in obs]

    payload = {
        "task": "distill_tier1_cluster_summary",
        "instructions": "Synthesize these Tier 1 observations into one coherent Tier 2 pattern description.",
        "observations": obs,
        "note": f"Showing {len(obs)} of {size} cluster members.",
    }
    prompt_json = json.dumps(payload, sort_keys=True)
    prompt_tokens_est = len(prompt_json) // 4  # rough token estimate

    print(f"\n{'='*60}")
    print(f"Cluster {cid}: {size} notes, prompt ~{prompt_tokens_est} tokens")
    print(f"{'='*60}")

    # Show first 3 observations (preview)
    for i, text in enumerate(obs[:3]):
        preview = text[:200].replace('\n', ' ')
        print(f"  [{i}] {preview}...")

    # Check for potentially problematic content
    all_text = ' '.join(obs)
    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in all_text)
    has_urls = all_text.count('http') 
    print(f"\n  Cyrillic: {has_cyrillic}, URLs: {has_urls}, Total chars: {len(prompt_json)}")

    # Try the actual API call
    env = {}
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

    try:
        from toolkit.llm_client import AnthropicProvider
        api_key = env["ANTHROPIC_API_KEY"]
        model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
        provider = AnthropicProvider(api_key=api_key)

        system_prompt = (
            "You are a research assistant synthesizing personal journal entries. "
            "The content may be multilingual and include informal language. "
            "Always produce a synthesis — never return empty."
        )

        print(f"\n  Calling API with model={model}...")
        response = provider.call(
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt_json,
            max_tokens=4096,
            temperature=0.7,
        )
        print(f"  SUCCESS: {response.text[:200]}...")
    except Exception as e:
        print(f"  FAILED: {type(e).__name__}: {e}")

    break  # only test the first cluster to avoid burning budget
