"""Deduplicate T1 vault notes by content hash. Keeps the oldest copy."""
import sys, os, hashlib
from pathlib import Path

vault = Path("/mnt/passport/shared/phosphene/vault/tier1")
if not vault.exists():
    print("No tier1 directory")
    sys.exit(1)

files = sorted(vault.glob("*.md"))
print(f"Total T1 files: {len(files)}")

# Hash content body (skip frontmatter)
seen = {}  # content_hash -> filepath
duplicates = []

for f in files:
    content = f.read_text(encoding="utf-8")
    parts = content.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
    else:
        body = content.strip()
    
    h = hashlib.md5(body.encode()).hexdigest()
    if h in seen:
        duplicates.append(f)
    else:
        seen[h] = f

print(f"Unique: {len(seen)}")
print(f"Duplicates: {len(duplicates)}")

if duplicates:
    print(f"\nDeleting {len(duplicates)} duplicates...")
    deleted = 0
    for f in duplicates:
        try:
            f.unlink()
            deleted += 1
        except OSError as e:
            print(f"  Failed to delete {f.name}: {e}")
    print(f"Deleted: {deleted}")
    print(f"Remaining: {len(files) - deleted}")
