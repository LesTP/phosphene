# Design: Batch Seeding Pipeline & Corpus Tuning

**Date:** 2026-05-14
**Context:** Post-MVP.4b. The system has completed initial corpus seeding (LJ archive → 3,856 T1 → 251 T2 → T3 in progress). This document captures the design for (1) future batch seeding that's less painful than the current manual process, and (2) an automated tuning pipeline that analyzes a corpus and suggests parameters before seeding.
**Status:** Design discussion. Not yet scheduled. Pick up after MVP.4 completes.

---

## Part 1: Normal Operation vs Batch Loading

### How the System Works in Steady State

Each piece of content goes through the full pipeline:

```
New content → Attention Filter (importance/friction scoring) → T1 storage
              ↓ (every ~20 notes)
              T1→T2 distillation (small clusters, cross-links)
              ↓ (continuously)
              Decay (low-link notes lose importance, prune)
              ↓ (every ~30 days)
              T2→T3 evolution (personality nudges)
```

Critical properties:
- **Content is filtered** — attention filter rejects noise and scores importance before anything enters memory
- **Structure builds incrementally** — each T1→T2 cycle clusters a few new notes against existing patterns
- **Decay keeps the network lean** — unlinked notes fade; linked notes persist
- **Personality evolves gradually** — T3 files gain inertia through version_count

### What Batch Loading Currently Breaks

| Property | Normal | Current Batch |
|----------|--------|---------------|
| Attention filtering | Yes — scores every note | **Bypassed** — everything enters at importance 0.5 |
| Decay between ingestions | Continuous | **None** — all notes survive |
| Distillation scope | ~20 notes per cycle | 200 per batch (improved, but still large) |
| T2→T3 frequency | Monthly | Once at the end (batched, but still one-shot) |
| Cross-links | Small per-run cliques | Fixed (similarity-filtered), but no inter-batch linking during seed |

### Problems Encountered During First Seed (LJ Archive)

1. Note ID collisions (same title+timestamp → silent overwrites) — fixed
2. LLM model refusals on bilingual content (Sonnet 4.5 refuses, Sonnet 4 works) — worked around
3. All-to-all T2 cross-links at bootstrap scale — fixed with similarity filtering
4. T2→T3 context overflow (251 T2 notes = ~202K tokens) — fixed with batched reflection (MVP.4b)
5. No T3 bootstrap path (evolution assumes existing T3) — fixed with bootstrap creation (MVP.4b)
6. SD card full on Pi (venv + pip cache + CUDA packages) — cleaned up

All symptoms of the same root cause: **pipeline designed for incremental drip-feed, not batch ingestion**.

---

## Part 2: Seeding Strategies

### Strategy A: "Enhanced Current" — Fast Seed (First Corpus)

The `--seed-chronological` approach with all fixes applied:
1. Sort chronologically, 200-note batches
2. T1→T2 distillation between batches (similarity-filtered cross-links)
3. Batched T2→T3 at the end

