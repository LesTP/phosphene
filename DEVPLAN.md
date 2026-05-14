---
phase: MVP.4b
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

- **Phase** — MVP.4b: Batch reflection + T3 bootstrap creation
- **Focus** — Make T2→T3 work at any T2 volume and with zero existing T3 files.
- **Blocked** — No.

## MVP.4: Remaining Steps

- [x] T1→T2 distillation working — 12/12 cluster summaries succeeded, 11 T2 notes produced from 200 notes
- [x] **Fix missing notes** — root cause: note ID collision (same title+timestamp → same filename). Fixed by including content in hash. Re-seeded: 3,856 T1 notes (was 1,469).
- [x] **Stage 200 notes + run preflight** — prepare for chronological distillation
- [x] **Full chronological distillation** — 3,856 T1 → 225 clusters, 2,328 promoted, 1,528 noise. 251 T2 notes + 225 assertion caches.
- [x] **Fix T2→T2 cross-links** — engine fixed; vault rebuilt and validated. See MVP.4a.
- [ ] **T2→T3 distillation** — see MVP.4b below
- [ ] **Run generation** — first output via Telegram
- [ ] **Verify Telegram** — check message arrives on phone

## MVP.4b: Batch Reflection + T3 Bootstrap (autonomous, Build)

**Problem:** Two blockers prevent T2→T3 from running on the live vault:
1. **Context overflow** — `_prepare_tier2_evolution_input()` reads ALL T2 notes. With 251 notes, the reflection prompt is ~202K tokens — exceeds practical context budget.
2. **No bootstrap path** — `_propose_personality_evolution()` only proposes supersession/unchanged for existing T3 files. With 0 T3 files, the evolution step has nothing to evolve.

**Design decision:** Option 1+2b from `DISCUSS_T2_TO_T3_BOOTSTRAP.md`. Batch reflection becomes the **permanent** T2→T3 reflection path (not bootstrap-specific code). Bootstrap creation fires only when T3 is empty. In steady state with 20 T2 notes, there's one batch — identical behavior. At 251 or 500+, it batches naturally.

**Current vault state:** 3,856 T1, 251 T2 (.md + .json caches), 0 T3. T2 cross-links rebuilt with similarity filtering (1-15 links per note). Embeddings stored in `vault/.embeddings/` (4,122 .npy files). 621 tests pass.

### Step 1: Batch reflection — chunk T2 input for `_reflect_tier2_patterns()` (done)

**What:** Add `t2_reflection_batch_size: int = 30` to `DistillationConfig`. Modify `_reflect_tier2_patterns()` to:
1. Sort T2 notes by importance (descending), breaking ties by unresolvedness
2. Split into chunks of `t2_reflection_batch_size`
3. Call the existing reflection LLM prompt once per batch
4. Merge all `ReflectionInsight` lists into a single list before returning

When T2 count ≤ batch size, behavior is identical to current (single batch = single call).

**Files:** `engine.py` — `DistillationConfig`, `_reflect_tier2_patterns()`, `_build_reflection_audit_artifact()`. Test file for batched reflection.

**Verification:** Unit test with FakeLLM: given 60 T2 notes at batch_size=30, verify two reflection calls are made and insights from both batches appear in the merged result. Single-batch case (20 notes at batch_size=30) should produce identical behavior to current. Existing T2→T3 tests must still pass.

**Contract change:** Adds `t2_reflection_batch_size` to `DistillationConfig` with default. Update ARCH_distillation.md step 2 of `distill_t2_to_t3` to describe batching.

### Step 2: Bootstrap creation — initial T3 files from merged insights (done)

**What:** Modify `_propose_personality_evolution()` to detect `len(personality_files) == 0`. When empty:
1. Send merged `ReflectionInsight` list to LLM with a bootstrap-specific prompt: "Given these synthesized patterns from a personal writing corpus, create 3-7 initial personality files. Each should capture a distinct dimension: core orientations, recurring tensions, aesthetic preferences, intellectual preoccupations, social modes, etc. Be specific to this corpus — not generic."
2. Parse the LLM response into `SupersessionRecord`-compatible writes (new notes, no supersession source)
3. Store each personality file via `memory_store.store_note(tier=3, ...)` with `version_count=1`

When personality files exist, use the existing supersession/unchanged path unchanged.

**Files:** `engine.py` — `_propose_personality_evolution()`, `_build_evolution_proposal_artifact()`. Possibly a new `_build_bootstrap_proposal_artifact()`. Test file for bootstrap path.

**Verification:** Unit test with FakeLLM: given 5 reflection insights and 0 T3 files, verify bootstrap prompt is sent and personality files are created. Given 5 insights and 2 existing T3 files, verify normal supersession path is used (regression). Existing T2→T3 tests must still pass.

**Contract change:** None to public API — `distill_t2_to_t3()` signature unchanged. Internal behavior change: creates T3 files when none exist. Update ARCH_distillation.md evolution step 1-2 to document the bootstrap branch.

### Step 3: Integration test — full T2→T3 with FakeLLM

**What:** End-to-end test: seed a MemoryStore with 60 T2 notes (no T3), run `distill_t2_to_t3()` with FakeLLM, verify:
- Reflection ran in 2 batches (batch_size=30)
- Bootstrap creation produced T3 personality files
- Personality files are stored in vault/tier3/
- `get_personality_context()` returns the new files
- A second `distill_t2_to_t3()` call uses the normal supersession path (not bootstrap)

**Files:** Test file in `tests/distillation/`.

**Verification:** All assertions in the test. Full test suite passes.

### Step 4: Run T2→T3 on live vault + validate

**What:** Run `distill_t2_to_t3()` on the live vault (251 T2 notes, 0 T3) via `run.py` or a one-off script. **Preflight first.** Estimate cost before running (~$2-5 for 8-9 reflection batches + 1 bootstrap evolution call).

**Verification:**
- T3 personality files created in vault/tier3/
- Content is specific to the corpus (not generic)
- `tools/measure_density.py` shows T3 notes
- Network visualization shows T3 (gold squares) in the map

**Note:** This step involves real LLM spend. Run on the Pi, not from Windows. Use Sonnet 4 (not 4.5) for bilingual content compatibility.

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
