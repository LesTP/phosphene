"""Preflight check: verify all preconditions before spending money.

Run this before any LLM operation (distillation, generation, --once).
Prints GO or NO-GO with specific issues.

Usage:
    ~/phosphene-venv/bin/python3 tools/preflight.py
"""
import sys, os, json, hashlib, time
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src",
          "c:/Users/myeluashvili/claude-code-workspace/projects/toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path
from datetime import datetime, timezone, timedelta

issues = []
warnings = []

# --- Load env ---
env = {}
env_path = Path(".env")
if not env_path.exists():
    issues.append(".env file missing")
else:
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()

# --- Check 1: Vault sanity ---
print("=== VAULT SANITY ===")
vault_path = Path(env.get("PHOSPHENE_VAULT_PATH", "vault"))

# T1 count
t1_dir = vault_path / "tier1"
if not t1_dir.exists():
    issues.append(f"No tier1 directory at {t1_dir}")
    t1_files = []
else:
    t1_files = list(t1_dir.glob("*.md"))
    print(f"  T1 notes: {len(t1_files)}")

# Duplicate check (by content hash)
if t1_files:
    hashes = {}
    dup_count = 0
    for f in t1_files:
        content = f.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        body = parts[2].strip() if len(parts) >= 3 else content.strip()
        h = hashlib.md5(body.encode()).hexdigest()
        if h in hashes:
            dup_count += 1
        else:
            hashes[h] = f
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate T1 notes found. Run tools/dedup_vault.py first.")
    else:
        print(f"  Duplicates: 0 ✓")

# Timestamp check (are timestamps real or all vault-creation-time?)
if t1_files:
    timestamps = set()
    sample = t1_files[:100]
    for f in sample:
        content = f.read_text(encoding="utf-8")
        # Extract created_at from frontmatter
        import re
        m = re.search(r"created_at:\s*'([^']+)'", content)
        if m:
            timestamps.add(m.group(1)[:16])  # group by minute
    unique_minutes = len(timestamps)
    if unique_minutes <= 3:
        warnings.append(f"Only {unique_minutes} unique timestamp minutes in 100 notes. "
                       f"Original publication dates may not be preserved.")
    else:
        print(f"  Timestamp diversity: {unique_minutes} unique minutes in 100-note sample ✓")

# T2/T3 from previous runs
t2_count = len(list((vault_path / "tier2").glob("*.md"))) if (vault_path / "tier2").exists() else 0
t3_count = len(list((vault_path / "tier3").glob("*.md"))) if (vault_path / "tier3").exists() else 0
if t2_count > 0 or t3_count > 0:
    warnings.append(f"Existing T2={t2_count}, T3={t3_count} notes from previous runs. "
                   f"Consider clearing if starting fresh.")
else:
    print(f"  T2/T3: clean (0/0) ✓")

# --- Check 2: API sanity ---
print("\n=== API SANITY ===")
api_key = env.get("ANTHROPIC_API_KEY", "")
model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-6")
if not api_key:
    issues.append("ANTHROPIC_API_KEY not set in .env")
else:
    print(f"  Model: {model}")
    # Trivial test call
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            system="Reply with exactly: OK",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=10,
            temperature=0,
        )
        if response.stop_reason == "end_turn" and response.content:
            print(f"  API test: {response.content[0].text} ✓")
        elif response.stop_reason == "refusal":
            issues.append(f"Model {model} refused trivial prompt (stop_reason=refusal)")
        else:
            warnings.append(f"API returned stop_reason={response.stop_reason}")
    except Exception as e:
        issues.append(f"API test failed: {type(e).__name__}: {e}")

# --- Check 3: Clustering sanity ---
print("\n=== CLUSTERING SANITY ===")
if len(t1_files) >= 50:
    try:
        from phosphene.memory_store import MemoryStore, MemoryStoreConfig
        from phosphene.memory_store.types import NoteQuery
        import numpy as np

        ms = MemoryStore(MemoryStoreConfig(
            vault_path=str(vault_path),
            embedding_path=str(vault_path / ".embeddings"),
        ))
        notes = ms.query_notes(NoteQuery(tier=1, limit=200))
        embeddings = [n.embedding for n in notes if n.embedding is not None]

        if len(embeddings) < 20:
            warnings.append(f"Only {len(embeddings)} notes with embeddings (need 20+)")
        else:
            import umap, hdbscan
            emb = np.array(embeddings)
            reduced = umap.UMAP(n_components=15, random_state=42).fit_transform(emb)
            labels = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=2).fit_predict(reduced)

            from collections import Counter
            cluster_sizes = Counter(l for l in labels if l >= 0)
            n_clusters = len(cluster_sizes)
            n_noise = int(np.sum(labels == -1))
            largest = max(cluster_sizes.values()) if cluster_sizes else 0

            print(f"  Clusters (200-note sample): {n_clusters}")
            print(f"  Noise: {n_noise} ({n_noise*100//len(labels)}%)")
            print(f"  Largest cluster: {largest}")

            if n_clusters == 0:
                issues.append("Zero clusters found. Check embeddings.")
            elif largest > 100:
                warnings.append(f"Largest cluster has {largest} notes. May need UMAP tuning.")
            else:
                print(f"  Clustering: healthy ✓")

            # Cost estimate
            est_cost = n_clusters * 0.015
            est_time = (n_clusters * 45) / 60
            print(f"\n  Estimated cost for 200-note distillation: ${est_cost:.2f}")
            print(f"  Estimated time: {est_time:.0f} min")
    except Exception as e:
        warnings.append(f"Clustering check failed: {type(e).__name__}: {e}")
else:
    warnings.append(f"Only {len(t1_files)} T1 notes. Need 50+ for clustering.")

# --- Check 4: Interface compatibility ---
print("\n=== INTERFACE COMPAT ===")
try:
    from phosphene.distillation.engine import _RaptorClusterConfig, _StrategyStr
    from toolkit.clustering import ClusterStrategy, cluster
    import numpy as np

    strat = _StrategyStr("raptor")
    if strat == ClusterStrategy.RAPTOR:
        print(f"  Strategy enum compat: ✓")
    else:
        issues.append("_StrategyStr != ClusterStrategy.RAPTOR")

    cfg = _RaptorClusterConfig(
        strategy=strat,
        raptor_summarizer=lambda texts: "test",
        raptor_embedder=lambda texts: np.zeros((len(texts), 10)),
    )
    emb_test = np.random.randn(25, 10).astype(np.float32)
    result = cluster(emb_test, cfg, texts=[f"t{i}" for i in range(25)])
    print(f"  Dry-run cluster: {result.n_clusters} clusters ✓")
except Exception as e:
    issues.append(f"Interface compat failed: {type(e).__name__}: {e}")

# --- VERDICT ---
print(f"\n{'='*60}")
if issues:
    print("NO-GO — fix these issues:")
    for i in issues:
        print(f"  ❌ {i}")
if warnings:
    print("WARNINGS (non-blocking):")
    for w in warnings:
        print(f"  ⚠️  {w}")
if not issues:
    print("GO ✓ — all checks passed" + (" (with warnings)" if warnings else ""))
print(f"{'='*60}")
