"""Check how many corpus items have no timestamp."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path
from phosphene.source_ingestion import SourceIngestion

# Use run.py's config builder
exec(open("run.py").read().split("def main")[0])  # load imports and defaults

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

vault_path = Path("vault")
Path("vault/.source_markers.json").unlink(missing_ok=True)

ingestion_config = _make_ingestion_config(env, vault_path)
source_ingestion = SourceIngestion(ingestion_config)
results = source_ingestion.poll()

items = []
for r in results:
    items.extend(r.items)

has_ts = sum(1 for i in items if i.timestamp is not None)
no_ts = sum(1 for i in items if i.timestamp is None)
print(f"Total items: {len(items)}")
print(f"With timestamp: {has_ts}")
print(f"Without timestamp: {no_ts}")

# Check for items sharing exact same timestamp
from collections import Counter
ts_counter = Counter(str(i.timestamp) for i in items if i.timestamp)
collisions = {ts: c for ts, c in ts_counter.items() if c > 1}
print(f"\nTimestamp collisions (same second): {len(collisions)} groups, {sum(c for c in collisions.values())} items")
if collisions:
    for ts, c in sorted(collisions.items(), key=lambda x: -x[1])[:5]:
        print(f"  {ts}: {c} items")
