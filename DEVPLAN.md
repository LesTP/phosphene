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
- [ ] **Chronological seeding mode** — `--seed-chronological` option: sort all corpus items by publication timestamp, feed in yearly batches, run distillation + decay between batches. Items without timestamps (plain text seed files) come in last. This lets the network "grow up" chronologically — early writing shapes initial personality, later writing reinforces or challenges it. Estimated cost: ~$5-10 extra for 3-4 distillation rounds. **Delete existing vault before running** — this replaces bulk seed. Record as D-54.
- [ ] **Measure link density on seeded vault** — run `get_density_metrics()` on Pi after seed to check actual mean_link_degree with multilingual model. If <5, default crossover (3.0) may be fine. If >10, raise to 15.0. The multilingual model produces tighter similarity distributions (11.5% of pairs above 0.4 vs 37% with English-only), so density may be naturally lower. Do this before deciding crossover value.
- [ ] **Raise `density_crossover` (if needed)** — based on measured link density. Set in run.py's AttentionFilterConfig. Only raise if mean_link_degree is well above the default crossover of 3.0.
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
3. **Deploy to Pi** — run inside `claude-code` Incus container (not over SMB from Windows). See deployment checklist below.
4. **Leiden community detection** — replace agglomerative clustering. See `notebooks/CLUSTERING_AB_PLAN.md`.
5. **Tuning panel** — live parameter adjustment interface.
6. **Network visualization** — 2D UMAP projection of vault embeddings, colored by source/cluster/tier.

## Deployment Checklist (Pi / claude-code container)

The Phosphene code and seed corpus are already on the Pi via the Samba share (`/mnt/passport/shared` → bind-mounted into `claude-code` at `/home/claude/workspace`). No file copying needed — just install deps and run locally instead of over SMB.

### Prerequisites
- `claude-code` container running (Incus)
- Workspace bind-mount active at `/home/claude/workspace`
- Phosphene repo at `/home/claude/workspace/phosphene/`
- Toolkit repo at `/home/claude/workspace/toolkit/` (or wherever — path is configurable)

### Steps

```bash
# Enter container
ssh pirozhok "incus exec claude-code -- su - claude"

# 1. Install Python deps
pip install sentence-transformers croniter anthropic

# 2. Verify paths
ls /home/claude/workspace/phosphene/run.py
ls /home/claude/workspace/phosphene/seed/
ls /home/claude/workspace/toolkit/src/toolkit/

# 3. Set up .env (edit with correct TOOLKIT_SRC path)
cat > /home/claude/workspace/phosphene/.env << 'EOF'
TELEGRAM_BOT_TOKEN=<bot-token>
TELEGRAM_CHAT_ID=<chat-id>
ANTHROPIC_API_KEY=<api-key>
TOOLKIT_SRC=/home/claude/workspace/toolkit/src
EOF

# 4. Test imports
cd /home/claude/workspace/phosphene
python3 run.py --help

# 5. Clear stale vault and re-seed (local disk I/O, ~3-10 minutes)
rm -rf vault/
python3 run.py --seed-direct

# 6. First cycle (distillation + generation + Telegram, costs ~$1-3 API)
python3 run.py --once

# 7. Verify Telegram message arrived on phone

# 8. (Optional) Install as systemd service for cron loop
#    Pattern: same as codexbot.service — see pirozhok README
```

### Notes
- **Edit from Windows, run on Pi.** VS Code edits via Samba share (P: drive) are fine. Python execution must happen inside the container where files are on local disk.
- **Git sync:** Push from Windows, pull inside container. Vault and `.env` are gitignored — they stay local.
- **Model download:** First `--seed-direct` run downloads `paraphrase-multilingual-MiniLM-L12-v2` (~471MB). Cached after that.
- **Memory:** Embedding model uses ~200-500MB. Container has 12-14GB RAM — plenty of headroom.
- **Vault on NVMe:** The `/mnt/passport/` drive is the Passport SSD. Vault writes go there, not the SD card.

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
