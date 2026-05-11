---
phase: MVP.4
blocked: true
state: execute
steps_remaining: 2
---

# Phosphene — Development Plan

<!-- This file is the primary state document for autonomous iteration.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses. -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step. -->

- **What this is** — Autonomous personality agent with hierarchical memory, attention filtering, and personality development through distillation.
- **Key constraints** — Python 3.12+. Depends on toolkit/ (sibling project, all modules complete). Obsidian-compatible markdown storage. LLM API costs managed via subscription rotation and model tier system. Target: Raspberry Pi 5 (orchestration only, inference via API).
- **Gotchas** —
  - toolkit/ is an external dependency — import from it, never modify it. `run.py` adds toolkit src to sys.path via `TOOLKIT_SRC` env var or hardcoded default.
  - Memory Store uses consumer-provided embeddings (no toolkit/embedding dependency in the store itself)
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - **Cost estimation** — before any batch operation that touches the LLM, estimate cost first: items × avg tokens × price/token. Use `--seed-direct` for corpus import (local embeddings only, no LLM). Never use `--seed-only` for large corpora.
  - **Run from local disk** — do NOT run the system from a network share (P: drive). Network drops kill long-running processes, SMB file I/O is 10× slower. Copy project + vault to local disk or deploy to RPi5.
  - **NTFS atomic rename** — `os.rename()` for marker files fails on network shares. Needs fix before production.

## Current Status

- **Module** — MVP Orchestrator
- **Phase** — MVP.4: Bootstrap and first run
- **Focus** — First distillation + generation cycle
- **Blocked** — Must move to local disk or RPi5 before continuing. Network share is not viable for runtime.
- **Contract** — ARCH_orchestrator_mvp.md

## MVP.4: Bootstrap and first run

### Completed
- [x] `run.py` entry point — wires all 6 modules, reads `.env`, CLI modes
- [x] `--seed-direct` mode — bypasses LLM attention filter, embeds locally, writes T1 notes directly
- [x] Bulk seed — 3,105 T1 notes in `vault/tier1/` from LJ (2002-2009), Blogspot (2 feeds), seed text files
- [x] JSON fence stripping — attention filter handles markdown-wrapped LLM responses
- [x] Gateway `allowed_chat_ids` fix — removed unsupported toolkit kwarg
- [x] Content cleaning in seed-direct — strips track listings, share links, bitrate lines
- [x] `_RaptorClusterConfig` fix — added `min_cluster_size` and other fields to match toolkit `ClusterConfig`
- [x] Facebook adapter — `CorpusFacebookAdapter` parses FB HTML data export (467 posts, not yet seeded)

### Remaining
- [ ] **Move to local disk or RPi5** — copy project, vault, seed, toolkit to local filesystem
- [ ] **Seed Facebook corpus** — add FB adapter to `run.py`, run `--seed-direct` (appends, no re-seed needed)
- [ ] **Run `--once`** — first distillation (T1→T2 clustering) + generation + Telegram delivery
- [ ] **Verify Telegram** — check message arrives on phone (manual)
- [ ] **Raise `density_crossover`** — set to 10-15 for establishment phase. Current value (3.0) activates Phase 2 immediately on the dense seeded vault, using artifact structure as if it were mature. Lower back to 3.0 after 30-60 days.

### Bugs found during first-run attempts
- Ingestion via `--seed-only` cost $4 before we realized it LLM-scores every item
- `_RaptorClusterConfig` missing `min_cluster_size` (toolkit interface mismatch) — fixed
- Gateway `allowed_chat_ids` kwarg not in toolkit `TelegramClient` — fixed
- LLM response wrapped in markdown fences, not raw JSON — fixed
- LJ adapter path wrong (`seed/livejournal` vs actual `seed/LJ Backup/ljsm/lestp`) — fixed
- Network share kills long-running processes — must run locally

## Post-MVP.4 (next priorities)

1. **Wire inbound message handler** — `#` prefix → ingestion (file away, ack with 📌), no prefix → conversation (generate personality-flavored reply, store user message as T1). Open decision: sync vs async response.
2. **Inbound chat ID filter** — filter messages by chat ID at Phosphene gateway level.
3. **Deploy to RPi5** — clone repos, install deps, copy `.env` + vault, configure paths.
4. **Leiden community detection** — replace agglomerative clustering. See `notebooks/CLUSTERING_AB_PLAN.md`.
5. **Tuning panel** — live parameter adjustment interface.
6. **Network visualization** — 2D UMAP projection of vault embeddings, colored by source/cluster/tier.

## Deferred Work

### Feedback Collector Phase 7.2 (post-MVP)
Delayed engagement checks and retention hardening.

### Module 8: Explorer (post-MVP)
Link-following with pre-fetch scoring.

### Full Orchestrator — Module 9 (post-MVP)
Lateral freedom, tension-responsive scheduling, ambient context, budget tracking.

## Key Decisions (recent)

- **D-52**: Use `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, 50+ languages). Cross-lingual gap reduced 80%.
- **D-53**: Embedding model is switchable — re-embed living notes on model change.
- See `DECISIONS.md` for full log (D-1 through D-53).
- See `notebooks/NETWORK_OPTIMUMS.md` for parameter study results.

## Completed Modules (summary)

7 modules complete (616 tests, 98% coverage). Memory Store, Attention Filter, Source Ingestion, Gateway, Generator, Distillation, Feedback Collector (Phase 7.1). MVP Orchestrator phases 1-3 complete.
