"""Inspect T2 notes — find placeholders and show what their source clusters contain."""
import sys, os
sys.path.insert(0, "src")
for p in ["/mnt/passport/shared/toolkit/src", "../toolkit/src"]:
    if os.path.isdir(p):
        sys.path.insert(0, p)
        break

from pathlib import Path

# Read T2 notes directly from vault
vault = Path("vault/tier2")
if not vault.exists():
    print("No tier2 directory")
    sys.exit(0)

t2_files = list(vault.glob("*.md"))
print(f"Total T2 notes: {len(t2_files)}")

placeholders = []
real = []
for f in t2_files:
    content = f.read_text(encoding="utf-8")
    # Split frontmatter and body
    parts = content.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
    else:
        body = content.strip()
    
    if "summary unavailable" in body:
        placeholders.append((f.name, body[:200]))
    else:
        real.append((f.name, body[:200]))

print(f"  Real summaries: {len(real)}")
print(f"  Placeholders: {len(placeholders)}")

if real:
    print(f"\n--- Sample real T2 summaries ---")
    for name, body in real[:3]:
        print(f"\n  {name}:")
        print(f"    {body.replace(chr(10), ' ')[:300]}")

if placeholders:
    print(f"\n--- Placeholder T2 notes ---")
    for name, body in placeholders[:5]:
        print(f"\n  {name}: {body}")

# Now check T1 notes — look for obvious junk
print(f"\n--- T1 junk check ---")
t1_files = list(Path("vault/tier1").glob("*.md"))
junk_count = 0
junk_samples = []
for f in t1_files[:500]:  # sample
    try:
        content = f.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
        else:
            body = content
        # Check for junk patterns
        words = body.split()
        if len(words) < 5:
            junk_count += 1
            if len(junk_samples) < 5:
                junk_samples.append((f.name, body[:100]))
        elif body.count("http") > 3 and len(words) < 15:
            junk_count += 1
            if len(junk_samples) < 5:
                junk_samples.append((f.name, body[:100]))
    except:
        pass

print(f"  Sampled 500 T1 notes, found {junk_count} junk")
for name, body in junk_samples:
    print(f"    {name}: {body.replace(chr(10), ' ')}")
