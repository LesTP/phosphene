"""Check note ID collisions by generating IDs in the same order as seed-direct."""
import sys, os, re
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path
from phosphene.memory_store.vault import generate_note_id
from collections import Counter
from datetime import datetime, timezone

# Replicate what seed-direct does: poll adapters, filter, clean, generate IDs
from toolkit.source_ingestion import SourceIngestion, IngestionConfig, AdapterConfig

vault_path = Path("vault")
params_common = {"marker_path": str(vault_path / ".source_markers_check.json")}

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

# Build same adapters as run.py
adapters = [
    AdapterConfig("corpus_livejournal", "corpus_livejournal", {
        "marker_path": params_common["marker_path"],
        "archive_path": env.get("PHOSPHENE_LJ_ARCHIVE_PATH", "seed/LJ Backup/ljsm/lestp"),
        "username": "lestp",
    }),
    AdapterConfig("corpus_blogspot", "corpus_blogspot_brassmonkeyonmyback", {
        "marker_path": params_common["marker_path"],
        "archive_path": "seed/brassmonkeyonmyback_feed.atom",
    }),
    AdapterConfig("corpus_blogspot", "corpus_blogspot_whatsinmyipod", {
        "marker_path": params_common["marker_path"],
        "archive_path": "seed/whatsinmyipod_feed.atom",
    }),
    AdapterConfig("corpus_text", "corpus_text", {
        "marker_path": params_common["marker_path"],
        "archive_path": "seed",
    }),
    AdapterConfig("corpus_facebook", "corpus_facebook", {
        "marker_path": params_common["marker_path"],
        "archive_path": "seed/your_posts__check_ins__photos_and_videos_1.html",
    }),
]

ingestion = SourceIngestion(IngestionConfig(adapters=adapters))
results = ingestion.poll()
items = []
for r in results:
    items.extend(r.items)

# Filter
MIN_WORDS = 10
items = [i for i in items if len(i.content.split()) >= MIN_WORDS]
print(f"Total items after filter: {len(items)}")

# Count timestamps
has_ts = sum(1 for i in items if i.timestamp)
no_ts = len(items) - has_ts
print(f"With timestamp: {has_ts}")
print(f"Without timestamp: {no_ts}")

# Generate IDs same as seed-direct does
ids = []
for item in items:
    title = item.title or item.content[:60].replace("\n", " ")
    ts = item.timestamp or datetime.now(timezone.utc)
    nid = generate_note_id(title, ts)
    ids.append(nid)

id_counter = Counter(ids)
unique = sum(1 for c in id_counter.values() if c == 1)
collisions = {nid: c for nid, c in id_counter.items() if c > 1}
total_lost = sum(c - 1 for c in collisions.values())

print(f"\nUnique IDs: {len(id_counter)}")
print(f"Colliding IDs: {len(collisions)} groups")
print(f"Total notes lost to collision: {total_lost}")
print(f"Expected vault count: {len(id_counter)}")

if collisions:
    print(f"\nTop collisions:")
    for nid, c in sorted(collisions.items(), key=lambda x: -x[1])[:10]:
        print(f"  {nid}: {c}x")

# Clean up temp marker
Path("vault/.source_markers_check.json").unlink(missing_ok=True)