**Cost:** ~$5-10 per full corpus
**Quality:** Good T2 patterns, but flat T1 importance (everything is 0.5), no decay, no filtering
**Use case:** First corpus seed when no personality exists yet (can't filter without personality)
**Status:** This is what we're doing now. Works after MVP.4 fixes.

### Strategy B: "Simulated Life" — Full Pipeline Per Batch

Run the entire pipeline for each batch: attention filter scoring → T1 storage → distillation → decay → periodic T2→T3.

**Cost:** ~$35-50 for 3,856 notes (attention filter is expensive — ~$0.01/note LLM call)
**Quality:** Closest to natural operation over years
**Use case:** Probably not worth the cost for initial seed. Better for a second corpus after personality exists.

### Strategy C: "Epoch Training" — Multiple Passes (Recommended for Quality)

Inspired by ML training — multiple passes, each refining the previous:

**Pass 1 — Rough seed (what we do now):**
- `--seed-direct` → all content enters T1 unfiltered
- Chronological T1→T2 distillation → produces clusters
- Batched T2→T3 bootstrap → creates initial personality files
- **Result:** Working personality, but noisy T1 layer

**Pass 2 — Filtered re-evaluation:**
- Personality files now exist → run attention filter retroactively on all T1 notes
- Update importance/friction/relevance scores
- Run decay — notes the personality finds unimportant lose links and prune
- Re-distill T1→T2 with the filtered, pruned network
- **Result:** T1 layer reflects what the personality actually cares about; junk pruned; T2 patterns sharper

**Pass 3 — Stabilization:**
- T2→T3 evolution on the filtered/pruned network
- Personality files now reflect genuine selection, not raw corpus dump
- Run decay again
- **Result:** Network has gone through complete seed → filter → prune → distill → evolve cycle

Each pass is cheaper than the last (fewer notes survive). Total ~$15-20 for three passes.

**This compresses what would happen naturally over months of operation into hours.**

### Strategy D: "Additive Batch" — For Adding a Second Corpus (e.g., Twitter)

When personality already exists, adding a new corpus is architecturally easier:

1. **Attention filter can work** — personality files exist, so it can score new content against established patterns
2. **Distillation integrates** — new T1 notes cluster against existing T2 patterns, not from scratch
3. **T2→T3 evolves** — existing personality files get nudged by new patterns, not created from nothing

Two sub-approaches:

**D1: Chronological interleave** — mix new and existing T1 by timestamp, re-seed entire timeline. Most faithful but re-processes everything.

**D2: Additive batch** (recommended) — load new corpus on top of existing network. Attention filter scores against current personality. Distillation integrates new patterns. Personality evolves. This is essentially normal operation at accelerated speed.

---

## Part 3: The `--seed-full-lifecycle` Mode

A single seeding mode that orchestrates the full pipeline per batch. Serves both Strategy C and D:

```python
# Proposed interface
run.py --seed-full-lifecycle \
  --corpus-dir /path/to/corpus \
  --batch-size 200 \
  --decay-every 5 \        # run decay cycle every N batches
  --evolve-every 10 \      # run T2→T3 every N batches
  --filter/--no-filter \    # use attention filter (requires existing personality) or default scoring
  --dry-run                 # estimate cost without LLM calls
```

Per-batch loop:
```
for batch in chronological_batches(corpus, size=200):
    if --filter and has_personality():
        scored = attention_filter.filter(batch)
    else:
        scored = default_score(batch)  # importance 0.5
    
    store_notes(scored)               # T1 storage
    distill_t1_to_t2()               # clustering + cross-links
    
    if batch_count % decay_every == 0:
        run_decay_cycle()             # prune low-link notes
    
    if batch_count % evolve_every == 0:
        distill_t2_to_t3()           # personality evolution
```

The individual pieces all exist (Modules 1-6 + MVP orchestrator). What's missing is the orchestration glue — estimated ~2-3 hours of Build work, mostly in `run.py`.

### Implementation Prerequisites
- MVP.4b complete (batched T2→T3 reflection + bootstrap creation)
- Decay mechanism tested on live vault (exists in Memory Store but hasn't been run on real data yet)
- Attention filter tested with real personality context (exists but only tested with FakeLLM)

---

## Part 4: Corpus Tuning Pipeline

### The Problem

Every corpus has different characteristics that affect pipeline parameters. Our first seed required manual discovery of:
- Embedding model (monolingual vs multilingual — language composition determines this)
- UMAP dimensionality (reduce_dims: 5/10/15/20 — 15 was optimal for this corpus)
- Coherence threshold (0.4 too strict for multilingual, lowered to 0.25)
- LLM model selection (Sonnet 4.5 refuses bilingual content, Sonnet 4 works)
- Content cleaning patterns (FB boilerplate, LJ comment stripping, track listings)
- Note ID collision risk (multi-item source entries)

These are all documented in `notebooks/TUNING_GUIDE.md` but currently require manual discovery per corpus.

### Proposed: `tools/explore_corpus.py`

An automated tuning pipeline that analyzes a corpus before seeding and produces recommendations. Already outlined in DEVPLAN Discussion Items:

```bash
# Usage
cd /mnt/passport/shared/phosphene
python3 tools/explore_corpus.py --corpus-dir /path/to/export --adapter livejournal
```

### Pipeline Steps

**Step 1: Source analysis (no LLM, free)**
- Count items per adapter type
- Measure language distribution (% Cyrillic, Latin, mixed, CJK, etc.)
- Detect multi-item source entries (collision risk)
- Sample content patterns — identify boilerplate (FB "shared a post", track listings, URLs)
- Report: item count, language split, estimated T1 note count, cleaning recommendations

**Step 2: Embedding model selection (free, ~2 min)**
- Embed a 200-item sample with both `all-MiniLM-L6-v2` (monolingual) and `paraphrase-multilingual-MiniLM-L12-v2` (multilingual)
- Compute within-language vs cross-language similarity means
- If cross-language gap > 0.2: recommend multilingual
- Report: model recommendation with similarity statistics

**Step 3: Terrain analysis (free, ~3 min)**
- Embed full corpus (or 1000-item sample for large corpora)
- Compute pairwise similarity statistics (mean, std, percentiles)
- Report: similarity distribution, whether corpus is tight (homogeneous) or diffuse (diverse)

**Step 4: Dimensionality sweep (free, ~5 min)**
- Run UMAP at dims 5/10/15/20/25 on the embedded sample
- Run HDBSCAN at each dimensionality
- Report: cluster count, largest cluster size, noise percentage, recommended reduce_dims

**Step 5: Coherence threshold sweep (free, ~2 min)**
- At the recommended dims, compute cluster coherences
- Report: coherence distribution, recommended min_cluster_coherence threshold, how many clusters pass at each threshold (0.2/0.25/0.3/0.35/0.4)

**Step 6: LLM compatibility test (~$0.10-0.50)**
- Pick 2-3 real clusters from step 4
- Send each to the configured LLM model (Sonnet 4, 4.5, 4.6, Haiku)
- Check `stop_reason` — detect refusals
- Report: which models work, which refuse, recommended model for this corpus

**Step 7: Cost estimation**
- Based on item count, cluster count, and model pricing:
  - `--seed-direct` cost (free — embedding only)
  - `--seed-chronological` cost (T1→T2 distillation per batch)
  - `--seed-full-lifecycle` cost (with attention filter + decay + T2→T3)
- Report: estimated cost and time for each seeding strategy

### Output

```
=== Corpus Analysis: twitter_export ===
Items: 12,847
Languages: EN 89%, RU 8%, mixed 3%
Cleaning needed: URL-only tweets (2,103 items, 16%), RT boilerplate (891 items)
Collision risk: LOW (unique timestamps per tweet)

=== Recommended Parameters ===
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
REDUCE_DIMS=15
MIN_CLUSTER_COHERENCE=0.25
DISTILL_MODEL=claude-sonnet-4-20250514
DISTILL_THROTTLE=45

=== Cost Estimates ===
--seed-direct:         Free (embedding only, ~15 min)
--seed-chronological:  ~$8-12 (65 batches × $0.15)
--seed-full-lifecycle: ~$25-35 (with attention filter + decay)

=== Cleaning Recommendations ===
1. Strip URL-only tweets (no text content)
2. Strip RT prefix boilerplate
3. Consider: merge thread replies into parent tweet
```

### Implementation Effort

Steps 1-5 are CPU-only analysis — ~3-4 hours of Build work.
Step 6 requires LLM integration — ~1 hour.
Step 7 is arithmetic — ~30 min.

Total: ~5-6 hours of Build work. Could be phased:
- Phase 1: Steps 1-5 (free analysis, parameter recommendations)
- Phase 2: Steps 6-7 (LLM compatibility + cost estimation)

---

## Part 5: New Corpus Onboarding Workflow

The complete workflow for adding a new corpus:

```
1. Export data from source platform
2. Write adapter (if new format) or use existing
3. Run explore_corpus.py → get parameters + cleaning recommendations
4. Apply cleaning recommendations (update adapter or add filters)
5. Re-run explore_corpus.py → verify improvements
6. Choose seeding strategy:
   a. First corpus (no personality): Strategy A or C
   b. Additional corpus (personality exists): Strategy D2
7. Run the seed
8. Validate: preflight, density metrics, network visualization
9. Optional: run Strategy C pass 2-3 for quality improvement
```

### For the Twitter Export Specifically

1. Export: Twitter archive download (JSON or CSV)
2. Adapter: Write `TwitterAdapter` in `src/phosphene/source_ingestion/adapters/`
   - Parse tweet JSON → ContentItem
   - Handle: threads (merge replies?), retweets (strip or keep?), media-only tweets, quote tweets
   - Timestamp from tweet metadata
3. Run `explore_corpus.py --corpus-dir twitter_export --adapter twitter`
4. Apply recommendations (strip URL-only, handle RT prefix)
5. Seed with `--seed-full-lifecycle --filter` (personality exists from LJ)
6. Validate

---

## Scheduling

| Item | Depends on | Estimated effort |
|------|-----------|-----------------|
| `--seed-full-lifecycle` mode | MVP.4b complete | ~2-3 hours Build |
| `explore_corpus.py` Phase 1 (analysis) | Nothing | ~3-4 hours Build |
| `explore_corpus.py` Phase 2 (LLM test) | Phase 1 | ~1.5 hours Build |
| Twitter adapter | Nothing | ~2-3 hours Build |
| Strategy C pass 2 (filtered re-evaluation) | MVP.4b + `--seed-full-lifecycle` | ~1 hour (run, not code) |

None of these block MVP.4. They're post-MVP quality improvements and expansion capabilities.
