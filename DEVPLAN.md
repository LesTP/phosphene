---
phase: MVP.1
blocked: "awaiting-human-audit"
state: close
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
  - **New dependency** — `croniter` needed for cron expression parsing. Install to `.python_deps` before Phase 1 implementation: `pip install --target .python_deps croniter`.

## Current Status

- **Module** — MVP Orchestrator (skipping ahead of Module 7 Phase 2 and Module 8 to reach MVP).
- **Phase** — MVP.1 complete: Contract and cron loop.
- **Focus** — Phase close complete.
- **Blocked/Broken** — See frontmatter gate.
- **Contract** — ARCH_orchestrator_mvp.md (strict subset of ARCH_orchestrator.md)

## MVP Orchestrator

*The MVP Orchestrator wires Modules 1–6 into a running system. It is the minimum needed to satisfy PROJECT.md MVP Definition: cron-triggered ingestion, distillation, generation, and decay — no lateral freedom, no tension-responsive scheduling, no ambient context, no feedback loop. See ARCH_orchestrator_mvp.md for the full contract.*

### Phase MVP.1: Contract and cron loop

Complete. Delivered the MVP Orchestrator public contract, constructor validation, cron due-entry evaluation, start/stop/trigger lifecycle, Phase 1 stub dispatch, and foundation tests. See `DEVLOG.md` Phase MVP.1 entries for details.

### Phase MVP.2: Activation wiring

**Goal:** Wire each activation type to the real module APIs. Each step adds one activation type.

**Steps:**

1. **Ingestion activation** — `_run_ingestion()`: call `source_ingestion.poll()`, flatten items, call `attention_filter.filter_content(items, config.attention_filter_config)`, store accepted fragments as Tier 1 `NoteInput` via `memory_store.store_note()`. Fragment-to-NoteInput mapping: title from content truncation or annotation, tags from `retention_criteria`, importance from `importance_score`, unresolvedness from friction target presence. Return `ActivationResult` with `outputs_delivered=0`. Tests use fake modules (same pattern as Generator/Distillation phases).

2. **Distillation activation** — `_run_distillation()`: call `distillation_engine.check_gates(config.distillation_config)`. If `gates.t1_to_t2_ready`, call `distill_t1_to_t2()`. If `gates.t2_to_t3_ready`, call `distill_t2_to_t3()`. Catch `DistillationLockError` as skip (success=True). Catch `InsufficientDataError` / `NoPatternDataError` as skip. Return `ActivationResult`. Tests verify gate-not-ready skips, lock contention skips, and successful dispatch.

3. **Generation activation + bootstrap** — `_run_generation()`: call `memory_store.get_personality_context()`. If empty personality files, return early (bootstrap skip). Otherwise call `generator.generate(prompt, {}, config.generator_config)`, route via `route(output, config.router_config, gateway)`, return `ActivationResult` with `outputs_delivered` count. Catch `EmptyPersonalityError` as bootstrap skip. Tests verify bootstrap detection, successful generation→route→send path, and delivery failure isolation.

4. **Respond activation** — `_run_respond(message)`: same as generation but calls `generator.respond(message, {}, config.generator_config)`. Wire Gateway listener callback in `start()` via `gateway.start_listener()` with an `on_message` callback that dispatches respond activations inline. Bootstrap skip applies. Tests verify inbound message dispatch and bootstrap drop.

5. **Decay activation** — `_run_decay()`: call `memory_store.run_decay()`. Return `ActivationResult`. Simplest activation — one call, no conditionals.

**Boundary:** After Phase 2, `trigger("ingestion")` runs the full poll→filter→store pipeline through fake modules. Each activation type is independently testable. No error isolation beyond what individual modules provide — that's Phase 3.

### Phase MVP.3: Integration hardening

**Goal:** Error isolation, logging, restart resilience, and end-to-end proof.

**Steps:**

1. **Error isolation** — Wrap each `_run_*` call in try/except at the dispatch level. Any unhandled exception from a module produces `ActivationResult(success=False, error=str(exc))`. The main loop continues — one failed activation never stops the system. Tests verify that a throwing module doesn't prevent subsequent activations in the same loop iteration.

2. **Activation logging** — When `config.log_path` is set, append a JSON-serialized `ActivationResult` line after each activation. Use atomic write (write to temp, rename) to avoid partial lines on crash. Tests verify log file content after multiple activations, and that missing log_path means no file I/O.

3. **Bootstrap transition** — Verify the system correctly transitions from bootstrap (skip generation) to active (generate output) within a single run session when distillation produces the first personality files. Test: trigger ingestion (stores notes) → trigger distillation (produces Tier 2 + Tier 3) → trigger generation (now succeeds). This is the proof that the bootstrap arc works end-to-end.

4. **End-to-end integration test** — Single test using fake modules wired through real `MVPOrchestrator`. Proves the full content path: configure source ingestion with a fake adapter returning content items → trigger ingestion → verify Tier 1 notes stored → trigger distillation (fake gates ready) → verify distillation called → trigger generation → verify output routed through Gateway. This is the MVP validation test.

5. **Restart recovery** — Verify that constructing a new `MVPOrchestrator` with the same config and the same Memory Store vault resumes correctly: schedule re-derives from config, distillation metadata persists in vault, stored notes survive. No orchestrator-owned state file needed — all durable state lives in Memory Store. Test: construct → trigger ingestion → construct new instance → trigger generation → verify personality context is still available.

**Boundary:** After Phase 3, the MVP Orchestrator is deployable as a systemd service. The full ingestion→distillation→generation→delivery path works, errors are isolated, activations are logged, and the system survives restarts.

## Deferred Work

### Feedback Collector Phase 7.2 (post-MVP)
Delayed engagement checks and retention hardening. Will be wired into the Orchestrator after MVP is running and producing real output.

### Module 8: Explorer (post-MVP)
Link-following with pre-fetch scoring. Adds depth to ingestion but not required for MVP core loop.

### Full Orchestrator — Module 9 (post-MVP)
Extends MVP Orchestrator with lateral freedom, tension-responsive scheduling, ambient context assembly, budget tracking, and task arbitration per ARCH_orchestrator.md.

## Completed Modules (summary)

- **Pre-Module-7 Hardening** — Phase A (Attention Filter additions) and Phase B (unresolvedness composite + network diagnostics). Both complete.
- **Module 1: Memory Store** — Four phases, all complete. Three-tier CRUD, index, embedding search, decay, density metrics.
- **Module 2: Attention Filter** — Four phases, all complete. Prompt scoring, structural scoring, assertion extraction, batch orchestration, wild-card/near-miss partitioning.
- **Module 3: Source Ingestion** — Two phases + coverage tooling, all complete. Adapter framework, RSS, Telegram channel, Reddit, human-share, corpus import, durable markers.
- **Module 4: Gateway** — Two phases, all complete. Adapter framework, Telegram delivery/polling, feedback signal dispatch.
- **Module 5: Generator + Output Router** — Two phases, all complete. Prompted/response/free-play generation, skeptical memory, output routing.
- **Module 6: Distillation** — Three phases, all complete. T1→T2 RAPTOR clustering, T2→T3 reflect-evolve, personality supersession, criteria adjustments.
- **Module 7: Feedback Collector** — Phase 7.1 complete (immediate feedback). Phase 7.2 (delayed engagement) deferred to post-MVP.

593 tests passing as of Phase MVP.1 completion.

<!--
HISTORY — Do not read past this marker.
Completed phase history below.
-->
