# Claude Worker Adapter — Phosphene

> **Contract:** Follow `WORKER_SPEC.md` for iteration lifecycle, allowed actions,
> one-action rule, escalation conditions, and output contract. This file covers
> Claude-specific mechanics only.

## Framework
From Idea to Code — governance framework for multi-session autonomous development.

## Required Reading — Every Iteration

Context loading is tiered to control cache size. Each turn re-reads the cached
prefix; smaller prefix → fewer cache-read tokens × turn count. Mirrors the
tiering in CODEX.md.

### Tier 1 — Always (mandatory, every iteration)

Auto-loaded via @-references:

- @DEVPLAN.md — current status, cold start summary, gotchas
- @WORKER_SPEC.md — backend-agnostic worker contract

### Tier 2 — Current module (mandatory for STEP / REVIEW / COMPLETE)

After determining the active module from DEVPLAN's Current Status, read the
relevant ARCH file using the lookup table below. Combine with source files
you intend to inspect or edit in the same turn when possible.

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

Do NOT load these unconditionally. Read only when the action requires them:

- `PROJECT.md` — only during Phase Plan (scope, constraints, success criteria)
- `ARCHITECTURE.md` — only during Phase Plan, or when reasoning about cross-module wiring
- `GOVERNANCE.md` — only if uncertain about process (regimes, modes, escalation rules)

### Tier 4 — Reference only (load explicitly when relevant)

- `DECISIONS.md` — read during Phase Review to verify no contract drift since prior decisions; otherwise on demand
- `DEVLOG.md` / `DEVLOG_archive.md` — read during Phase Complete (DEVLOG learning review per GOVERNANCE.md)

This file (CLAUDE.md) provides Available Modules and Project-Specific Notes
inline so non-plan iters don't need to load PROJECT or ARCHITECTURE for
high-level orientation.

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
- **Model policy:** D-5 in DECISIONS.md — single primary model during establishment phase.

## Claude-Specific Tool Rules
- **Edit tool requires fresh reads:** Before editing any file (especially DEVPLAN.md), read it immediately before the edit — not at the start of the iteration.
- **No subagent spawning for simple tasks:** Do NOT spawn Agent(Explore) subagents for simple file discovery — use `bash find` or `bash ls` instead.
- Use `bash grep` instead of the Grep tool if built-in tools have path issues.
- Use `bash find` instead of the Glob tool if paths contain special characters.

## Claude-Specific Runner Info
**Runner:** `run-iteration.sh` — runs `claude -p` per iteration, logs to `logs/loop/`.

**Slash commands:** Project commands in `.claude/commands/` — these are NOT
Skill-tool skills. To use them, read the `.md` file and follow its instructions.
Do NOT call them via the Skill tool.

| Action (from WORKER_SPEC) | Claude command file |
|---------------------------|---------------------|
| Phase Plan | `.claude/commands/phase-plan.md` |
| Step Execution | `.claude/commands/step-done.md` |
| Phase Review | `.claude/commands/phase-review.md` |
| Phase Complete | `.claude/commands/phase-complete.md` |

## Autonomy
This project supports autonomous execution. When invoked with
`autonomous: true` in the prompt, commands auto-proceed and the agent follows
`WORKER_SPEC.md`. Otherwise, commands pause for human approval.

See WORKER_SPEC.md §8 for mode definitions (autonomous vs. supervised).
