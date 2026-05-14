# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Append new entries at the bottom (newest last).
     During phase close, archive the previous phase's entries to DEVLOG_archive.md. -->

<!-- MVP.3 entries archived to DEVLOG_archive.md on 2026-05-14. -->
<!-- Earlier entries archived — see DEVLOG_archive.md -->

### Step MVP.4.1: Create run.py

**Date:** 2026-05-10
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added `run.py` as the MVP bootstrap entry point. The script reads `.env`, builds runtime configs for Memory Store, Attention Filter, Source Ingestion corpus adapters, Distillation, Generator, Gateway, and MVP Orchestrator, then exposes `--seed-only`, `--once`, and default cron-loop modes. It uses `paraphrase-multilingual-MiniLM-L12-v2` as the default embedding model and keeps `--help` import-safe even when the external `toolkit` package is not present in this checkout.

### MVP.4 Integration Session (supervised)
**Date:** 2026-05-10 through 2026-05-12
**Mode:** supervised (interactive)
**Outcome:** Complete — seed run with distillation succeeded

Two-day supervised integration session — first time all modules ran against real dependencies, real APIs, and real corpus data. 25 commits covering corpus adapters (5), bootstrap/seeding (6), integration bugfixes (8), clustering optimization (2), deployment (3), design decisions (2), governance (2), documentation (2). 3,919 T1 notes seeded from 4 sources. Key findings: integration testing is a distinct work regime (15+ interface mismatches at fake/real boundaries); LLM model version selection matters (Sonnet 4.5 refuses bilingual content, Sonnet 4 works).

### First successful T1→T2 distillation
**Date:** 2026-05-13
**Mode:** supervised
**Outcome:** Success — 11 T2 notes from 200-note batch

Pipeline validated: T1 → UMAP (384→15 dim) → HDBSCAN (12 clusters) → LLM summaries (12/12 Sonnet 4.6, no refusals) → coherence gating (11/12 at 0.25) → T2 writes → assertion cache.

### Note ID collision fix
**Date:** 2026-05-13
**Mode:** supervised
**Outcome:** 3,856 T1 notes (was 1,469 — 62% silently overwritten)

Root cause: LJ comment replies share parent's title+timestamp → identical filenames. Fix: include content in SHA1 hash. Also fixed ASCII-only slugifier → Unicode-aware \w regex. Contract change: note IDs differ from previous runs; vault re-seeded.

### T2→T2 cross-link bug identified
**Date:** 2026-05-13
**Mode:** supervised (Discuss)
**Outcome:** Bug documented, fix planned as MVP.4a (autonomous Build)
**Contract changes:** Planned — `DistillationConfig` gains `cross_link_threshold` and `max_cross_links`

All-to-all mesh in `_write_tier2_cluster_notes()`: every T2 from a run linked to every other. 225 notes × 224 links each. Designed for incremental (small clique OK), broke at bootstrap scale.

### MVP.4a Step 1: Engine fix — similarity-filtered cross-links
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** `DistillationConfig` now includes `cross_link_threshold` and `max_cross_links`; `ARCH_distillation.md` step 7 updated.

Replaced all-to-all mesh with centroid cosine similarity ranking + top-K cap. 619→621 tests.

### MVP.4a Step 2: Strip bad links + regenerate
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** None.

`tools/rebuild_t2_crosslinks.py`: stripped 51,050 bad T2 links, preserved 2,645 T1 links, added 3,582 similarity-filtered T2 links. Distribution 1-15 per note. Mean link degree 26.15→3.03.

### MVP.4a Step 3: Validate vault state
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** None.

Vault validated: 4,107 notes, 225 clusters, mean link degree 3.03. Rebuild idempotent (rewritten_count: 0 on re-run). Preflight GO. 621 tests pass.

### T2→T3 distillation blocked — escalation
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Escalated — design decision needed
**Contract changes:** None.

Worker estimated T2→T3 reflection at ~202K input tokens (251 T2 notes) — exceeds context budget. Also: 0 T3 files, evolution path only supersedes existing T3. Stopped before LLM spend. See `DISCUSS_T2_TO_T3_BOOTSTRAP.md`.

