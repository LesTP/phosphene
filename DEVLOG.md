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
