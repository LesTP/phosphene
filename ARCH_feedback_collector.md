# ARCH: Feedback Collector — MOVED

This module has been extracted to the Toolkit project as of 2026-06-02.

**New location:** `toolkit/ARCH_feedback_collector.md` (and `toolkit/src/toolkit/feedback_collector/`).

Phosphene now consumes it via `from toolkit.feedback_collector import ...`. Public API unchanged. The collector's previous static import of `phosphene.memory_store.NoteInput` / `NotePatch` is replaced by internal `_NoteInput` / `_NotePatch` dataclasses that are structurally compatible with Phosphene's — Phosphene's `MemoryStore` accepts them by duck typing without code changes. See the toolkit ARCH for the memory-store contract.