### MVP.4b design decision: Batch reflection + T3 bootstrap
**Date:** 2026-05-14
**Mode:** supervised (Discuss)
**Outcome:** Decision closed — Option 1+2b selected
**Contract changes:** Planned — `DistillationConfig` gains `t2_reflection_batch_size`; `distill_t2_to_t3()` bootstrap branch when T3 is empty.

Discussed three options for T2→T3 bootstrap (see `DISCUSS_T2_TO_T3_BOOTSTRAP.md`):
- Option 1 (T3 creation path): necessary but doesn't solve context overflow alone
- Option 2b (batch reflection): essential for any T2 volume, mirrors `--seed-chronological` pattern
- Option 3 (manual T3 seed): rejected — defeats pipeline's purpose of deriving personality from corpus

Selected **Option 1+2b combined**: batch reflection becomes the permanent T2→T3 path (not bootstrap-specific). T3 bootstrap creation fires only when personality files are empty. ~3-4 hours autonomous Build work planned as MVP.4b steps 1-4 in DEVPLAN.


### MVP.4b phase plan activated
**Date:** 2026-05-14
**Mode:** autonomous Plan
**Outcome:** Ready for execution
**Contract changes:** Planned -- `DistillationConfig` gains `t2_reflection_batch_size`; `ARCH_distillation.md` will document batched T2 reflection and empty-T3 bootstrap behavior during implementation.

Confirmed MVP.4b as a four-step Build phase: batch reflection, bootstrap T3 creation, FakeLLM integration proof, and live-vault T2->T3 validation after preflight and cost estimate. DEVPLAN state moved to `execute`.

### Step MVP.4b.1: Batch T2 reflection
**Date:** 2026-05-14
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** `DistillationConfig` now includes `t2_reflection_batch_size`; `ARCH_distillation.md` documents batched T2 reflection.

