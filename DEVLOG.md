# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Append new entries at the bottom (newest last).
     During phase close, archive the previous phase's entries to DEVLOG_archive.md. -->

<!-- Earlier entries archived — see DEVLOG_archive.md -->

### Step MVP.1.1: Public package contract

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Created the MVP Orchestrator package surface under `src/phosphene/orchestrator/`. Added ARCH-aligned public dataclasses for `MVPOrchestratorConfig`, `ScheduleEntry`, `ActivationResult`, and `ModuleRefs`; added the Orchestrator error hierarchy with `OrchestratorError`, `ConfigError`, and `UnknownTaskTypeError`; and exported the public API through `phosphene.orchestrator`.

Added the initial `MVPOrchestrator` constructor shell. It stores `modules` and `config` exactly as provided and intentionally performs no validation or module attribute inspection, leaving validation for MVP.1 step 2. Focused tests cover package exports, dataclass field order/defaults, error inheritance, and the no-validation constructor boundary. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator/test_orchestrator_exports.py` (4 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (578 passed).

### Step MVP.1.2: Config and ModuleRefs validation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented constructor validation for the MVP Orchestrator. `MVPOrchestrator` now rejects empty schedules, unknown scheduled task types, non-5-field cron strings, cron expressions rejected by `croniter`, missing module references, missing Memory Store methods, and missing Gateway `send()`.

Validation remains limited to constructor-time shape checks. The Memory Store and Gateway checks inspect callable attributes but do not invoke module methods, preserving the Phase MVP.1 boundary that all modules are held as references and no runtime APIs are called. Installed `croniter` into `.python_deps` per the DEVPLAN gotcha. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (11 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (585 passed).

### Step MVP.1.3: Cron evaluation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented private cron evaluation for the MVP Orchestrator. `MVPOrchestrator._next_due_entries(now)` now normalizes timestamps to UTC, tracks the previous check time per schedule-entry index, returns enabled entries whose cron fired in the `(last_check, now]` window, and advances each entry's last-check timestamp on every poll.

Added deterministic tests for first-call initialization, fired-since-last-check behavior, independent tracking across multiple schedule entries, and disabled-entry suppression. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (15 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (589 passed).

### Step MVP.1.4: Main loop and lifecycle

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the MVP Orchestrator lifecycle shell. `start()` now blocks in the 60-second sleep-poll loop, checks due cron entries, and dispatches each due entry sequentially through the Phase 1 stub dispatcher. `stop()` requests loop shutdown after the current activation, and `trigger(task_type)` runs a single activation synchronously.

Added `_run_activation(task_type)` as the Phase 1 dispatch stub: allowed scheduled task types return successful `ActivationResult` objects with zero delivered outputs, while unknown task types raise `UnknownTaskTypeError`. Focused tests cover trigger dispatch without module calls, unknown trigger rejection, sequential start-loop dispatch with no real sleep, and stop-before-poll shutdown. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (593 passed).

### Step MVP.1.5: Foundation tests

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Completed the Phase MVP.1 foundation test sweep for the public contract, constructor validation, cron evaluation, lifecycle loop, stop handling, trigger dispatch, and no-runtime-module-call boundary. The existing orchestrator coverage exercises package exports, dataclass fields and defaults, validation failures, fake-timestamp cron behavior, disabled schedule entries, no-real-sleep lifecycle dispatch, and stub activation behavior.

No production code changes were needed in this step. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (593 passed). Because this was the final Phase MVP.1 step, DEVPLAN frontmatter now advances to `state: review`; the next action is the Phase MVP.1 review.

### Phase MVP.1 Review: Contract and cron loop

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Reviewed the MVP Orchestrator Phase 1 implementation against `ARCH_orchestrator_mvp.md`. Must fix: none. Should fix: none. Optional: no optional cleanups deferred.

The implementation preserves the Phase 1 boundary: public types and errors are exported, constructor validation checks schedule/module shape without invoking module methods, cron evaluation is deterministic and per-entry, and lifecycle/trigger dispatch returns stub `ActivationResult` values without module runtime wiring. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (19 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (593 passed). DEVPLAN frontmatter now advances to `state: close`; the next action is Phase MVP.1 completion.

### Phase MVP.1 Completion: Contract and cron loop

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed MVP Orchestrator Phase 1. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (593 passed).

Phase MVP.1 delivered the minimal Orchestrator foundation behind `ARCH_orchestrator_mvp.md`: public config/schedule/result/module-reference types, exported error classes, constructor-time schedule and module-reference validation, deterministic cron due-entry evaluation, start/stop/trigger lifecycle behavior, and stub activation dispatch that returns successful `ActivationResult` values without invoking module runtime APIs.

DEVLOG learning review: MVP.1 landed linearly through five implementation steps and review. Step 2 installed `croniter` into `.python_deps`, matching the already-promoted DEVPLAN gotcha. No repeated trial-and-error pattern or new environment gotcha needs promotion.
Contract Changes scan: All MVP.1 step, review, and completion entries record "Contract changes: None". D-49 documents the Phase 1 scope boundary; no upstream contract propagation remains.
DEVPLAN cleanup: reduced Phase MVP.1 to a one-line completion summary, updated Current Status, and set the close gate in frontmatter.
ARCHITECTURE.md: MVP Orchestrator status updated from in progress to Phase MVP.1 complete.

(Entries before MVP.1 archived to DEVLOG_archive.md on 2026-05-08.)

### Phase MVP.2 Plan: Activation wiring

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Planned MVP Orchestrator Phase 2 as a Build phase with five testable activation-wiring steps: ingestion, distillation, generation/bootstrap, respond/listener, and decay. The phase remains inside `ARCH_orchestrator_mvp.md`: no lateral freedom, no ambient context, no feedback collector, no Explorer integration, and no Phase 3 error/logging hardening.

Recorded D-50 for the one-activation-per-step scope decision. DEVPLAN frontmatter now advances to `state: execute` with the invocation budget decremented to 4; the next action is MVP.2.1 ingestion activation.

### Step MVP.2.1: Ingestion activation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `_run_ingestion()` behind `trigger("ingestion")`. The activation now polls Source Ingestion, flattens returned items, calls `attention_filter.filter_content(items, config.attention_filter_config)`, maps accepted fragments to Tier 1 `NoteInput`, and stores them through `memory_store.store_note()`. Empty polls skip filtering and storage while still returning a successful `ActivationResult`.

Added fake-module orchestrator tests for the poll→filter→store path, empty-poll skip behavior, title fallback/truncation, tags, links, source, embedding, importance, and friction-gated unresolvedness mapping. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (22 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (596 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 3, and moves focus to MVP.2.2 distillation activation.

### Step MVP.2.2: Distillation activation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `_run_distillation()` behind `trigger("distillation")`. The activation now calls `distillation_engine.check_gates(config.distillation_config)`, skips cleanly when gates are not ready, dispatches `distill_t1_to_t2()` and `distill_t2_to_t3()` for ready gates, and treats `DistillationLockError`, `InsufficientDataError`, and `NoPatternDataError` as successful no-op skips.

Added fake-module orchestrator tests for gate-not-ready behavior, successful dual-promotion dispatch, and expected skip exceptions. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (27 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (601 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 2, and moves focus to MVP.2.3 generation activation + bootstrap.

### Step MVP.2.3: Generation activation + bootstrap

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `_run_generation()` behind `trigger("generation")`. The activation now loads `memory_store.get_personality_context()`, skips cleanly when no personality files exist, calls `generator.generate(config.generation_prompt, {}, config.generator_config)` when bootstrapped, routes the resulting output through `route(output, config.router_config, gateway)`, and reports `outputs_delivered=1` only for successful delivery results. `EmptyPersonalityError` is treated as a bootstrap skip.

Added fake-module orchestrator tests for empty personality bootstrap detection, `EmptyPersonalityError` bootstrap skip, successful generation→route→send delivery, and delivery failure isolation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (31 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (605 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 1, and moves focus to MVP.2.4 respond activation.

### Step MVP.2.4: Respond activation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `_run_respond(message)` for inbound Gateway messages. The activation now mirrors generation bootstrap behavior, calls `generator.respond(message, {}, config.generator_config)` when personality files exist, routes the output through `route(output, config.router_config, gateway)`, and counts only successful deliveries. `EmptyPersonalityError` is treated as a bootstrap drop.

Updated `start()` to register `_run_respond` as the Gateway `on_message` callback before starting the listener. Added fake-module tests for bootstrap drops, inline listener dispatch to respond, successful response routing, and `EmptyPersonalityError` handling. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (34 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (608 passed). DEVPLAN now keeps `state: execute`, sets `steps_remaining` to 0, and moves focus to MVP.2.5 decay activation.

### Step MVP.2.5: Decay activation

**Date:** 2026-05-08
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `_run_decay()` behind `trigger("decay")`. The activation calls `memory_store.run_decay()` and returns `ActivationResult(task_type="decay", success=True, outputs_delivered=0)`. No bootstrap check, no conditionals — the simplest activation in the suite.

Replaced the stub test `test_trigger_runs_unwired_decay_stub_without_calling_modules` with `test_trigger_decay_calls_run_decay_and_returns_success`, which verifies `run_decay()` is called exactly once and the result fields are correct. Extended `RecordingMemoryStore` with `decay_calls` tracking. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (34 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (608 passed). All five Phase MVP.2 activation steps are now complete — DEVPLAN transitions to `state: review`.

### Phase MVP.2 Review: Activation wiring

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Reviewed MVP.2 implementation against `ARCH_orchestrator_mvp.md`. Must fix: none. Should fix: none. Optional: none. The phase wires ingestion, distillation, generation/bootstrap, respond/listener dispatch, and decay within the MVP boundary; Phase 3 error isolation, activation logging, restart recovery, and end-to-end hardening remain deferred as planned.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (34 passed). DEVPLAN now transitions to `state: close`.
