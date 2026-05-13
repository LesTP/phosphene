"""Check note ID collisions: generate IDs for all items and find duplicates."""
import sys, os, re, hashlib
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from phosphene.memory_store.vault import generate_note_id
from phosphene.source_ingestion import SourceIngestion, IngestionConfig, AdapterConfig

# Minimal env
env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

# Build adapters same as run.py
from pathlib import Path
vault_path = Path("vault")
params_common = {"marker_path": str(vault_path / ".source_markers.json")}
adapters = [
    AdapterConfig("corpus_livejournal", "corpus_livejournal", {**params_common, "archive_path": "seed/LJ Backup/ljsm/lestp", "username": "lestp"}),
    AdapterConfig("corpus_blogspot", "corpus_blogspot_brassmonkeyonmyback", {**params_common, "archive_path": "seed/brassmonkeyonmyback_feed.atom"}),
    AdapterConfig("corpus_blogspot", "corpus_blogspot_whatsinmyipod", {**params_common, "archive_path": "seed/whatsinmyipod_feed.atom"}),
    AdapterConfig("corpus_text", "corpus_text", {**params_common, "archive_path": "seed"}),
    AdapterConfig("corpus_facebook", "corpus_facebook", {**params_common, "archive_path": "seed/your_posts__check_ins__photos_and_videos_1.html"}),
]
ingestion = SourceIngestion(IngestionConfig(adapters=adapters))

# Delete markers to get all items
Path("vault/.source_markers.json").unlink(missing_ok=True)
results = ingestion.poll()
items = []
for r in results:
    items.extend(r.items)

# Filter same as run.py
MIN_WORDS = 10
items = [i for i in items if len(i.content.split()) >= MIN_WORDS]
print(f"Total items: {len(items)}")

# Generate IDs and check collisions
from collections import Counter
ids = []
for item in items:
    title = item.title or item.content[:60].replace("\n", " ")
    ts = item.timestamp
    from datetime import datetime, timezone
    if ts is None:
        ts = datetime.now(timezone.utc)
    note_id = generate_note_id(title, ts)
    ids.append((note_id, title[:50], ts))

id_counter = Counter(nid for nid, _, _ in ids)
collisions = {nid: count for nid, count in id_counter.items() if count > 1}

print(f"Unique IDs: {len(id_counter)}")
print(f"Colliding IDs: {len(collisions)} (affecting {sum(c for c in collisions.values())} items)")

if collisions:
    print(f"\nTop 10 collisions:")
    for nid, count in sorted(collisions.items(), key=lambda x: -x[1])[:10]:
        examples = [(t, ts) for i, t, ts in ids if i == nid][:3]
        print(f"  {nid}: {count}x")
        for t, ts in examples:
            print(f"    title={t!r}, ts={ts}")