Added permanent batching to the T2→T3 reflection path. Tier 2 patterns are sorted by importance descending with unresolvedness as the tie-breaker, split by `config.t2_reflection_batch_size`, reflected with the existing prompt once per batch, and merged into a single insight list before evolution. Single-batch runs keep the same request shape as before.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation/test_distillation_exports.py tests/distillation/test_t2_to_t3_preparation.py` (53 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (624 passed). DEVPLAN keeps `state: execute`, decrements `steps_remaining` to 2, and moves focus to MVP.4b Step 2: empty-T3 bootstrap creation.

### Step MVP.4b.2: Empty-T3 bootstrap creation
**Date:** 2026-05-14
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** `ARCH_distillation.md` documents the empty-personality bootstrap branch inside `distill_t2_to_t3()`.

Added a bootstrap proposal path for T2→T3 when `memory_store.get_personality_context()` returns no personality files. The engine now sends merged reflection insights to a bootstrap-specific LLM prompt asking for 3-7 corpus-specific initial personality files, parses that response separately from supersession proposals, and writes Tier 3 notes with `version_count:1`. Existing personality files still use the normal supersession/unchanged evolution path.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation/test_t2_to_t3_preparation.py` (42 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (633 passed). DEVPLAN keeps `state: execute`, decrements `steps_remaining` to 1, and moves focus to MVP.4b Step 3: full T2→T3 FakeLLM integration coverage.

### Step MVP.4b.3: Full T2→T3 FakeLLM integration
**Date:** 2026-05-14
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** None.

Added real MemoryStore integration coverage for the complete T2→T3 bootstrap path. The test seeds 60 Tier 2 notes with no Tier 3 files, verifies reflection runs in two batches at `t2_reflection_batch_size=30`, verifies bootstrap creates Tier 3 personality files retrievable through `get_personality_context()`, then runs T2→T3 a second time and verifies the normal evolution prompt is used instead of the bootstrap branch.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation/test_t1_to_t2_integration.py -k 't2_to_t3_bootstrap_then_normal_evolution'` (1 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (634 passed). DEVPLAN keeps `state: execute`, decrements `steps_remaining` to 0, and moves focus to MVP.4b Step 4: live-vault T2→T3 run and validation.

### Step MVP.4b.4: Live T2→T3 distillation
**Date:** 2026-05-14
**Mode:** supervised
**Outcome:** Success — 7 personality files created and evolved
**Contract changes:** `_pattern_note_payload()` no longer sends `cluster_group`; reflection prompt explicitly requests full `note_id` slugs.

First run (bootstrap): 9 batches of reflection, 42 insights produced. But batches 3, 7, 8 produced 0 insights — the LLM used numeric `cluster_group` values ("198", "152") in `source_pattern_ids` instead of full `note_id` slugs. Root cause: `_pattern_note_payload()` sent both `note_id` (long slug) and `cluster_group` (short number), and the LLM preferred the shorter form. All insights from those 3 batches were dropped by the validation.

Bootstrap still succeeded: 42 insights from 6/9 batches produced 7 initial T3 personality files: The Authenticity Paradox, Productive Incompletion as Preferred State, Multilingual Identity Performance, Expertise Without Authority, Cultural Connection Through Shared Uncertainty, Emotional Deflection Through Analysis, Digital Ephemerality as Structural Feature.

Fix applied: (1) removed `cluster_group` from `_pattern_note_payload()` — the LLM no longer sees the competing short ID; (2) added explicit instruction in reflection prompt to use full `note_id` strings; (3) changed `_parse_reflection_insights()` from crash-on-hallucination to warn-and-drop (tolerant parsing).

Second run (evolution): all 9/9 batches succeeded, 51 insights (was 42). All 7 personality files superseded with enriched content. Titles evolved to be more specific (e.g., "The Authenticity Paradox" → "The Authenticity Paradox and Evolution Beyond Binary Thinking").

**Gotcha promoted:** LLMs hallucinate shorter/simpler IDs when long slug IDs and short numeric IDs coexist in the prompt. Remove competing ID fields or use synthetic short IDs with a mapping.

### MVP.4c phase plan activated
**Date:** 2026-05-14
**Mode:** autonomous Plan
**Outcome:** Ready for execution
**Contract changes:** None.

Confirmed MVP.4c as a two-step Build phase: first persist every `GeneratorOutput` to `vault/outputs/` before Telegram routing and update the saved frontmatter after delivery, then run the first live generation on the Pi and verify Telegram delivery plus output archival. DEVPLAN state moved to `execute`.

### Step MVP.4c.1: Save GeneratorOutput to vault/outputs/
**Date:** 2026-05-14
**Mode:** autonomous Build
**Outcome:** Success
**Contract changes:** None.

Added generation output archival inside `_run_generation()`: after `generator.generate()` and before routing, the orchestrator writes markdown under `vault/outputs/` with YAML frontmatter for intent tag, output mode, importance, active T3 personality file IDs, creation time, and initial `delivery_success: false`. After routing completes, the same file is updated to reflect actual delivery success, so failed Telegram delivery still leaves the generated body archived.

Added tests for successful and failed delivery persistence. Also updated a stale distillation test to match the already-documented MVP.4b behavior where hallucinated reflection source IDs are warned-and-dropped instead of raising. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation/test_t2_to_t3_preparation.py tests/orchestrator/test_orchestrator_exports.py` (86 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (636 passed). DEVPLAN keeps `state: execute`, decrements `steps_remaining` to 1, and moves focus to MVP.4c Step 2: first live generation plus Telegram delivery on the Pi.

### Step MVP.4c.2: First live generation blocked
**Date:** 2026-05-14
**Mode:** autonomous Build
**Outcome:** Blocked — Pi hostname unavailable
**Contract changes:** None.

Attempted to run the required Pi-side script for preflight plus `run.py --once`, but both `scp` and `ssh` failed before execution with `Could not resolve hostname pirozhok: Name or service not known`. No preflight, LLM call, Telegram delivery, or vault write happened. DEVPLAN is blocked for human/operator action: run the Step 2 command locally on the Pi or provide a reachable SSH/Tailscale host from this environment.

### MVP.4d phase plan activated
**Date:** 2026-05-14
**Mode:** autonomous Plan
**Outcome:** Ready for execution
**Contract changes:** None.

Confirmed MVP.4d as a three-step Build phase: write the MemoryStore index cache after a full rebuild, load the cache on startup when valid and fresh with a `skip_cache` test escape hatch, then validate the warmed-cache `run.py --once` path on the Pi. DEVPLAN state moved to `execute`; the invocation step budget was normalized from the prompt and decremented to 3.
