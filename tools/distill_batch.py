"""Distill the first N T1 notes by timestamp. No seeding — uses existing vault.

Usage:
    ~/phosphene-venv/bin/python3 tools/distill_batch.py 200
    ~/phosphene-venv/bin/python3 tools/distill_batch.py 400
"""
import sys, os, json, time
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src",
          "c:/Users/myeluashvili/claude-code-workspace/projects/toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path
from datetime import datetime, timedelta, timezone

# Load env
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 200
print(f"Distilling first {batch_size} T1 notes by timestamp...")

# Load vault
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteQuery

vault_path = Path(env.get("PHOSPHENE_VAULT_PATH", "vault"))
ms = MemoryStore(MemoryStoreConfig(
    vault_path=str(vault_path),
    embedding_path=str(vault_path / ".embeddings"),
))

# Query all T1, sort by timestamp, take first N
notes = ms.query_notes(NoteQuery(tier=1, limit=10000))
print(f"  Total T1 notes: {len(notes)}")

def sort_key(n):
    ts = getattr(n, "created_at", None)
    if ts and hasattr(ts, "year") and ts.year < 2026:
        return (0, ts)
    return (1, datetime.min.replace(tzinfo=timezone.utc))

notes = sorted(notes, key=sort_key)[:batch_size]
print(f"  Using first {len(notes)} by timestamp")
if notes:
    first_ts = getattr(notes[0], "created_at", "?")
    last_ts = getattr(notes[-1], "created_at", "?")
    print(f"  Range: {first_ts} → {last_ts}")

# Set up distillation
from phosphene.distillation import DistillationEngine, DistillationConfig
from toolkit.llm_client import LLMConfig
from toolkit.embedding import EmbeddingConfig

model = env.get("PHOSPHENE_ANTHROPIC_MODEL", "claude-sonnet-4-6")
llm_config = LLMConfig(
    provider="anthropic",
    api_key=env["ANTHROPIC_API_KEY"],
    models={"default": model, "quality": model, "commodity": model},
)
embedding_config = EmbeddingConfig(
    model=env.get("PHOSPHENE_EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
)
distill_config = DistillationConfig(
    llm_config=llm_config,
    embedding_config=embedding_config,
    min_time_between_runs=timedelta(seconds=0),
)

engine = DistillationEngine(ms)
print(f"\nModel: {model}")

# Check gates
gates = engine.check_gates(distill_config)
print(f"Gates: t1_to_t2_ready={gates.t1_to_t2_ready}")

if not gates.t1_to_t2_ready:
    print("Gates not met. Need more T1 notes.")
    sys.exit(0)

print(f"\nRunning T1→T2 distillation...")
try:
    result = engine.distill_t1_to_t2(distill_config)
    print(f"\nSUCCESS:")
    print(f"  New clusters: {len(result.new_cluster_ids)}")
    print(f"  Promoted: {result.promoted_count}")
    print(f"  Noise: {result.noise_count}")
    print(f"  Tree depth: {result.cluster_tree_depth}")
    
    # Check T2 notes
    t2_count = len(list(vault_path.glob("tier2/*.md")))
    print(f"  T2 notes in vault: {t2_count}")
except Exception as e:
    print(f"\nFAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
