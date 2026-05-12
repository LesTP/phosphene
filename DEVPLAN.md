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
  - **Run from local disk** — do NOT run the system from a network share (P: drive). Network drops kill long-running processes, SMB file I/O is 10× slower. Run on the Pi via SSH.
  - **No inline SSH commands** — PowerShell→SSH→Python quoting is broken. Always write a script file (e.g., `tools/script.py`), then `ssh pirozhok "python3 /path/script.py"`. Never use `python -c` through SSH.
  - **Integration checks before expensive runs** — before launching distillation, seeding, or any multi-hour operation, write a dry-run probe script that validates the full interface chain (config types, method signatures, enum values) against the actual toolkit code. Do not rely on "try and see" for integration bugs.
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
- [x] Deploy to Pi — venv at `~/phosphene-venv`, toolkit copied to `/mnt/passport/shared/toolkit/`, .env with TOOLKIT_SRC configured
- [x] Seed Facebook corpus — FB adapter added to `run.py` config
- [x] Chronological seeding mode — `--seed-chronological` implemented with yearly batches + distillation between
- [x] Measure link density — all zeros after direct seed, Phase 2 naturally inactive, density_crossover NOT NEEDED
- [ ] **Chronological seed IN PROGRESS (attempt 5)** — running on Pi. All interface fixes applied, per-cluster error tolerance, prompt size cap.
- [ ] **Run `--once`** — first generation + Telegram delivery (after seed completes)
- [ ] **Verify Telegram** — check message arrives on phone (manual)

### Bugs found and fixed during first-run attempts
- Ingestion via `--seed-only` cost $4 — LLM-scores every item (use `--seed-direct`)
- `_RaptorClusterConfig` missing `min_cluster_size` — toolkit interface mismatch
- `_RaptorClusterConfig.strategy` uppercase `"RAPTOR"` — toolkit enum expects lowercase `"raptor"`
- `_RaptorClusterConfig.strategy` plain string — toolkit accesses `.value` (enum compat). Added `_StrategyStr`
- `_RaptorClusterConfig.metric` defaulted to `"cosine"` — HDBSCAN expects `"euclidean"`
- Gateway `allowed_chat_ids` kwarg not in toolkit `TelegramClient`
- LLM response wrapped in markdown fences — added fence stripping to JSON parser
- LJ adapter path wrong (`seed/livejournal` → `seed/LJ Backup/ljsm/lestp`)
- Network share kills long-running processes — must run on Pi via SSH
- RAPTOR summary prompt sent all cluster members (227K tokens > 200K limit) — capped at 50 obs × 2000 chars
- Anthropic API empty response — added retry + per-cluster tolerance with placeholder summaries
- NTFS-3G `rm -rf` fails — use `find -delete` pattern
- Toolkit not on Samba share — copied to `/mnt/passport/shared/toolkit/`
- Venv can't run on NTFS (no exec bits) — created on ext4 at `~/phosphene-venv`
- `run.py` toolkit path hardcoded to Windows — added cross-platform resolution

### Governance improvements
- `/phase-complete` step 5: integration check for cross-module types
- DEVPLAN gotchas: no inline SSH commands, integration checks before expensive runs
- `tools/check_clustering_compat.py` — dry-run interface validation
- `tools/measure_density.py` — vault density metrics
- Discussion: `tools/preflight.py` for full module graph validation

## Post-MVP.4 (next priorities)

1. **Wire inbound message handler** — `#` prefix → ingestion (file away, ack with 📌), no prefix → conversation (generate personality-flavored reply). Open decision: sync vs async response.
   - **Trust tiers for input:** Owner (your chat ID) = full importance, stored as T1, enters distillation. Trusted (manually approved) = lower importance (0.2-0.3), stored but unlikely to form clusters. Untrusted (everyone else) = minimal importance (0.05), stored briefly for conversation memory but decays fast (7d) and never reaches distillation. Uses existing `importance` and `attractor_relevance` fields — no new mechanisms needed.
   - **Conversation memory:** All tiers get stored as T1 with `source=conversation:{chat_id}`, so the bot remembers previous exchanges per person. For untrusted users, this memory is ephemeral (fast decay) but provides continuity within a few days.
   - **Trust promotion:** `/trust @username` raises stored note importance. Could be automatic over time for consistently benign interlocutors. Post-MVP feature.
2. **Inbound chat ID filter** — determines trust tier. Owner chat ID = owner tier. Others start as untrusted.
3. **Deploy to Pi** — DONE. See deployment checklist below (already executed).
4. **Leiden community detection** — replace agglomerative clustering. See `notebooks/CLUSTERING_AB_PLAN.md`.
5. **Tuning panel** — live parameter adjustment interface.
6. **Network visualization** — 2D UMAP projection of vault embeddings, colored by source/cluster/tier.

## Deployment Checklist (Pi / claude-code container)

The Phosphene code and seed corpus are already on the Pi via the Samba share (`/mnt/passport/shared` → bind-mounted into `claude-code` at `/home/claude/workspace`). No file copying needed — just install deps and run locally instead of over SMB.

### Prerequisites
- `claude-code` container running (Incus)
- Workspace bind-mount active at `/home/claude/workspace`
- Phosphene repo at `/home/claude/workspace/phosphene/`
- Toolkit repo at `/home/claude/workspace/toolkit/` — **not on the share by default.** Clone or copy from Windows:
  ```bash
  # Option A: clone from GitHub
  cd /mnt/passport/shared && git clone https://github.com/LesTP/toolkit.git
  # Option B: copy from Windows
  scp -r "c:\Users\myeluashvili\claude-code-workspace\projects\toolkit" pirozhok:/mnt/passport/shared/
  ```

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

## Discussion Items

- **`tools/preflight.py`** — Runtime integration check script. Imports every module with real dependencies (not fakes), constructs minimal configs, runs trivial operations. Catches type/interface mismatches before expensive runs. Questions: should it run automatically before `--once`/`--seed-chronological`? Should it be a separate command or built into run.py as a `--preflight` flag?

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
