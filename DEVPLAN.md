---
phase: MVP.4c
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
  - **LLM ID hallucination** — LLMs prefer shorter IDs when long slugs and short numeric IDs coexist in prompts. Remove competing ID fields from LLM payloads, or use synthetic short IDs with a mapping.

## Current Status

- **Phase** — MVP.4c: Generation output persistence + first run
- **Focus** — Save generations to vault/outputs/ before Telegram delivery, then first live generation.
- **Blocked** — No.

## MVP.4: Remaining Steps

- [x] T1→T2 distillation working — 12/12 cluster summaries succeeded, 11 T2 notes produced from 200 notes
- [x] **Fix missing notes** — root cause: note ID collision (same title+timestamp → same filename). Fixed by including content in hash. Re-seeded: 3,856 T1 notes (was 1,469).
- [x] **Stage 200 notes + run preflight** — prepare for chronological distillation
- [x] **Full chronological distillation** — 3,856 T1 → 225 clusters, 2,328 promoted, 1,528 noise. 251 T2 notes + 225 assertion caches.
- [x] **Fix T2→T2 cross-links** — engine fixed; vault rebuilt and validated. See MVP.4a.
- [x] **T2→T3 distillation** — 7 personality files bootstrapped and evolved. See MVP.4b.
- [ ] **Save generations** — see MVP.4c below
- [ ] **Run generation** — first output via Telegram
- [ ] **Verify Telegram** — check message arrives on phone

## MVP.4c: Generation Output Persistence (autonomous, Build)

**Problem:** `_run_generation()` produces a `GeneratorOutput` in memory, routes it to Telegram, and discards it. Generated content is not saved anywhere. The system's development over time cannot be studied without preserving its outputs.

**Decision:** Save to `vault/outputs/` as Obsidian-compatible markdown with frontmatter. NOT in the distillation loop (distillation reads `vault/tier1/`, `vault/tier2/`, `vault/tier3/` only). Outputs are an archival/analysis layer — they can be retrospectively analyzed or selectively promoted to T1, but by default they do not feed back into personality evolution. This avoids echo chamber / self-reinforcement.

**Telegram smoke test:** Passed. Bot `@battlepenguin_phosphenebot` delivered to chat_id successfully.

### Step 1: Save GeneratorOutput to vault/outputs/

**What:** In `_run_generation()` (orchestrator.py), after `generator.generate()` and before `route()`, write the output as a markdown file in `vault/outputs/`:

```
vault/outputs/{slug}-{timestamp}-{hash}.md
---
intent_tag: observation
output_mode: prompted
importance_score: 0.7
delivery_success: true/false  (updated after route())
personality_file_ids: [list of T3 note_ids active at generation time]
created_at: '2026-05-14T09:30:00+00:00'
---
[generated content body]
```

Save BEFORE routing so the output is preserved even if Telegram delivery fails. Update `delivery_success` after routing completes.

**Files:** `orchestrator/orchestrator.py` — `_run_generation()`. Possibly a `_save_generation_output()` helper.

**Verification:** Unit test: run generation with FakeGenerator + FakeGateway, verify `.md` file appears in `vault/outputs/`, verify frontmatter fields. Test with failed delivery: verify file still saved with `delivery_success: false`. Existing tests must pass.

### Step 2: First live generation + Telegram delivery

**What:** Run `run.py --once` on the Pi. This triggers one orchestrator cycle: ingestion (no sources configured → skip), distillation (gates won't pass — just ran), generation (personality files exist → generate), delivery (Telegram).

**Verification:**
- Generated content appears in `vault/outputs/`
- Message arrives on Telegram
- Content is recognizably derived from the personality files (not generic)
- Activation log (`logs/mvp_orchestrator.jsonl`) records the result

**Note:** This step involves real LLM spend (~$0.50-1). Run on Pi.

## MVP.4b: Batch Reflection + T3 Bootstrap — Complete

Batched T2 reflection (30 notes per batch) + bootstrap T3 creation. 251 T2 patterns → 51 insights → 7 personality files created and evolved. See DEVLOG.

**What:** End-to-end test: seed a MemoryStore with 60 T2 notes (no T3), run `distill_t2_to_t3()` with FakeLLM, verify:
- Reflection ran in 2 batches (batch_size=30)
- Bootstrap creation produced T3 personality files
- Personality files are stored in vault/tier3/
- `get_personality_context()` returns the new files
- A second `distill_t2_to_t3()` call uses the normal supersession path (not bootstrap)

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
