---
module: SOURCE_INGESTION
phase: 1.5
phase_title: Coverage tooling infra reviewed; ready for completion
step: 3.1.5.complete
mode: Complete
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
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — Module 3 Phase 1.5 (infra): coverage tooling baseline before Phase 2 planning
- **Focus** — Phase 1.5 reviewed; ready for phase completion
- **Blocked/Broken** — None

## Module 1: Memory Store (complete)

Four-phase plan (matching ARCH_memory_store.md public API surface) — all phases complete.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (complete)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`. See DEVLOG "Phase 4 Completion" entry.

## Module 2: Attention Filter (complete)

Planned phases follow `ARCH_attention_filter.md`: first stabilize the public contract (including `ScoringConfig`) and deterministic geometric scoring helpers, then add Memory Store retrieval/embedding integration, then LLM Phase 1 scoring (precision_surplus) and assertion extraction (friction), then full batch orchestration with triple-gate blend.

### Phase 1 (audited complete): Attention Filter contract and scoring foundation

Delivered ARCH-aligned public dataclasses/exports, default precision-surplus criteria, config validation, triple-gate blend helpers, deterministic Phase 2 geometric scoring helpers, and focused tests. Audited complete. See DEVLOG "Phase 2.1 Completion" and "Phase 2.1 Audit Closure" entries.

### Phase 2 (reviewed complete): Memory Store retrieval and embedding integration

Delivered embedding boundary integration, Memory Store density reads, similar-note retrieval contexts, Memory Store-backed structural preparation, and non-LLM public-path wiring without Memory Store writes or premature LLM/annotation behavior. Reviewed complete. See DEVLOG "Phase 2.2 Completion" and "Phase 2.2 Audit Closure".

### Phase 3 (complete): LLM Phase 1 scoring and assertion extraction

Delivered private LLM prompt scoring, precision-surplus composite integration, incoming assertion extraction, friction-preparation records, and public-path regression coverage while preserving the no-accepted-fragments boundary before orchestration. Reviewed and completed. See DEVLOG "Phase 2.3 Review" and "Phase 2.3 Completion" entries.

### Phase 4 (complete): Full batch orchestration and annotation output

Delivered annotation generation, acceptance and auto-accept decisions, public `AnnotatedFragment` assembly, rejected counts, batch metadata, and Phase 2 assertion-extraction gating while preserving read-only Memory Store behavior. Reviewed and completed. See DEVLOG "Phase 2.4 Review" and "Phase 2.4 Completion" entries.

## Module 3: Source Ingestion (in progress)

Planned phases follow `ARCH_source_ingestion.md`: first stabilize the public contract, manager orchestration, adapter registry boundary, shared content normalization, and state-marker abstraction without live network adapters; then add concrete autonomous adapters, human-share handling, corpus import adapters, and persistence/integration hardening.

### Phase 1 (complete): Source Ingestion contract and adapter foundation

Delivered ARCH-aligned public dataclasses/exports, config validation, adapter protocol/registry, manager polling orchestration, per-adapter error reporting, in-memory last-seen marker handoff, deterministic normalization helpers, and focused unit tests. Reviewed and completed. See DEVLOG "Phase 3.1 Review" and "Phase 3.1 Completion" entries.

### Phase 1.5 (active): Coverage tooling infra

Project-level infra step inserted at the Module 3 Phase 1 → Phase 2 boundary, per the "Coverage tooling" entry in ARCHITECTURE.md "Deferred Test Investments". Single isolated step. Not a Source Ingestion logic change — instrumentation only, no source or test code modifications.

- [x] **Step 3.1.5.infra** — Add `pytest-cov` to `pyproject.toml` dev dependencies, install it into the existing `.python_deps/` target (`pip install --target .python_deps pytest-cov`), then run a baseline coverage report:

  ```bash
  PYTHONPATH=src:.python_deps python3 -m pytest tests/ --cov=src/phosphene --cov-report=term-missing
  ```

  Capture the baseline numbers in a DEVLOG entry — overall coverage % plus per-module breakdown (memory_store, attention_filter, source_ingestion). Note any module below 80% as a follow-up worth flagging (do not fix in this step). Commit the `pyproject.toml` change and the DEVLOG entry. Do NOT modify any `src/` or `tests/` files — purpose is purely instrumentation and baseline capture.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
