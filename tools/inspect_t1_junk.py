"""Check T1 notes for junk patterns that might cause LLM refusals."""
import sys, os
sys.path.insert(0, "src")
from pathlib import Path

vault = Path("vault/tier1")
if not vault.exists():
    print("No tier1 directory")
    sys.exit(0)

t1_files = sorted(vault.glob("*.md"))
print(f"Total T1 notes: {len(t1_files)}")

# Categories
very_short = []  # <20 chars body
link_only = []   # mostly URLs
boilerplate = [] # FB/LJ boilerplate
lyrics_only = [] # song lyrics with no commentary
other_junk = []

for f in t1_files:
    try:
        content = f.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) >= 3:
            body = parts[2].strip()
        else:
            body = content.strip()
        
        words = body.split()
        urls = [w for w in words if w.startswith("http")]
        
        if len(body) < 20:
            very_short.append((f.name, body[:100]))
        elif len(urls) > 0 and len(words) - len(urls) < 5:
            link_only.append((f.name, body[:150]))
        elif any(p in body.lower() for p in ["shared a", "added a new", "posted on", "wrote on"]):
            boilerplate.append((f.name, body[:150]))
    except:
        pass

print(f"\nJunk breakdown:")
print(f"  Very short (<20 chars): {len(very_short)}")
print(f"  Link-only: {len(link_only)}")
print(f"  Boilerplate: {len(boilerplate)}")

for label, items in [("Very short", very_short), ("Link-only", link_only), ("Boilerplate", boilerplate)]:
    if items:
        print(f"\n--- {label} samples ---")
        for name, body in items[:5]:
            print(f"  {body.replace(chr(10), ' ')[:150]}")
