---
module: GATEWAY
phase: 2
phase_title: Gateway Phase 2 — Telegram adapter delivery and polling
step: 4.2.5
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
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.
  - **No ripgrep** — `rg` is not installed in the Codex container. Use `find` and `grep` instead. Do not attempt `rg` on first command.
  - **Subagent context** — when spawning Explore or review subagents, include in the prompt: (1) source tree layout is `src/phosphene/<module>/`, not `src/<module>/`; (2) the working test command is `PYTHONPATH=src:.python_deps python3 -m pytest`; (3) `.python_deps/` contains all pip dependencies. Subagents have no memory of the parent's environment discovery.

## Current Status

- **Phase** — Module 4 Phase 2 ready for review
- **Focus** — Review concrete Telegram Gateway adapter delivery and polling
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

## Module 3: Source Ingestion (complete)

Planned phases follow `ARCH_source_ingestion.md`: first stabilize the public contract, manager orchestration, adapter registry boundary, shared content normalization, and state-marker abstraction without live network adapters; then add concrete autonomous adapters, human-share handling, corpus import adapters, and persistence/integration hardening.

### Phase 1 (complete): Source Ingestion contract and adapter foundation

Delivered ARCH-aligned public dataclasses/exports, config validation, adapter protocol/registry, manager polling orchestration, per-adapter error reporting, in-memory last-seen marker handoff, deterministic normalization helpers, and focused unit tests. Reviewed and completed. See DEVLOG "Phase 3.1 Review" and "Phase 3.1 Completion" entries.

### Phase 1.5 (complete): Coverage tooling infra

Added `pytest-cov` dev tooling and captured the full-suite baseline: 310 tests pass, 98% total coverage, no tracked module below 80%. Reviewed and completed. See DEVLOG "Phase 3.1.5 Review" and "Phase 3.1.5 Completion" entries.

### Phase 2 (complete): Concrete adapters, human-share, and corpus import

Delivered shared adapter utilities, RSS/Atom, local and structured corpus adapters, human-share, Telegram channel, Reddit, Source Ingestion-owned durable marker persistence, and cross-adapter manager coverage while keeping public dataclasses stable and avoiding a Memory Store dependency. Reviewed and completed. See DEVLOG "Phase 3.2 Completion" entry.

## Module 4: Gateway (in progress)

Planned phases follow `ARCH_gateway.md`: first stabilize the public Gateway contract, validation, adapter registry, outbound routing, local log adapter, and listener callback semantics with fake/local adapters; then add concrete Telegram delivery and polling behavior through the toolkit boundary.

### Phase 1 (complete): Gateway contract and adapter foundation

Delivered ARCH-aligned Gateway dataclasses/errors/exports, config validation, internal adapter registry/lifecycle, outbound routing, local log delivery, fake inbound/feedback dispatch, callback exception isolation, and bounded in-memory delivery tracking. Reviewed and completed. See DEVLOG "Phase 4.1 Completion" entry.

### Phase 2 (in progress): Telegram adapter delivery and polling

Build the concrete Telegram Gateway adapter behind the existing internal adapter protocol without changing public dataclasses. Keep Source Ingestion separate from human-facing Gateway behavior and keep tests credential-free with fake toolkit clients.

- [x] **Step 4.2.1 — Telegram adapter construction and toolkit boundary**: Replace the pending Telegram adapter with a concrete internal adapter, isolate toolkit client construction behind an injectable factory, validate missing toolkit/factory failures as `PlatformConfigError`, and cover construction without live credentials.
- [x] **Step 4.2.2 — Outbound Telegram delivery**: Route `text`, `markdown`, `thread`, and `telegraph` sends through the toolkit boundary, map platform message IDs into `DeliveryResult`, preserve reply and intent metadata, and convert toolkit/API failures into failed delivery results.
- [x] **Step 4.2.3 — Polling listener lifecycle and inbound normalization**: Add non-blocking Telegram polling start/stop behavior, normalize incoming updates to `InboundMessage`, honor `listen=False` and idempotent lifecycle semantics, and keep callback exception isolation in Gateway-owned dispatch.
- [x] **Step 4.2.4 — Telegram feedback signal normalization**: Detect supported Telegram feedback events from replies/reactions/edits exposed by the toolkit boundary, normalize them to `FeedbackSignal`, and preserve raw payload metadata for downstream attribution.
- [x] **Step 4.2.5 — Gateway Telegram integration hardening**: Add end-to-end fake-client coverage for mixed log/Telegram configs, listener stop cleanup, recent-delivery tracking with Telegram IDs, and full Gateway test-suite verification.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
