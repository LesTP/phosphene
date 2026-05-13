"""Seed 200 items from real corpus with per-note logging. Find missing notes."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path
from phosphene.memory_store import MemoryStore, MemoryStoreConfig
from phosphene.memory_store.types import NoteInput
from phosphene.memory_store.vault import generate_note_id, note_path
from toolkit.embedding import embed, EmbeddingConfig
from datetime import datetime, timezone
import numpy as np

# Use separate vault to avoid interference
vault_path = Path("vault_test200")
for d in ["tier1", "tier2", "tier3"]:
    (vault_path / d).mkdir(parents=True, exist_ok=True)

ms = MemoryStore(MemoryStoreConfig(
    vault_path=str(vault_path),
    embedding_path=str(vault_path / ".embeddings"),
))

# Load env
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

# Use run.py's _make_ingestion_config to get the real adapter setup
# Import run.py's config builder by running its module init
sys.path.insert(0, ".")
import run as run_module
ingestion_config = run_module._make_ingestion_config(env, vault_path)

from phosphene.source_ingestion import SourceIngestion
# Delete markers
(vault_path / ".source_markers.json").unlink(missing_ok=True)
si = SourceIngestion(ingestion_config)
results = si.poll()
items = []
for r in results:
    items.extend(r.items)

# Filter and clean (same as seed-direct)
MIN_WORDS = 10
items = [i for i in items if len(i.content.split()) >= MIN_WORDS]
items = items[:200]
print(f"Items to seed: {len(items)}")

# Embed
texts = [i.content for i in items]
emb_result = embed(texts, EmbeddingConfig(model="paraphrase-multilingual-MiniLM-L12-v2"))

# Store with logging
stored = 0
written = 0
missing = []
seen_ids = {}

for i, item in enumerate(items):
    title = item.title or item.content[:60].replace("\n", " ")
    ts = item.timestamp
    note_id = generate_note_id(title, ts or datetime.now(timezone.utc))
    
    # Check for collision
    if note_id in seen_ids:
        prev = seen_ids[note_id]
        print(f"[{i+1}] COLLISION: {note_id}")
        print(f"  prev: title={prev[0][:40]!r} ts={prev[1]}")
        print(f"  this: title={title[:40]!r} ts={ts}")
    seen_ids[note_id] = (title, ts)
    
    note = NoteInput(
        tier=1, content=item.content, title=title,
        importance=0.5, source=item.source,
        embedding=emb_result.vectors[i], tags=[],
        created_at=ts,
    )
    
    try:
        returned_id = ms.store_note(note)
        stored += 1
        fpath = note_path(vault_path, 1, returned_id)
        if fpath.exists():
            written += 1
        else:
            missing.append((i, returned_id, title[:40], ts))
            print(f"[{i+1}] MISSING: {returned_id} title={title[:40]!r}")
    except Exception as e:
        print(f"[{i+1}] ERROR: {type(e).__name__}: {e}")

total_files = len(list((vault_path / "tier1").glob("*.md")))
print(f"\nStored: {stored}")
print(f"Written to disk: {written}")
print(f"Missing after write: {len(missing)}")
print(f"Files on disk: {total_files}")
print(f"Collisions: {sum(1 for nid, v in seen_ids.items() if list(seen_ids.values()).count(v) > 1)}")

if total_files != stored:
    print(f"\nDISCREPANCY: {stored} stored but {total_files} files")
