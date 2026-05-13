"""Debug: create 20 notes directly and check which ones appear on disk."""
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
from datetime import datetime, timezone, timedelta
import numpy as np

vault_path = Path("vault_debug")
for d in ["tier1", "tier2", "tier3"]:
    (vault_path / d).mkdir(parents=True, exist_ok=True)

ms = MemoryStore(MemoryStoreConfig(
    vault_path=str(vault_path),
    embedding_path=str(vault_path / ".embeddings"),
))

# Create 20 test notes — mix of Cyrillic, English, same-timestamp pairs
test_cases = [
    ("Hello world", datetime(2004, 1, 1, tzinfo=timezone.utc)),
    ("Привет мир", datetime(2004, 1, 1, tzinfo=timezone.utc)),
    ("Тест заметки", datetime(2004, 1, 1, 0, 0, 1, tzinfo=timezone.utc)),
    ("Another test", datetime(2004, 1, 2, tzinfo=timezone.utc)),
    ("Ещё один тест", datetime(2004, 1, 2, tzinfo=timezone.utc)),
    # Same timestamp, different titles
    ("AAA", datetime(2003, 6, 15, tzinfo=timezone.utc)),
    ("BBB", datetime(2003, 6, 15, tzinfo=timezone.utc)),
    ("ААА", datetime(2003, 6, 15, tzinfo=timezone.utc)),
    ("БББ", datetime(2003, 6, 15, tzinfo=timezone.utc)),
    # No timestamp (falls back to now)
    ("No timestamp test 1", None),
    ("No timestamp test 2", None),
    ("Без метки времени", None),
    # Long Cyrillic title
    ("Очень длинный заголовок на русском языке который может обрезаться", datetime(2005, 3, 1, tzinfo=timezone.utc)),
    # Special chars
    ("Test: special & chars <here>", datetime(2005, 4, 1, tzinfo=timezone.utc)),
    ("Тест: спецсимволы & <тут>", datetime(2005, 4, 1, tzinfo=timezone.utc)),
    # Empty-ish after slug
    ("!!! ???", datetime(2005, 5, 1, tzinfo=timezone.utc)),
    ("... ---", datetime(2005, 5, 1, tzinfo=timezone.utc)),
    # Mixed
    ("Mixing English и Русский", datetime(2005, 6, 1, tzinfo=timezone.utc)),
    ("Context reply [context: user] text", datetime(2005, 7, 1, tzinfo=timezone.utc)),
    ("[context: bulatych] Ну да", datetime(2005, 7, 1, tzinfo=timezone.utc)),
]

stored = 0
for i, (title, ts) in enumerate(test_cases):
    note = NoteInput(
        tier=1, content=f"Content for: {title}", title=title,
        importance=0.5, source="test", tags=[],
        embedding=np.random.randn(384).astype(np.float32),
        created_at=ts,
    )
    try:
        nid = ms.store_note(note)
        path = note_path(vault_path, 1, nid)
        exists = path.exists()
        print(f"[{i+1:2d}] {'OK' if exists else 'MISSING'} id={nid[:50]:50s} title={title[:30]}")
        stored += 1
        if not exists:
            print(f"      PATH: {path}")
    except Exception as e:
        print(f"[{i+1:2d}] ERROR: {type(e).__name__}: {e}")

total = len(list((vault_path / "tier1").glob("*.md")))
print(f"\nStored: {stored}, Files: {total}, Missing: {stored - total}")
