# Claude Worker Adapter — Phosphene

> **Contract:** Follow `WORKER_SPEC.md` for iteration lifecycle, allowed actions,
> one-action rule, escalation conditions, and output contract. This file covers
> Claude-specific mechanics only.

## Framework
From Idea to Code — governance framework for multi-session autonomous development.

## Always Loaded
- @PROJECT.md — scope, constraints, success criteria
- @ARCHITECTURE.md — component map, layer contracts, implementation sequence
- @GOVERNANCE.md — development process reference
- @DEVPLAN.md — current status, cold start summary, gotchas
- @WORKER_SPEC.md — backend-agnostic worker contract

## Load for Current Module
Determine the active track and module from DEVPLAN's Current Status section.
For layer contracts and module dependencies, see ARCHITECTURE.md.

| Module | ARCH file |
|--------|----------|
| Memory Store | `ARCH_memory_store.md` |
| Seeding | `ARCH_seeding.md` |
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
- Module 2: Seeding — corpus-to-personality pipeline (populates Memory Store)

**Track B — Core Loop (content in):**
- Module 3: Attention Filter — personality-driven content selection
- Module 4: Source Ingestion — adapters for content sources (including human-share)

**Track C — Core Loop (content out):**
- Module 5: Gateway — multi-platform message bus
- Module 6: Generator + Output Router — content generation and delivery

**Track D — Development (personality evolves):**
- Module 7: Distillation — tier promotion, RAPTOR clustering, reflect-evolve

**Track E — Feedback and Depth:**
- Module 8: Feedback Collector — signal normalization, silence detection
- Module 9: Explorer — autonomous link-following

**Track F — Orchestration (wires everything):**
- Module 10: Orchestrator — activation lifecycle, scheduling, lateral freedom

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
