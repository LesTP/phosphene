---
module: MEMORY_STORE
phase: 2
phase_title: Index layer and queries
step: null
mode: Review
blocked: null
regime: Build
review_done: false
---

# Phosphene — Development Plan

<!-- This file is the primary state document for autonomous iteration.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses. -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step. -->

- **What this is** — Autonomous personality agent with hierarchical memory, attention filtering, and personality development through distillation.
- **Key constraints** — Python 3.12+. Depends on toolkit/ (sibling project, all modules complete). Obsidian-compatible markdown storage. LLM API costs managed via subscription rotation and model tier system. Runs on Raspberry Pi 5 (orchestration only, inference via API).
- **Gotchas** —
  - toolkit/ is an external dependency — import from it, never modify it
  - Memory Store uses consumer-provided embeddings (no toolkit/embedding dependency in the store itself)
  - All 10 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — 2 — Index layer and queries
- **Focus** — Phase review
- **Blocked/Broken** — None

## Module 1: Memory Store

Four-phase plan (matching ARCH_memory_store.md public API surface). Phases 3–4 are sketched here for orientation only and will each get their own Phase Plan when reached.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (in progress)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting. Also retrofits Phase 1 `get_note` and `update_note` to read via the index instead of scanning tier directories (per D-8).
- **Phase 3** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`.
- **Phase 4** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`.

### Phase 2 Step Plan

Regime: Build. Three steps. Each step ends with passing `tests/memory_store` and a commit.

**Step 1 (complete) — Index data model, rebuild on init, `get_index`**

- New private module `phosphene.memory_store.index` exposing an `Index` object that owns:
  - `entries: dict[note_id → IndexEntry-shaped record]` (carries tier, title, importance, unresolvedness, tags, source, created_at, outbound link list, plus the markdown path so `get_note` can locate the file without a directory scan).
  - `inbound: dict[note_id → int]` — incremented for every target id appearing in any note's `links`.
- `MemoryStore.__init__` constructs the index by walking `tier1/`, `tier2/`, `tier3/`, parsing each note's frontmatter via `parse_note`, and registering the entry. Duplicate `note_id` across tiers raises `VaultError`.
- Public method `get_index(tier=None) -> list[IndexEntry]` — projects the internal entries down to `IndexEntry` (no link path, no source, since `IndexEntry` only carries the fields in the ARCH dataclass), filters by tier when given, sorts by `created_at` descending, validates tier in `{1,2,3}` else raises `InvalidTierError`.
- `store_note` and `update_note` are NOT yet wired to the index in this step (still write through, but the in-memory index is rebuilt only at init). To keep `get_index` consistent across the step boundary, the simplest path is: at end of `store_note` / `update_note`, register/refresh the in-memory entry. That avoids the index going stale within a process. Inbound counts for stored/updated notes are also recomputed on the affected target ids at this step.

  *Acceptance:* index correctness after constructor on populated vaults, after `store_note`, and after `update_note` (links change → inbound counts change). `get_note`/`update_note` still scan tier dirs in this step — retrofit lands in Step 2.
- Tests (`tests/memory_store/test_index.py`):
  - empty vault → `get_index()` returns `[]`
  - constructor on a vault with notes across all three tiers rebuilds entries; `get_index()` returns all three sorted by `created_at` desc
  - `get_index(tier=2)` filters correctly; tier=0 / tier=4 raise `InvalidTierError`
  - `store_note` adds an entry to the index immediately (visible in next `get_index` call without re-init)
  - `update_note` reflects new title/importance/unresolvedness/tags in the index entry
  - duplicate `note_id` in two tier directories → constructor raises `VaultError`
  - inbound count: A links to B → B's inbound count = 1; remove via `update_note` → B's inbound count = 0; second source linking B → count = 2.

**Step 2 (complete) — Inbound link counts on `MemoryNote`; retrofit `get_note`/`update_note` via index**

- `get_note` resolves the note's path through `index.entries[note_id]` instead of scanning tier subdirectories. Raise `NoteNotFoundError` when the index has no such id. The tier-scan helper `_find_note_path` is removed.
- `update_note` resolves the path the same way. After mutation, the index entry is refreshed. If `patch.links` is provided, inbound counts are decremented for old targets and incremented for new ones.
- `MemoryNote.link_count` returned from `get_note` and `update_note` is now `inbound_count(note_id) + len(note.links)` per the ARCH definition. Disk frontmatter still stores outbound-only `link_count` for round-trip stability; the inbound contribution is added at read time. (This keeps `serialize_note`/`parse_note` unchanged and avoids invalidating Phase 1's stored files.)
- Tests (`tests/memory_store/test_index.py` — extend; `tests/memory_store/test_crud.py` — extend):
  - `get_note(B).link_count` reflects inbound after A links to B
  - `update_note` removing links decrements the prior targets' inbound counts (visible via subsequent `get_note(target).link_count`)
  - `get_note` on a missing id raises `NoteNotFoundError` (still); behavior preserved through retrofit
  - existing `test_crud.py` cases continue to pass — their fixtures link to non-existent ids, so inbound for the round-trip note remains 0 and `link_count` equals outbound count.
  - **Index-drift recovery (regression guard for D-11):** mutate `MemoryStore._index.inbound` to a deliberately wrong value, instantiate a new `MemoryStore` on the same vault, and assert the rebuilt inbound counts match the on-disk truth. Guards against silent drift if a future write path forgets to update the index — restart corrects it.

**Step 3 (complete) — `query_notes`**

- Implement `query_notes(query: NoteQuery) -> list[MemoryNote]`:
  - Validates `query.tier` in `{1,2,3}` when given; raises `InvalidTierError` otherwise.
  - Filters using the in-memory index (cheap predicates), then loads matching notes from disk via `parse_note` to return full `MemoryNote` objects (with inbound-augmented `link_count`).
  - Predicates: `tier`, `min_importance`, `min_unresolvedness`, `tags` (any-of), `source`, `since` (`created_at >= since`), `until` (`created_at <= until`).
  - Order by one of `created_at | importance | unresolvedness | link_count` (validated; reject other strings). Honor `descending` flag. Apply `limit` (default 50).
- Tests (`tests/memory_store/test_query.py`):
  - each filter independently across a fixture set spanning all tiers
  - combined filters
  - each `order_by` value, ascending vs descending
  - `limit` truncates results
  - `tier=4` raises `InvalidTierError`
  - empty result set returns `[]`
  - returned notes carry inbound-augmented `link_count`.

### Phase 2 Acceptance

- All Phase 1 tests still pass.
- New test files `test_index.py` and `test_query.py` pass.
- `get_note` and `update_note` no longer scan tier directories.
- `MemoryNote.link_count` reflects inbound + outbound.
- `ARCH_memory_store.md` Phase 1/Phase 2 split language matches the now-shipping behavior (no contract changes; this phase fulfills the Phase 2 commitments already in the ARCH).

<!-- HISTORY — Worker: stop reading here. Everything below is completed phase history. -->
