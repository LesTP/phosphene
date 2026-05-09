# Codex Worker Adapter — Phosphene

> **Contract:** Follow `WORKER_SPEC.md` for the 4-state machine, one-action
> rule, escalation conditions, and output contract. This file covers
> Codex-specific mechanics only.

## Framework
From Idea to Code — governance framework for multi-session autonomous development.

## Required Reading — Every Iteration

You do not have `@`-reference loading. You must explicitly read these files at
the start of every iteration before taking any action.

**CRITICAL: Minimize tool calls.** Each tool call round-trips through the full
context window. Combine reads into as few shell commands as possible.

### Tier 1 — Always (mandatory, every iteration)

Read CODEX.md (this file), WORKER_SPEC.md, and DEVPLAN.md (up to the HISTORY
fence) in a **single command**:

```bash
cat CODEX.md && echo '---SPLIT---' && cat WORKER_SPEC.md && echo '---SPLIT---' && awk '/HISTORY/{exit} {print}' DEVPLAN.md
```

**DEVLOG.md:** Append new entries at the bottom (newest last). During phase
close, archive the previous phase's entries to `DEVLOG_archive.md`.

### Tier 2 — Current module (mandatory for execute/review/close actions)

After determining the active module from DEVPLAN's Current Status, read the
relevant `ARCH_*.md` file (see table below). Combine with any source files
you need in the **same command**.

### Tier 3 — On demand (read only when needed)
- `PROJECT.md` — only during phase plan actions
- `ARCHITECTURE.md` — only during phase plan or cross-module wiring
- `GOVERNANCE.md` — only if unsure about process

### Read efficiency rules
- **Combine related reads** into one `cat A && echo '---' && cat B` command
- **Never read one file per tool call** when you need multiple files
- **Fresh reads before edits** — re-read immediately before editing, not at iteration start

## Load for Current Module

| Module | ARCH file |
|--------|-----------|
| Memory Store | `ARCH_memory_store.md` |
| Attention Filter | `ARCH_attention_filter.md` |
| Source Ingestion | `ARCH_source_ingestion.md` |
| Gateway | `ARCH_gateway.md` |
| Generator + Output Router | `ARCH_generator.md` |
| Distillation | `ARCH_distillation.md` |
| Feedback Collector | `ARCH_feedback_collector.md` |
| Explorer | `ARCH_explorer.md` |
| Orchestrator | `ARCH_orchestrator.md` |

## Available Modules

**Track A — Foundation:**
- Module 1: Memory Store — three-tier hierarchical memory (leaf, everything depends on it)

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
- **Model policy:** D-5 in DECISIONS.md — single primary model during establishment phase (~90 days).
- **Gotchas:**
  - toolkit/ is an external dependency — import from it, never modify it.
  - All 9 ARCH files define contracts — implementation must match signatures exactly.
  - NTFS drives: use `bash script.sh`, not `./script.sh`.
  - **No ripgrep** — `rg` is not installed. Use `find` and `grep` instead.
  - **Test environment** — `.python_deps/` contains pip dependencies (gitignored, persists). Do NOT recreate `.venv`.
  - **Subagent context** — when spawning subagents, include: source tree is `src/phosphene/<module>/`, test command is `PYTHONPATH=src:.python_deps python3 -m pytest`, `.python_deps/` has all deps.

## Codex-Specific Tool Rules
- **No `@` references.** Read files explicitly using CLI.
- **Minimize tool calls.** Combine reads into single shell commands.
- **Command files shared with Claude.** Read `.claude/commands/*.md` and follow their instructions.
- **Search tool availability.** Use `find` for discovery, `grep -RIn` for search. Do not attempt `rg`.

## Action Instructions

WORKER_SPEC.md defines four states. Read `state` from DEVPLAN frontmatter
and execute the matching action. Perform **exactly one** per iteration
unless `steps_remaining` > 0 (see WORKER_SPEC.md §4 for multi-step budget).

### state: plan
1. Read `.claude/commands/phase-plan.md` and follow its instructions.
2. Set DEVPLAN frontmatter `state: execute`. Commit.
3. Emit exit signal and stop (or continue to first step if steps_remaining > 0).

### state: execute
1. Pick the next step from DEVPLAN. Do all file read/write work.
2. Run tests. Read `.claude/commands/step-done.md` and follow its instructions.
3. Emit exit signal and stop. Do **not** start the next step unless `steps_remaining > 0`.

### state: review
1. Read `.claude/commands/phase-review.md` and follow its instructions.
2. Set DEVPLAN frontmatter `state: close`. Commit.
3. Emit exit signal and stop.

### state: close
1. Read `.claude/commands/phase-complete.md` and follow its instructions.
2. Set DEVPLAN frontmatter `blocked: true`. Commit.
3. Emit exit signal with ESCALATE and stop.

## Output Contract

End every iteration with exactly these four lines:

```
LOOP_SIGNAL: CONTINUE | ESCALATE
REASON: <one-line summary>
ACTION_TYPE: PLAN | EXECUTE | REVIEW | CLOSE
ACTION_ID: <phase.step>
```
