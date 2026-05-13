"""Quick collision test: generate note IDs for sample titles and timestamps."""
import sys, os
sys.path.insert(0, "src")

from phosphene.memory_store.vault import generate_note_id
from datetime import datetime, timezone
from collections import Counter

# Simulate: many notes with same timestamp but different content
ts = datetime(2004, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
titles = [
    "Привет мир",
    "Привет мир!",
    "Привет, мир",
    "note without title",
    "note without title",  # exact dup
    "Тест",
    "Тест",  # exact dup
]
for t in titles:
    nid = generate_note_id(t, ts)
    print(f"  {t!r:40s} → {nid}")

# Now test with real data: read existing vault and check what share timestamps
from pathlib import Path
import re

vault = Path("vault/tier1")
if not vault.exists():
    print("\nNo vault")
    sys.exit(0)

files = list(vault.glob("*.md"))
print(f"\nVault has {len(files)} files")

# Extract created_at from frontmatter
timestamps = []
for f in files:
    content = f.read_text(encoding="utf-8")
    m = re.search(r"created_at:\s*'([^']+)'", content)
    if m:
        timestamps.append(m.group(1))

ts_counter = Counter(timestamps)
colliding_ts = {ts: c for ts, c in ts_counter.items() if c > 1}
print(f"Unique timestamps: {len(ts_counter)}")
print(f"Timestamps with >1 note: {len(colliding_ts)}")

if colliding_ts:
    top = sorted(colliding_ts.items(), key=lambda x: -x[1])[:5]
    print(f"Top 5 shared timestamps:")
    for ts, count in top:
        print(f"  {ts}: {count} notes")
