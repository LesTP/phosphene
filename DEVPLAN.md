---
module: 2
phase: 1
phase_title: Attention Filter contract and scoring foundation
step: 2.1.1
mode: autonomous
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

- **Phase** — Module 2 (Attention Filter), Phase 1: Attention Filter contract and scoring foundation.
- **Focus** — Build the public Attention Filter package contract and deterministic scoring foundation before adding live embedding/LLM calls.
- **Blocked/Broken** — None

## Module 1: Memory Store (complete)

Four-phase plan (matching ARCH_memory_store.md public API surface) — all phases complete.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (complete)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`. See DEVLOG "Phase 4 Completion" entry.

## Module 2: Attention Filter (in progress)

Planned phases follow `ARCH_attention_filter.md`: first stabilize the public contract and deterministic scoring helpers, then add Memory Store retrieval/embedding integration, then LLM criteria and annotation, then full batch orchestration.

### Phase 1 (in progress): Attention Filter contract and scoring foundation

Regime: Build

Outcome: a testable `phosphene.attention_filter` package exposing the ARCH-defined dataclasses, errors, default prompt criteria, config validation, prompt/structure blend calculation, and deterministic structural scoring helpers. This phase deliberately excludes live toolkit embedding calls and LLM prompt execution; those are later phases.

Steps:

- [ ] **2.1.1** — Scaffold `phosphene.attention_filter` package exports, public dataclasses, and `InvalidScoreError` matching `ARCH_attention_filter.md`.
- [ ] **2.1.2** — Add default prompt criteria construction and validation for threshold, density crossover, candidate count, and criterion weights.
- [ ] **2.1.3** — Implement deterministic prompt/structure blend calculation from `DensityMetrics`, including empty-memory and high-density cases.
- [ ] **2.1.4** — Implement structural scoring helpers for link density, cluster novelty, unresolvedness affinity, friction target, and connection extraction from Memory Store search/index data.
- [ ] **2.1.5** — Add focused unit tests for package exports, dataclass defaults, validation failures, blend weights, and structural scoring edge cases.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
