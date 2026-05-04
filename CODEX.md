# Codex Worker Adapter — Phosphene

> **Contract:** Follow `WORKER_SPEC.md` for iteration lifecycle, allowed actions,
> one-action rule, escalation conditions, and output contract. This file covers
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
cat CODEX.md && echo '---SPLIT---' && cat WORKER_SPEC.md && echo '---SPLIT---' && awk '/<!-- HISTORY -->/{exit} {print}' DEVPLAN.md
```

**DEVLOG.md fence:** When reading or writing to DEVLOG.md, stop at the
`<!-- HISTORY` fence. Insert new entries **above** the fence line. Do not read
or patch content below it.

```bash
awk '/<!-- HISTORY -->/{exit} {print}' DEVLOG.md
```

### Tier 2 — Current module (mandatory for step/review/complete actions)

After determining the active module from DEVPLAN's Current Status, read the
relevant `ARCH_*.md` file (see table below). Combine with any source files
you need in the **same command**:

```bash
cat ARCH_memory_store.md && echo '---SPLIT---' && cat src/phosphene/memory_store/store.py
```

### Tier 3 — On demand (read only when needed)
- `PROJECT.md` — only during Phase Plan actions
- `ARCHITECTURE.md` — only during Phase Plan or cross-module wiring
- `GOVERNANCE.md` — only if unsure about process

### Read efficiency rules
- **Combine related reads** into one `cat A && echo '---' && cat B` command
- **Never read one file per tool call** when you need multiple files
- **Combine source + test reads**: `cat src/phosphene/memory_store/foo.py && echo '---' && cat tests/memory_store/test_foo.py`
- **Use `sed -n` ranges** only when you need a specific section, not the whole file
- **Fresh reads before edits** — re-read immediately before editing, not at iteration start

## Load for Current Module
After reading DEVPLAN, determine the active track and module from its Current
Status section. Then read the relevant `ARCH_*.md` file for the layer contract
and module dependencies:

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
- Module 3: Source Ingestion — adapters for content sources (including human-share and corpus import)

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
- **External dependency:** toolkit/ (sibling project). Import from toolkit — never modify it. All five toolkit modules are complete (embedding, clustering, llm_client, telegram_client, json_rpc).
- **Storage format:** Obsidian-compatible markdown with YAML frontmatter. Memory Store writes `.md` files to a vault directory.
- **Test strategy:** pytest. Unit tests per module. Integration tests at module boundaries (Type compatibility → Boundary tests → Bridge logic per GOVERNANCE.md cross-module pattern).
- **Key constraint:** Memory Store is a leaf dependency. It stores and searches embedding vectors but never computes them — consumers provide embeddings via toolkit/embedding.
- **Model policy:** D-5 in DECISIONS.md — single primary model during establishment phase (~90 days).
- **Gotchas:**
  - toolkit/ is an external dependency — import from it, never modify it.
  - All 9 ARCH files define contracts — implementation must match signatures exactly.
  - NTFS drives: use `bash script.sh`, not `./script.sh`.

## Codex-Specific Tool Rules
- **No `@` references.** Read files explicitly using CLI.
  When a file contains `@FILENAME` references, treat them as file paths to read.
- **Minimize tool calls.** Every tool call re-processes the full context. Combine
  multiple file reads, greps, and short commands into single shell invocations.
  Bad: `sed -n '1,100p' A.py` then `sed -n '1,100p' B.py` (2 calls).
  Good: `cat A.py && echo '---' && cat B.py` (1 call).
- **Command files shared with Claude.** Action procedures live in
  `.claude/commands/*.md`. Read these files and follow their instructions the
  same way Claude does — the content is backend-agnostic.
- **Fresh reads before edits.** Before editing any file (especially DEVPLAN.md),
  read it immediately before the edit — not at the start of the iteration.
- **Shell usage.** Use CLI tools directly for builds, tests, git operations,
  file discovery, and search.
- **Search tool availability.** This loop environment may not have `rg`
  installed. Before using `rg`, check availability with `command -v rg`. If it
  is absent, use portable fallbacks instead: `find` for file discovery,
  `grep -RIn` for text search, and `sed -n` for bounded file reads. Do not
  repeatedly attempt `rg` after it has failed in the same iteration.

## Action Instructions

WORKER_SPEC.md defines four allowed actions. Here is how to execute each one
in Codex. Perform **exactly one** per iteration.

### Phase Plan
**When:** No active phase for the current module.
1. Read `.claude/commands/phase-plan.md` and follow its instructions.
2. Commit with message: `phase-plan: <module>.<phase> — <summary>`.
3. Emit exit signal and stop.

### Step Execution
**When:** A phase is in progress with remaining steps.
1. Pick the next step from DEVPLAN. Do all file read/write work.
2. Run builds, tests, and git operations as needed.
3. Read `.claude/commands/step-done.md` and follow its instructions.
4. Emit exit signal and stop. Do **not** start the next step.

### Phase Review
**When:** All steps in the current phase are complete.
1. Read `.claude/commands/phase-review.md` and follow its instructions.
2. Emit exit signal and stop.

### Phase Complete
**When:** Review is done and fixes (if any) are applied.
1. Read `.claude/commands/phase-complete.md` and follow its instructions.
2. Emit exit signal and stop.

## Output Contract

End every iteration with exactly these four lines — no additional text after:

```
LOOP_SIGNAL: CONTINUE | ESCALATE
REASON: <one-line summary>
ACTION_TYPE: PHASE_PLAN | STEP | REVIEW | COMPLETE
ACTION_ID: <module.phase.step>
```

## Autonomy

When invoked in autonomous mode, execute the action and emit the exit signal
without waiting for human input. In supervised mode, surface proposed changes
for approval before committing.

See WORKER_SPEC.md §8 for full mode definitions.
