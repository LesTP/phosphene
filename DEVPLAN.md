---
phase: MVP.3
blocked: false
state: execute
steps_remaining: 5
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
  - **Turn health check** — Codex iterations include `ITERATION_JSONL` in the prompt. At step-done, the worker checks `grep -c '"item.completed"' $ITERATION_JSONL` and escalates if total turns exceed `steps_completed × 50` (spiraling detection). See WORKER_SPEC.md §4.

## Current Status

- **Module** — MVP Orchestrator (skipping ahead of Module 7 Phase 2 and Module 8 to reach MVP).
- **Phase** — MVP.3: Integration hardening.
- **Focus** — Step 3: Bootstrap transition.
- **Blocked/Broken** — See frontmatter gate.
- **Contract** — ARCH_orchestrator_mvp.md (strict subset of ARCH_orchestrator.md)

## MVP Orchestrator

*The MVP Orchestrator wires Modules 1–6 into a running system. It is the minimum needed to satisfy PROJECT.md MVP Definition: cron-triggered ingestion, distillation, generation, and decay — no lateral freedom, no tension-responsive scheduling, no ambient context, no feedback loop. See ARCH_orchestrator_mvp.md for the full contract.*

### Phase MVP.1: Contract and cron loop

Complete. Delivered the MVP Orchestrator public contract, constructor validation, cron due-entry evaluation, start/stop/trigger lifecycle, Phase 1 stub dispatch, and foundation tests. See `DEVLOG.md` Phase MVP.1 entries for details.

### Phase MVP.2: Activation wiring

Complete. Wired ingestion, distillation, generation/bootstrap, respond/listener dispatch, and decay activations to Modules 1–6 with fake-module verification. See `DEVLOG.md` Phase MVP.2 entries for details.

### Phase MVP.3: Integration hardening

**Goal:** Error isolation, logging, restart resilience, and end-to-end proof.

**Steps:**

1. **Error isolation** — Complete. Dispatch wraps `_run_*` calls in try/except, unhandled module exceptions produce `ActivationResult(success=False, error=str(exc))`, and loop tests verify a failed activation does not prevent subsequent activations in the same iteration.

2. **Activation logging** — Complete. When `config.log_path` is set, activations append JSON-serialized `ActivationResult` lines via same-directory temp write and rename; tests verify multiple records and no file I/O when `log_path` is missing.

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

608 tests passing as of Phase MVP.2 completion.

<!--
HISTORY — Do not read past this marker.
Completed phase history below.
-->
