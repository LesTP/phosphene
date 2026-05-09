# Claude Worker Adapter — Phosphene

> **Contract:** Follow `WORKER_SPEC.md` for the 4-state machine, one-action
> rule, escalation conditions, and output contract. This file covers
> Claude-specific mechanics only.

## Framework
From Idea to Code — governance framework for multi-session autonomous development.

## Required Reading — Every Iteration

### Tier 1 — Always (mandatory, every iteration)

Auto-loaded via @-references:

- @DEVPLAN.md — current status, cold start summary, gotchas
- @WORKER_SPEC.md — 4-state worker contract

### Tier 2 — Current module (mandatory for EXECUTE / REVIEW / CLOSE)

After determining the active module from DEVPLAN's Current Status, read the
relevant ARCH file using the lookup table below.

| Module | ARCH file |
|--------|----------|
| Memory Store | `ARCH_memory_store.md` |
| Attention Filter | `ARCH_attention_filter.md` |
| Source Ingestion | `ARCH_source_ingestion.md` |
| Gateway | `ARCH_gateway.md` |
| Generator + Output Router | `ARCH_generator.md` |
| Distillation | `ARCH_distillation.md` |
| Feedback Collector | `ARCH_feedback_collector.md` |
| Explorer | `ARCH_explorer.md` |
| Orchestrator | `ARCH_orchestrator.md` |

### Tier 3 — On demand (read only when needed)

- `PROJECT.md` — only during state: plan (scope, constraints, success criteria)
- `ARCHITECTURE.md` — only during state: plan, or cross-module wiring
- `GOVERNANCE.md` — only if uncertain about process

### Tier 4 — Reference only

- `DECISIONS.md` — read during review to verify no contract drift
- `DEVLOG.md` / `DEVLOG_archive.md` — read during close (learning review)

**DEVLOG.md:** Append new entries at the bottom (newest last). During phase
close, archive the previous phase's entries to `DEVLOG_archive.md`.

## Available Modules

**Track A — Foundation:**
- Module 1: Memory Store — three-tier hierarchical memory (leaf)

**Track B — Core Loop (content in):**
- Module 2: Attention Filter — personality-driven content selection
- Module 3: Source Ingestion — adapters for content sources

**Track C — Core Loop (content out):**
- Module 4: Gateway — multi-platform message bus
- Module 5: Generator + Output Router — content generation and delivery

**Track D — Development (personality evolves):**
- Module 6: Distillation — tier promotion, RAPTOR clustering, reflect-evolve

**Track E — Feedback and Depth:**
- Module 7: Feedback Collector — signal normalization, silence detection
- Module 8: Explorer — autonomous link-following

**Track F — Orchestration (wires everything):**
- Module 9: Orchestrator — activation lifecycle, scheduling, lateral freedom

## Project-Specific Notes
- **Language:** Python 3.12+
- **External dependency:** toolkit/ (sibling project). Import from toolkit — never modify it.
- **Storage format:** Obsidian-compatible markdown with YAML frontmatter.
- **Test command:** `PYTHONPATH=src:.python_deps python3 -m pytest tests/`
- **Key constraint:** Memory Store is a leaf dependency — stores/searches embeddings but never computes them.
- **Model policy:** D-5 in DECISIONS.md — single primary model during establishment phase.

## Claude-Specific Tool Rules
- **Edit tool requires fresh reads:** Re-read files immediately before editing.
- **No subagent spawning for simple tasks:** Use `bash find` or `bash ls` instead.
- Use `bash grep` instead of the Grep tool if built-in tools have path issues.

## Claude-Specific Runner Info
**Runner:** `run-iteration.sh` — runs `claude -p` per iteration, logs to `logs/loop/`.

**Slash commands:** Read `.claude/commands/*.md` and follow their instructions.
Do NOT call them via the Skill tool.

| State (from WORKER_SPEC) | Command file |
|--------------------------|-------------|
| plan | `.claude/commands/phase-plan.md` |
| execute | `.claude/commands/step-done.md` |
| review | `.claude/commands/phase-review.md` |
| close | `.claude/commands/phase-complete.md` |

## Output Contract

End every iteration with exactly these four lines:

```
LOOP_SIGNAL: CONTINUE | ESCALATE
REASON: <one-line summary>
ACTION_TYPE: PLAN | EXECUTE | REVIEW | CLOSE
ACTION_ID: <phase.step>
```
