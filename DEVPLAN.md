---
phase: MVP.4
blocked: false
state: execute
steps_remaining: 2
---

# Phosphene — Development Plan

<!-- This file is the primary state document for autonomous iteration.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses. -->

## Cold Start Summary

- **What this is** — Autonomous personality agent with hierarchical memory, attention filtering, and personality development through distillation.
- **Key constraints** — Python 3.12+. Depends on toolkit/ (sibling project, all modules complete). Obsidian-compatible markdown storage. Target: Raspberry Pi 5 (orchestration only, inference via API).
- **Gotchas** —
  - toolkit/ is an external dependency — import from it, never modify it. `run.py` resolves path via `TOOLKIT_SRC` env var or auto-detection.
  - **Cost estimation** — before any batch LLM operation, estimate cost first. Use `--seed-direct` (free) not `--seed-only` (~$35) for corpus import.
  - **Run on Pi** — do NOT run from Windows over SMB. SSH into Pi, run locally.
  - **No inline SSH commands** — write script files, push and execute. PowerShell quoting is broken for SSH→Python.
  - **Integration checks before expensive runs** — validate interface chain with dry-run probe scripts (e.g., `tools/check_clustering_compat.py`).
  - **Preflight before LLM spend** — run `tools/preflight.py` before any operation that costs money. Checks vault sanity (duplicates, timestamps), API, clustering, interface compat. Fix all NO-GO items first.
  - **Small-batch test first** — before any full-corpus LLM operation, test on 5-10 items and verify output. Only scale up after small test passes.
  - **NTFS atomic rename** — `os.rename()` fails on NTFS-3G shares. Use `find -delete` to clear vault.

## Current Status

- **Phase** — MVP.4: Bootstrap and first run
- **Focus** — Chronological seed + first distillation + first Telegram output
- **Blocked** — No. Chronological seed ready to launch on Pi.

## MVP.4: Remaining Steps

- [ ] **Run `--seed-chronological`** — 200-note batches, distillation between each. Launch overnight on Pi.
- [ ] **Run `--once`** — first generation + Telegram delivery (after seed completes)
- [ ] **Verify Telegram** — check message arrives on phone (manual)

## Next Priorities (post-MVP.4)

1. **Wire inbound message handler** — `#` prefix → ingestion, no prefix → conversation. Trust tiers: owner (full importance), trusted (0.2-0.3), untrusted (0.05, fast decay). Open decision: sync vs async response.
2. **Leiden community detection** — replace HDBSCAN. See `notebooks/CLUSTERING_AB_PLAN.md`.
3. **Tuning panel** — live parameter adjustment interface.
4. **Network visualization** — `tools/visualize_network.py` ready, run after seed.

## Deferred Work

- Feedback Collector Phase 7.2 (delayed engagement checks)
- Module 8: Explorer (link-following with pre-fetch scoring)
- Module 9: Full Orchestrator (lateral freedom, tension-responsive scheduling)

## Discussion Items

- **`tools/preflight.py`** — should it run automatically before expensive operations?
- **Corpus exploration protocol** — write a `tools/explore_corpus.py` (or notebook) that runs on any new seed corpus before seeding and returns tuning parameter suggestions. Steps: (1) measure language distribution (% Cyrillic, Latin, mixed), (2) terrain analysis (pairwise similarity stats), (3) test embedding model candidates on cross-lingual gap, (4) run UMAP + HDBSCAN at multiple `reduce_dims` values, (5) compute cluster coherences at multiple thresholds, (6) test 1-2 cluster summaries on candidate LLM models for refusal, (7) estimate cost for full distillation. Output: recommended `.env` parameter values. This automates everything we manually discovered over this session.

## Key References

- `DECISIONS.md` — D-1 through D-53 (embedding model, switchability, etc.)
- `notebooks/NETWORK_OPTIMUMS.md` — parameter study results
- `notebooks/TUNING_GUIDE.md` — corpus-to-personality tuning guide and findings
- `notebooks/CLUSTERING_AB_PLAN.md` — Leiden vs HDBSCAN comparison plan

## Operations Quick Reference

```bash
# Clear vault and seed (on Pi)
ssh pirozhok
cd /mnt/passport/shared/phosphene
find vault -type f -delete; find vault -mindepth 1 -type d -delete
nohup ~/phosphene-venv/bin/python3 -u run.py --seed-chronological > logs/seed.log 2>&1 &
tail -f logs/seed.log

# Check progress
ssh pirozhok "tail -20 /mnt/passport/shared/phosphene/logs/seed.log"

# Run one cycle
ssh pirozhok "cd /mnt/passport/shared/phosphene && ~/phosphene-venv/bin/python3 -u run.py --once"

# Visualize network
ssh pirozhok "cd /mnt/passport/shared/phosphene && ~/phosphene-venv/bin/python3 tools/visualize_network.py"

# Check vault state
ssh pirozhok "cd /mnt/passport/shared/phosphene && ~/phosphene-venv/bin/python3 tools/measure_density.py"
```

## Completed Modules

7 modules complete (616 tests, 98% coverage). MVP Orchestrator phases 1-3 complete. See `DEVLOG_archive.md` for history.
