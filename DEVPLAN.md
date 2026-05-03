---
module: 2
phase: 4
phase_title: Full batch orchestration and annotation output
step: 4
mode: Build
blocked: false
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
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — Module 2 (Attention Filter), Phase 4 in progress: Full batch orchestration and annotation output.
- **Focus** — Next step: 2.4.4 Public batch orchestration regression.
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

### Phase 2 (reviewed complete): Memory Store retrieval and embedding integration

Delivered embedding boundary integration, Memory Store density reads, similar-note retrieval contexts, Memory Store-backed structural preparation, and non-LLM public-path wiring without Memory Store writes or premature LLM/annotation behavior. Reviewed complete. See DEVLOG "Phase 2.2 Completion" and "Phase 2.2 Audit Closure".

### Phase 3 (complete): LLM Phase 1 scoring and assertion extraction

Delivered private LLM prompt scoring, precision-surplus composite integration, incoming assertion extraction, friction-preparation records, and public-path regression coverage while preserving the no-accepted-fragments boundary before orchestration. Reviewed and completed. See DEVLOG "Phase 2.3 Review" and "Phase 2.3 Completion" entries.

### Phase 4 (planned): Full batch orchestration and annotation output

Scope: turn the private per-item evaluation records from Phases 2-3 into the public `FilterResult` contract: threshold/auto-accept decisions, generated annotations, accepted `AnnotatedFragment` objects, rejected counts, and batch metadata. The Attention Filter remains read-only against Memory Store; consumers store accepted fragments later. Cluster-cache scoring beyond retrieved-note structural signals stays behind the existing preparation boundary until Distillation owns the assertion/centroid cache format.

- [x] **Step 2.4.1 — Annotation generation boundary and parsing.** Added the private LLM annotation request/parser over accepted evaluation candidates, with tests for prompt payload shape, config/tier propagation, annotation text normalization, malformed payload handling, unchanged LLM error propagation, and multi-candidate wrapping.
- [x] **Step 2.4.2 — Acceptance decisions and retention criteria.** Added deterministic decision helpers for composite thresholding, `auto_accept_sources` bypass, rejected counts, and retention criteria attribution from prompt and structure score maps. Tests cover threshold edges, auto-accepted low-score items, zero-score rejects, batch accepted/rejected bookkeeping, and no Memory Store writes.
- [x] **Step 2.4.3 — AnnotatedFragment assembly.** Built public fragments from accepted evaluations with original content metadata, annotation, importance score, unresolvedness, prompt/structure scores, friction target, connections, linked URLs, and embedding. Tests verify exact field mapping and that accepted fragments carry consumer-ready data without calling Memory Store write APIs.
- [ ] **Step 2.4.4 — Public batch orchestration regression.** Wire the full non-empty `filter_content` path end to end with fake embedding and LLM boundaries. Tests should cover mixed accepted/rejected batches, auto-accept behavior, prompt/structure blend metadata, LLM call ordering, empty batch stability, and the Attention Filter plus Memory Store slices.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
