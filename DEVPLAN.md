---
module: 2
phase: 2
phase_title: Memory Store retrieval and embedding integration
step: 4 of 4
mode: Review
blocked: false
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
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — Module 2 (Attention Filter), Phase 2: Memory Store retrieval and embedding integration.
- **Focus** — Phase 2 review.
- **Blocked/Broken** — None

## Module 1: Memory Store (complete)

Four-phase plan (matching ARCH_memory_store.md public API surface) — all phases complete.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (complete)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`. See DEVLOG "Phase 4 Completion" entry.

## Module 2: Attention Filter (in progress)

Planned phases follow `ARCH_attention_filter.md`: first stabilize the public contract (including `ScoringConfig`) and deterministic geometric scoring helpers, then add Memory Store retrieval/embedding integration, then LLM Phase 1 scoring (precision_surplus) and assertion extraction (friction), then full batch orchestration with triple-gate blend.

### Phase 1 (audited complete): Attention Filter contract and scoring foundation

Delivered ARCH-aligned public dataclasses/exports, default precision-surplus criteria, config validation, triple-gate blend helpers, deterministic Phase 2 geometric scoring helpers, and focused tests. Audited complete. See DEVLOG "Phase 2.1 Completion" and "Phase 2.1 Audit Closure" entries.

### Phase 2 (in progress): Memory Store retrieval and embedding integration

Regime: Build. Four steps. Each step ends with focused `tests/attention_filter` coverage plus the existing Memory Store and Attention Filter tests passing under the repo test pattern.

Scope boundary: this phase wires embeddings, Memory Store density reads, and similar-note retrieval into the Attention Filter. It does not add live LLM prompt scoring, assertion extraction, or final annotation generation; those remain later Module 2 phases.

**Step 1 (complete) — Embedding bridge and empty-batch result**

Added the private embedding boundary, import-isolated toolkit embedding call, empty-batch `FilterResult` path with density snapshot/blend weights, and focused tests. See DEVLOG "Step 2.2.1".

**Step 2 (complete) — Similar-note retrieval context**

Added private per-item retrieval contexts that embed each item once, call `memory_store.search_by_embedding` with the configured candidate limit, preserve ordered note ids/similarities/unresolvedness values, and normalize candidate metadata without Memory Store writes. See DEVLOG "Step 2.2.2".

**Step 3 (complete) — Memory-backed structural scores**

Added private Memory Store-backed structural evaluation over retrieval contexts, including `link_density`, `unresolvedness_affinity`, connection ids above threshold, and unset `friction_target`. See DEVLOG "Step 2.2.3".

**Step 4 (complete) — Partial non-LLM pipeline wiring**

Added private non-LLM item evaluations that combine retrieval contexts, Memory Store-backed structural scores, and current blend weights. Non-empty public `filter_content` now performs density, embedding, retrieval, and structural preparation with no Memory Store writes and returns batch metadata without manufacturing accepted fragments, rejected counts, LLM annotations, or final scoring. See DEVLOG "Step 2.2.4".

### Phase 2 Acceptance

- Existing Phase 1 Attention Filter tests still pass.
- New tests cover embedding boundary behavior, Memory Store density reads, similar-note retrieval, link-density connections, and unresolvedness-affinity scoring.
- Memory Store remains a read-only dependency from the Attention Filter.
- No live LLM scoring, assertion extraction, Distillation assertion-cache reads, or annotation generation are introduced in this phase.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
