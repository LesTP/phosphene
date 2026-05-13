---
phase: MVP.4
blocked: false
state: execute
steps_remaining: 1
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
- **Focus** — Fix T2→T2 cross-link bug before T2→T3 distillation.
- **Blocked** — No.

## MVP.4: Remaining Steps

- [x] T1→T2 distillation working — 12/12 cluster summaries succeeded, 11 T2 notes produced from 200 notes
- [x] **Fix missing notes** — root cause: note ID collision (same title+timestamp → same filename). Fixed by including content in hash. Re-seeded: 3,856 T1 notes (was 1,469).
- [x] **Stage 200 notes + run preflight** — prepare for chronological distillation
- [x] **Full chronological distillation** — 3,856 T1 → 225 clusters, 2,328 promoted, 1,528 noise. 251 T2 notes + 225 assertion caches.
- [x] **Fix T2→T2 cross-links** — engine fixed; vault rebuilt and validated.
- [ ] **T2→T3 distillation** — reflect-evolve personality files
- [ ] **Run generation** — first output via Telegram
- [ ] **Verify Telegram** — check message arrives on phone

## MVP.4a: Fix T2→T2 Cross-Links (autonomous, Build)

**Problem:** `_write_tier2_cluster_notes()` (engine.py:638-641) creates an all-to-all mesh: every T2 note produced in a distillation run gets linked to every other T2 note from the same run. In incremental mode (~10 clusters per run), this is a small clique and roughly correct. In the full-corpus bootstrap (225 clusters), it produces a 225-node complete graph where every note has 224 meaningless cross-links. The ARCH spec (line 128) says "wires cross-references between **related** clusters" — the implementation skips the "related" filter.

**Current vault state:** 251 T2 .md notes. 225 have 224 T2 cross-links each (from `distill_full`), 26 have 25 each (from `distill_loop2`). T1 source links (5-16 per note) are correct and must be preserved. Cluster centroids stored in `vault/.embeddings/` (4,122 .npy files). `_cosine_similarity()` helper exists at engine.py:1707.

**Network impact:** All-to-all T2 links make density metrics flat (every node equally connected), defeat link-density decay (nothing can be forgotten), and provide no structural signal for the Attention Filter's prompt-to-structure transition.

### Step 1: Engine fix — similarity-filtered cross-links (done)

**What:** Replace lines 638-641 with centroid-similarity filtering. Add `cross_link_threshold: float = 0.45` and `max_cross_links: int = 15` to `DistillationConfig`. For each note, compute cosine similarity against all other centroids from the same run, keep only pairs above threshold, cap at top-K.

**Files:** `engine.py` (lines 638-641), `engine.py` (DistillationConfig definition — find line). Test file for cross-linking.

**Verification:** Unit test — given 5 promotions with known centroids (2 similar, 3 dissimilar), verify only the similar pair gets cross-linked. Existing tests must still pass.

**Contract change:** Adds `cross_link_threshold` and `max_cross_links` to `DistillationConfig`. Both have defaults so existing callers are unaffected. Update ARCH_distillation.md step 7 to describe the filtering.

### Step 2: Strip bad links + regenerate proper cross-links (done)

**What:** Write `tools/rebuild_t2_crosslinks.py` that:
1. Loads all T2 notes from `vault/tier2/*.md`
2. For each note, partitions `links` into T1 links (resolve to `vault/tier1/`) and T2 links (resolve to `vault/tier2/`)
3. Strips all T2→T2 links
4. Loads centroid embeddings from `vault/.embeddings/{note_id}.npy`
5. Computes pairwise cosine similarity between all T2 centroids
6. For each T2 note, adds cross-links to top-K most similar peers above threshold
7. Rewrites the .md files with corrected links

**Parameters:** `--threshold 0.45 --max-links 15` (same defaults as engine). `--dry-run` mode that prints link distribution without writing.

**Verification:**
- Dry-run first: check link count distribution (should be 0-15 per note, not 224)
- After write: verify T1 links preserved, T2 links within expected range
- Run `tools/measure_density.py` and compare before/after

### Step 3: Validate vault state (done)

**What:** Run `tools/measure_density.py` and `tools/preflight.py`. Verify:
- T2 link distribution is ~5-15 per note (not 224)
- T1 source links unchanged
- Total T2 notes unchanged (251)
- Assertion caches (.json) untouched
- All existing tests pass

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
