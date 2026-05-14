---
phase: MVP.4d
blocked: false
state: execute
steps_remaining: 3
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
  - **LLM ID hallucination** — LLMs prefer shorter IDs when long slugs and short numeric IDs coexist in prompts. Remove competing ID fields from LLM payloads, or use synthetic short IDs with a mapping.

## Current Status

- **Phase** — MVP.4d: Cached index for fast MemoryStore startup
- **Focus** — Eliminate 15+ min cold-start index rebuild. Make `run.py --once` usable on Pi.
- **Blocked** — No.

## MVP.4: Remaining Steps

- [x] T1→T2 distillation — 3,856 T1 → 251 T2 notes + 225 assertion caches
- [x] Fix T2→T2 cross-links — similarity-filtered. See MVP.4a.
- [x] T2→T3 distillation — 7 personality files bootstrapped and evolved. See MVP.4b.
- [x] Generation output persistence — vault/outputs/. See MVP.4c.
- [x] First generation + Telegram delivery — verified via lean script.
- [ ] **Cached index** — see MVP.4d below
- [ ] **Verify `run.py --once`** — should complete in <30s with cached index

## MVP.4d: Cached Index for Fast MemoryStore Startup (autonomous, Build)

**Problem:** `_rebuild_index()` reads and YAML-parses every `.md` file in the vault on every MemoryStore construction. With 4,107 notes on the Pi's USB drive, this takes 15+ minutes — making `run.py --once` unusable and cold starts painfully slow.

**Solution:** Write a JSON sidecar cache (`vault/.index_cache.json`) after index rebuild. On next startup, load from cache if it's newer than the newest vault file. The MemoryStore is the only writer, so the cache stays in sync automatically. Add `--rebuild-index` flag for manual invalidation.

**Cache contents per note:** `note_id`, `tier`, `path`, `created_at`, `updated_at`, `supersedes`, `links`, `tags`, `importance`, `unresolvedness`, `cluster_group`, `source`, `link_count`, `decay_deadline`. No content or embeddings — those are loaded on demand from the actual files.

### Step 1: Cache write — persist index after rebuild

**What:** After `_rebuild_index()` completes, serialize the index entries to `vault/.index_cache.json`. Use atomic write (temp file + rename). Include a version number and timestamp.

**Files:** `memory_store/store.py` — `_rebuild_index()`, new `_write_index_cache()`, new `_read_index_cache()`.

**Verification:** Unit test: build a MemoryStore, verify `.index_cache.json` exists, verify it contains all note IDs. Existing tests must pass.

### Step 2: Cache read — load index from cache on startup

**What:** In `_rebuild_index()`, check if `vault/.index_cache.json` exists and is valid:
1. Cache exists AND cache version matches current code
2. Cache timestamp is newer than the newest `.md` file modification time across all tiers
3. If both pass: load from cache (single file read + JSON parse) instead of scanning
4. If either fails: fall back to full scan, then write updated cache

Add `MemoryStoreConfig.skip_cache: bool = False` for tests that need guaranteed fresh index.

**Files:** `memory_store/store.py` — `_rebuild_index()`, `MemoryStoreConfig`.

**Verification:** Unit test: build MemoryStore (full scan), verify cache written. Construct second MemoryStore, verify it loads from cache (mock/spy on file reads to confirm no `.md` parsing). Modify a vault file, construct third MemoryStore, verify it falls back to full scan and updates cache. Existing tests must pass.

### Step 3: Validate on Pi

**What:** Run `run.py --once` on the Pi. First run builds cache (still 15 min). Second run should complete in <30 seconds.

**Verification:**
- First run: cache file created at `vault/.index_cache.json`
- Second run: startup in <30s, generation + Telegram delivery works
- `tools/measure_density.py` produces same results with and without cache

## MVP.4c: Generation Output Persistence — Complete

Outputs saved to `vault/outputs/` as markdown with frontmatter. Not in distillation loop. First generation delivered to Telegram. Superseded T3 files filtered in lean script. See DEVLOG.

## MVP.4b: Batch Reflection + T3 Bootstrap — Complete

Batched T2 reflection (30 notes per batch) + bootstrap T3 creation. 251 T2 patterns → 51 insights → 7 personality files created and evolved. See DEVLOG.

## MVP.4a: Fix T2→T2 Cross-Links — Complete

Engine fixed (similarity-filtered cross-links), vault rebuilt (51K bad links stripped, 3.5K proper links added), validated (621 tests). See DEVLOG.

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
- **T2→T3 preflight section** — current preflight only checks T1→T2 readiness. Needs: T2 count vs context budget, batched reflection batch count estimate, T2 embedding availability, cost estimate for T2→T3 (different from T1→T2), bootstrap path detection (0 T3 files).
- **Corpus exploration protocol** — write a `tools/explore_corpus.py` (or notebook) that runs on any new seed corpus before seeding and returns tuning parameter suggestions. Steps: (1) measure language distribution (% Cyrillic, Latin, mixed), (2) terrain analysis (pairwise similarity stats), (3) test embedding model candidates on cross-lingual gap, (4) run UMAP + HDBSCAN at multiple `reduce_dims` values, (5) compute cluster coherences at multiple thresholds, (6) test 1-2 cluster summaries on candidate LLM models for refusal, (7) estimate cost for full distillation. Output: recommended `.env` parameter values. This automates everything we manually discovered over this session. See `DESIGN_BATCH_SEEDING.md` for full design.

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
