---
phase: MVP.4
blocked: false
state: execute
steps_remaining: 3
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

- **Module** — MVP Orchestrator
- **Phase** — MVP.4: Bootstrap and first run
- **Focus** — Write the bootstrap script that wires all modules and runs the system.
- **Blocked/Broken** — See frontmatter gate.
- **Contract** — ARCH_orchestrator_mvp.md

## MVP Orchestrator

*The MVP Orchestrator wires Modules 1–6 into a running system. It is the minimum needed to satisfy PROJECT.md MVP Definition: cron-triggered ingestion, distillation, generation, and decay — no lateral freedom, no tension-responsive scheduling, no ambient context, no feedback loop. See ARCH_orchestrator_mvp.md for the full contract.*

### Phase MVP.1: Contract and cron loop

Complete. See `DEVLOG_archive.md`.

### Phase MVP.2: Activation wiring

Complete. See `DEVLOG_archive.md`.

### Phase MVP.3: Integration hardening

Complete. See `DEVLOG.md`.

### Phase MVP.4: Bootstrap and first run

Write the entry-point script (`run.py`) that instantiates all 6 modules from real configs, reads secrets from `.env`, and starts the orchestrator. This is pure wiring — no new module code.

**Work regime:** Build (testable — the script either starts and processes a cycle, or it doesn't).

**Prerequisites already met:**
- All 6 modules implemented and tested (616 tests, 98% coverage)
- MVP Orchestrator complete with error isolation, logging, restart recovery
- Corpus adapters for LJ (ljsm), Blogspot (atom), and plain text
- Embedding model selected: `paraphrase-multilingual-MiniLM-L12-v2` (D-52)
- Telegram bot configured (`.env` with token + chat ID)
- Anthropic API key in `.env`

**Steps:**

1. ~~**Create `run.py`** — DONE. Entry point imports successfully and `--help` works.~~

2. **Test seed-only mode** — Run `python run.py --seed-only` against the real corpus archives:
   - Verify adapters find and parse the HTML/atom files
   - Verify embedding model loads and produces vectors
   - Verify notes are written to `./vault/` as Obsidian-compatible markdown
   - Count ingested notes vs expected (~3500 raw, filtered by attention filter)
   - Test: vault directory contains tier-1 notes with frontmatter

3. **Test single activation cycle** — Run `python run.py --once`:
   - Ingestion: poll adapters (should be no-op after seed since markers are set)
   - Distillation: check gates, run T1→T2 if volume threshold met
   - Generation: load personality context, generate one output
   - Decay: run decay cycle
   - Test: activation log written, no crashes, generation output is non-empty

4. **Test Telegram delivery** — Run generation and verify output reaches Telegram:
   - Gateway sends generated text to configured chat ID
   - Test: message received on Telegram (manual verification — ESCALATE for human check)

**Note for autonomous loop:** Steps 1–3 are Build work, fully automatable. Step 4 requires manual verification of the Telegram message — ESCALATE at that point for human sign-off.

## Immediate Todos

*From network optimums analysis session (May 2026). Pick-one-next.*

1. **Launch MVP** — Seed corpus import, configure adapters (Telegram, RSS), deploy as systemd service, validate 48hr unattended operation. The system can start churning now.
   - **Bulk seed**: LJ (ljsm, `format: "ljsm"`), Blogspot (2 atom files), seed text files. ~3500 chunks total.
   - **Embedding model**: `paraphrase-multilingual-MiniLM-L12-v2` (D-52).
   - **Model migration** (D-53): If model changes later, re-embed all living notes before scoring. Steps: (1) update `EmbeddingConfig.model` in orchestrator config, (2) iterate all notes with stored embeddings, (3) re-embed with new model, (4) update stored vectors, (5) clear embedding cache. Scriptable, ~minutes on CPU for <5K notes. Invalidates similarity-based metadata (link counts, unresolvedness) — run a full decay + recompute cycle after migration.
2. **Leiden community detection (with A/B vs alternatives)** — Replace agglomerative clustering with Leiden (strict improvement over Louvain: same UX, no disconnected-community pathology, often higher modularity). Plan A/B against HDBSCAN-on-embeddings as a paradigm contrast (graph-modularity vs density-on-vectors). Prototype in simulation first. See `notebooks/CLUSTERING_AB_PLAN.md` and `notebooks/NETWORK_OPTIMUMS.md`.
3. ~~**Multilingual embedding model**~~ — DONE (D-52). Using `paraphrase-multilingual-MiniLM-L12-v2`. Cross-lingual gap reduced 80%. Model switchable per D-53.
4. **Tuning panel** — Parameter control interface ("cobwebbed panel with staticky knobs") for live adjustment of sim_threshold, retention days, ingestion rate, prune cycle, unresolvedness weights. Observe network behavior changes in real time.

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

616 tests passing as of Phase MVP.3 completion.

<!--
HISTORY — Do not read past this marker.
Completed phase history below.
-->
