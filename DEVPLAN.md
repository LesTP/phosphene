---
module: MEMORY_STORE
phase: 4
phase_title: Decay, supersession, and density metrics
step: null
mode: Review
blocked: null
regime: Build
review_done: true
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

- **Phase** — 4 — Decay, supersession, and density metrics
- **Focus** — Phase Complete: apply DEVLOG learning review, ARCHITECTURE status update, DEVPLAN cleanup, and frontmatter reset. Phase 4 review complete (see DEVLOG "Phase 4 Review" entry).
- **Blocked/Broken** — None

## Module 1: Memory Store

Four-phase plan (matching ARCH_memory_store.md public API surface).

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (in progress)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`.

### Phase 4 Step Plan

Regime: Build. Four steps. Each step ends with passing `tests/memory_store` and a commit.

**Step 1 — `get_density_metrics`**

- Extend `phosphene.memory_store.index.IndexedNote` with `cluster_group: str | None`. Populate it in `Index.register` from `MemoryNote.cluster_group`. No public `IndexEntry` change.
- Implement `MemoryStore.get_density_metrics() -> DensityMetrics` purely from the in-memory index — no markdown reads:
  - `note_count` = `len(self._index.entries)`
  - `tier_counts` = `{1: n1, 2: n2, 3: n3}` — every tier key present even when zero (keys 1/2/3 always populated)
  - `mean_link_degree` = mean over all notes of `inbound_count(id) + len(entry.links)`. `0.0` when `note_count == 0`.
  - `cluster_count` = number of distinct non-`None` `cluster_group` values across **Tier 2** entries only
  - `unresolved_count` = entries with `unresolvedness > 0.5` (strict greater-than, ARCH-stated threshold)
  - `max_unresolvedness` = max across all entries (`0.0` when empty)
- Tests (`tests/memory_store/test_density.py` — new file):
  - empty vault returns zeros, all tier keys present, `max_unresolvedness == 0.0`
  - tier_counts reflects mixed-tier vault accurately
  - `mean_link_degree` averages inbound + outbound across all notes (verify with a hand-computed example: a 4-note graph with two A→B and one C→A links)
  - `cluster_count` counts distinct Tier 2 `cluster_group` values; ignores `None`; ignores cluster_group set on Tier 1/3
  - `unresolved_count` strict `> 0.5` (a note at exactly 0.5 is *not* counted)
  - `max_unresolvedness` returns the highest score across all tiers
  - density metrics reflect freshly stored notes immediately (no rebuild needed); confirm after `add_links` updates inbound counts

**Step 2 (complete)** — `supersede`: added `MemoryNote.change_summary`, implemented Tier 3 supersession, logged D-14, and verified with `tests/memory_store`; see DEVLOG Step 2.

**Step 3 (complete)** — `run_decay`: implemented Tier 1 decay rules, `DecayReport` skeleton, markdown and embedding sidecar expiry cleanup, and verified with `tests/memory_store`; see DEVLOG Step 3.

**Step 4 (complete)** — `run_decay`: implemented Tier 2 cycle-window expiry, Tier 3 superseded-version expiry, full multi-tier `DecayReport`, added `tier2_cycle_window_days` (D-15), and verified with `tests/memory_store`; see DEVLOG Step 4.

**End of Phase 4:** `/phase-review` then `/phase-complete`. Review must verify: no public-API drift beyond `change_summary` (D-14) and `tier2_cycle_window_days` (D-15); `get_density_metrics` is index-only and cheap; `run_decay` cleans both markdown and embedding sidecars; supersession chain semantics align with `get_personality_context`.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
