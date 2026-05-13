"""Count how many items have no timestamp (these will collide when seeded in same second)."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from phosphene.memory_store.vault import generate_note_id
from collections import Counter
from datetime import datetime, timezone

# Read vault notes and count per-second groups
from pathlib import Path

vault = Path("vault/tier1")
files = sorted(vault.glob("*.md"))
print(f"Files on disk: {len(files)}")

# Extract note_ids from filenames
note_ids = [f.stem for f in files]
id_counter = Counter(note_ids)
dupes = {k: v for k, v in id_counter.items() if v > 1}
print(f"Unique note IDs: {len(id_counter)}")
print(f"Duplicate IDs: {len(dupes)}")

# Count how many notes have no-timestamp (created_at = now)
import re
now_notes = 0
real_notes = 0
for f in files[:200]:
    content = f.read_text(encoding="utf-8")
    m = re.search(r"created_at:\s*'([^']+)'", content)
    if m:
        ts = m.group(1)
        if "2026-05-1" in ts:  # today's date = no original timestamp
            now_notes += 1
        else:
            real_notes += 1
print(f"\nSample of 200: {real_notes} real timestamps, {now_notes} today's date")

# The key question: how many items does run.py report vs how many files exist?
# run.py said "3859 stored" but we see 1469 files
# Expected = 3859, Actual = 1469, Missing = 2390
# If the 2390 missing all have timestamp=None (text notes, FB with broken timestamps)
# they'd all get datetime.now() → same second → same slug + same ts → collision
print(f"\nExpected: 3859, Actual: {len(files)}, Missing: {3859 - len(files)}")
