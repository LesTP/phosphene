---
module: 2
phase: 3
phase_title: LLM Phase 1 scoring and assertion extraction
step: 1
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

- **Phase** — Module 2 (Attention Filter), Phase 3 in progress: LLM Phase 1 scoring and assertion extraction.
- **Focus** — Next step: 2.3.1 LLM prompt scoring boundary and score parsing.
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

### Phase 3 (in progress): LLM Phase 1 scoring and assertion extraction

Build phase scoped to live LLM calls that enrich the existing private per-item evaluation path. This phase adds precision-surplus prompt scoring and incoming-text assertion extraction for future friction scoring, while leaving final acceptance, annotation generation, and full batch orchestration for the next Attention Filter phase. See D-26.

- [ ] **Step 2.3.1 — LLM prompt scoring boundary and score parsing.** Add a private toolkit LLM boundary for Phase 1 prompt criteria, with deterministic fake-call tests covering request construction, tier/config propagation, score parsing, invalid payload handling, and unchanged LLM error propagation.
- [ ] **Step 2.3.2 — Precision-surplus prompt composite integration.** Compute weighted prompt scores from configured criteria inside the private item evaluation path, preserve the existing Memory Store retrieval/structural context, and keep public non-empty `FilterResult` output free of accepted fragments until annotation exists.
- [ ] **Step 2.3.3 — Incoming assertion extraction boundary.** Add a private assertion-extraction LLM boundary using `config.assertion_extraction_tier`, returning structured incoming assertions for friction scoring with tests for empty/noisy extraction, parser failures, tier propagation, and unchanged LLM error propagation.
- [ ] **Step 2.3.4 — Friction preparation from assertions and cached-cluster contract.** Add private friction-preparation records that pair incoming assertions with retrieved cluster identifiers and the existing Distillation assertion-cache contract, without inventing Memory Store writes or changing public dataclasses.
- [ ] **Step 2.3.5 — Phase 3 public-path regression coverage.** Cover the non-empty `filter_content` path end-to-end with fakes to verify embedding, retrieval, prompt scoring, assertion extraction, blend metadata, read-only Memory Store behavior, and the intentional absence of acceptance/annotation behavior before the orchestration phase.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
