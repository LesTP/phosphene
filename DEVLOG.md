# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Append new entries at the bottom (newest last).
     During phase close, archive the previous phase's entries to DEVLOG_archive.md. -->

<!-- Earlier entries archived — see DEVLOG_archive.md -->

### Phase MVP.3 Plan: Integration hardening

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Planned MVP Orchestrator Phase 3 as Build work under `ARCH_orchestrator_mvp.md`: dispatch-level error isolation, activation logging, bootstrap transition proof, end-to-end fake-module validation, and restart recovery verification. The phase stays inside the MVP boundary with no lateral freedom, ambient context, Feedback Collector integration, Explorer integration, or orchestrator-owned durable state beyond the optional activation log.

DEVPLAN now transitions to `state: execute`, decrements `steps_remaining` to 7, and keeps focus on MVP.3.1 error isolation.

### Step MVP.3.1: Error isolation

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added dispatch-level activation isolation for scheduled/manual activations and inbound respond handling. Unexpected module exceptions now return `ActivationResult(success=False, outputs_delivered=0, error=str(exc))` with duration populated instead of escaping the activation.

Added orchestrator tests proving a throwing source ingestion module returns a failed activation result and does not prevent a subsequent decay activation in the same loop iteration. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (36 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (610 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 6, and moves focus to MVP.3.2 activation logging.

### Step MVP.3.2: Activation logging

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added activation logging at the shared activation wrapper. When `config.log_path` is set, successful and failed activations serialize the public `ActivationResult` fields as JSON lines with ISO timestamps; writes use a same-directory temporary file followed by `os.replace()` so the log file is not left partially written.

Added tests for multiple activation log records across a failed ingestion and successful decay activation, and for the no-log-path case producing no file output. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (38 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (612 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 5, and moves focus to MVP.3.3 bootstrap transition.

### Step MVP.3.3: Bootstrap transition

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the bootstrap transition proof for a single `MVPOrchestrator` run session. The test first confirms scheduled generation skips while the Memory Store has no personality files, then triggers ingestion to store a Tier 1 note, triggers distillation through fake T1→T2 and T2→T3 promotion, and verifies the next generation activation delivers output through Gateway without reconstructing the orchestrator.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (39 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (613 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 4, and moves focus to MVP.3.4 end-to-end integration test.

### Step MVP.3.4: End-to-end integration test

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the explicit MVP content-path validation test using fake modules wired through real `MVPOrchestrator`. The test triggers ingestion from two fake source results, verifies Attention Filter input flattening and Tier 1 note storage, triggers ready T1→T2 and T2→T3 distillation dispatch, then triggers generation and verifies the output is routed through Gateway.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (40 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (614 passed). DEVPLAN now keeps `state: execute`, decrements `steps_remaining` to 3, and moves focus to MVP.3.5 restart recovery.

### Step MVP.3.5: Restart recovery

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added restart recovery coverage for the MVP Orchestrator's stateless boundary. The test constructs an orchestrator, advances its in-memory schedule state, triggers ingestion, then constructs a second orchestrator with the same config and shared Memory Store boundary. The new instance starts with fresh schedule tracking while stored notes, simulated distillation metadata, and personality context remain available for generation.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (41 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (615 passed). All MVP.3 implementation steps are complete, so DEVPLAN now transitions to `state: review` and decrements `steps_remaining` to 2.

### Phase MVP.3 Review: Integration hardening

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Reviewed MVP.3 against `ARCH_orchestrator_mvp.md`. Must fix: activation log write failures could escape the isolation wrapper and stop the loop; fixed by finalizing activation results through a log-safe path that returns `success=False` with an activation-log error if logging fails. Should fix: none. Optional: none.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/orchestrator` (42 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (616 passed). DEVPLAN now transitions to `state: close` and decrements `steps_remaining` to 1.

### Phase MVP.3 Completion: Integration hardening

**Date:** 2026-05-09
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed MVP Orchestrator Phase 3. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (616 passed).

Phase MVP.3 delivered dispatch-level error isolation, activation JSONL logging, log-write failure isolation, bootstrap transition proof, end-to-end fake-module integration coverage, and restart recovery verification. The MVP Orchestrator now satisfies `ARCH_orchestrator_mvp.md` and is ready for human audit before post-MVP planning resumes.

DEVLOG learning review: MVP.3 landed linearly through planning, five implementation steps, and review. No repeated trial-and-error pattern or new environment gotcha needs promotion.
Contract Changes scan: All MVP.3 plan, step, review, and completion entries record "Contract changes: None". D-51 documents the integration-hardening scope boundary and is now closed; no upstream contract propagation remains.
DEVPLAN cleanup: reduced Phase MVP.3 to a one-line completion summary, kept Current Status on the completed MVP phase, and set the close gate in frontmatter.
ARCHITECTURE.md: MVP Orchestrator status updated from Phase MVP.2 complete to Complete.
DECISIONS.md: D-51 closed. PROJECT.md: no open project risks were resolved by this phase.

(MVP.2 entries archived to DEVLOG_archive.md on 2026-05-09.)

### Step MVP.4.1: Create run.py

**Date:** 2026-05-10
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added `run.py` as the MVP bootstrap entry point. The script reads `.env`, builds runtime configs for Memory Store, Attention Filter, Source Ingestion corpus adapters, Distillation, Generator, Gateway, and MVP Orchestrator, then exposes `--seed-only`, `--once`, and default cron-loop modes. It uses `paraphrase-multilingual-MiniLM-L12-v2` as the default embedding model and keeps `--help` import-safe even when the external `toolkit` package is not present in this checkout.

Verification passed with `PYTHONPATH=src:.python_deps python3 - <<'PY' ... import run ... PY`, `PYTHONPATH=src:.python_deps python3 run.py --help`, and `PYTHONPATH=src:.python_deps python3 -m pytest tests/`. DEVPLAN keeps `state: execute`, leaves `steps_remaining` at 3 after consuming one action from the prompt budget, and moves focus to MVP.4.2 seed-only mode.

### MVP.4 Integration Session (supervised)
**Date:** 2026-05-10 through 2026-05-12
**Mode:** supervised (interactive)
**Outcome:** In progress — seed run with distillation pending overnight

This was a two-day supervised integration session — the first time all modules ran against real dependencies, real APIs, and real corpus data. 25 commits covering:

**Corpus adapters (5 commits):**
- ljsm format support for LJ adapter (date extraction, comment stripping, reply context)
- Blogspot Atom adapter (posts + author follow-up comments)
- Facebook HTML export adapter (467 posts, boilerplate cleanup)
- Content cleaning in seed-direct (track listings, share links, bitrate lines)
- FB boilerplate stripping ("shared a photo/post")

**Bootstrap and seeding (6 commits):**
- `--seed-direct` mode (bypasses LLM attention filter, embeds locally)
- `--seed-chronological` mode (200-note batches, distillation between each)
- Fixed-size batches (replaced uneven yearly batches)
- Cross-platform toolkit path resolution
- 3,919 T1 notes successfully seeded from 4 sources

**Integration bugfixes (8 commits):**
- `_RaptorClusterConfig` interface: missing `min_cluster_size`, uppercase strategy, plain string vs enum `.value`, wrong metric default
- Gateway `allowed_chat_ids` kwarg not in toolkit
- JSON fence stripping in attention filter and distillation parsers
- Cluster summary prompt overflow (capped at 50 obs × 2000 chars)
- Rate limit throttling (30s between calls, 60s on 429)
- Per-cluster error tolerance with placeholder summaries
- System prompt for cluster summaries
- Model switch: Sonnet 4.5 refuses bilingual content (`stop_reason: refusal`), Sonnet 4 handles it (`stop_reason: end_turn`)

**Clustering optimization (2 commits):**
- UMAP `reduce_dims=15`: 25→227 clusters, largest 733→50, noise 76%→38%
- Tested dims 5/10/15/20; 15 optimal

**Deployment (3 commits):**
- Pi deployment: venv on ext4, toolkit copied to share, .env with TOOLKIT_SRC
- Network visualization tool (`tools/visualize_network.py`)
- Density measurement tool (`tools/measure_density.py`)

**Design decisions (2 commits):**
- D-52/D-53: multilingual embedding model, switchability
- Inbound message handler: `#` prefix → ingestion, no prefix → conversation, trust tiers

**Governance (2 commits):**
- `/phase-complete` step 5: integration check for cross-module types
- DEVPLAN gotchas: no inline SSH, integration checks before expensive runs, cost estimation

**Documentation (2 commits):**
- `notebooks/TUNING_GUIDE.md`: corpus-to-personality findings
- `AUTONOMOUS_SOFTWARE_DEVELOPMENT.md` §11 + lessons 25-29

**Key finding:** Integration testing is a distinct work regime. 15+ interface mismatches discovered, all at boundaries between real dependencies and fake test doubles. A dry-run probe script (`tools/check_clustering_compat.py`) catches these in 30 seconds — established as standard practice.

**Key finding:** LLM model version selection matters for personality corpora. Sonnet 4.5 refuses on bilingual casual content. Sonnet 4 produces excellent summaries. Must test with real cluster content before committing to a model.

### First successful T1?T2 distillation
**Date:** 2026-05-13
**Mode:** supervised
**Outcome:** Success � 11 T2 notes produced

Pipeline validated end-to-end: T1 notes (200, chronologically sorted with real timestamps from 2003-2026) ? UMAP (384?15 dim) ? HDBSCAN (12 clusters) ? LLM cluster summaries (12/12 succeeded, Sonnet 4.6, no refusals) ? coherence gating (11/12 passed at 0.25 threshold) ? T2 note writes ? assertion cache.

Key changes that enabled success:
- Sonnet 4.6 instead of 4.5 (which refuses bilingual content)
- reduce_dims=15 (UMAP pre-reduction eliminates mega-clusters)
- min_cluster_coherence=0.25 (lowered from 0.4 for multilingual model)
- 45s throttle between LLM calls (stays under 30K tokens/min)
- RAPTOR summary extraction from tree layers (was falling through to raw text fallback)
- Staging approach to limit distillation scope (engine processes all vault T1 notes)
- Success logging per cluster summary for progress tracking
- NoteInput.created_at for original timestamp preservation (D-54)
- All tuning params extracted to .env-backed config

### Note ID collision fix
**Date:** 2026-05-13
**Mode:** supervised
**Outcome:** 3,856 T1 notes (was 1,469 � 62% were silently overwritten)

Root cause: LJ comment replies share the parent post's title and timestamp. The note ID hash used only title+timestamp, so multiple replies from the same post generated identical filenames. Each subsequent write overwrote the previous file.

Fix: include note content in the SHA1 hash input (vault.py line 22). The 4-char hash suffix now differentiates notes with identical titles and timestamps but different content.

Also fixed: ASCII-only slugifier (only matched [A-Za-z0-9]) replaced with Unicode-aware \w regex. Cyrillic titles now produce readable slugs instead of falling back to 'note'.

Both are contract changes to the Memory Store vault module — note IDs generated after this fix are different from previous runs. Vault must be re-seeded.

### T2→T2 cross-link bug identified
**Date:** 2026-05-13
**Mode:** supervised (Discuss)
**Outcome:** Bug documented, fix planned as MVP.4a (autonomous Build)
**Contract changes:** Planned — `DistillationConfig` gains `cross_link_threshold` and `max_cross_links` fields (both with defaults, backward compatible)

Investigation of vault state after full chronological distillation revealed that `_write_tier2_cluster_notes()` (engine.py:638-641) creates an all-to-all mesh: every T2 note from a distillation run is linked to every other T2 note from the same run. Vault distribution: 225 notes with 224 T2 cross-links each (from `distill_full`), 26 notes with 25 each (from `distill_loop2`). The two cliques are disconnected from each other.

Designed for incremental operation (~10 clusters per batch = small clique, roughly correct), but the full-corpus bootstrap produced 225 clusters in one pass, creating a meaningless complete graph. T1 source links (5-16 per note) are correct.

Fix planned as three Build steps: (1) engine fix with centroid similarity filtering, (2) vault link regeneration script, (3) validation. See DEVPLAN MVP.4a for details.

### Step 1: Engine fix — similarity-filtered cross-links
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Success — distillation now links only similar same-run T2 clusters
**Contract changes:** `DistillationConfig` now includes `cross_link_threshold` and `max_cross_links`; `ARCH_distillation.md` step 7 documents centroid-similarity cross-link filtering.

Replaced the T2 all-to-all same-run link mesh with centroid cosine similarity ranking. Each promoted cluster now links only to peers above the configured threshold, capped at the configured top-K. Added regression coverage for five known centroids where only the similar pair cross-links, updated config contract tests, and kept backward compatibility through defaults.

Validation: `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation/` passed (82 tests). Full suite passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/` (619 tests).

### Step 2: Strip bad links + regenerate proper cross-links
**Date:** 2026-05-13
**Mode:** autonomous Build
**Outcome:** Success — live vault T2 cross-links rebuilt from centroid similarity
**Contract changes:** None.

Added `tools/rebuild_t2_crosslinks.py` with dry-run and write modes, using the Memory Store markdown parser and stored centroid embeddings. The tool strips T2→T2 links, preserves non-T2 source links, ranks candidate T2 peers by cosine similarity, and rewrites note frontmatter link counts with corrected outbound links.

Live vault run at `--threshold 0.45 --max-links 15`: dry-run and write both processed 251 T2 notes, stripped 51,050 old T2 links, preserved 2,645 non-T2 links, added 3,582 similarity-filtered T2 links, and produced a T2 link distribution from 1 to 15 links per note. `tools/measure_density.py` changed mean link degree from 26.15 before rebuild to 3.03 after rebuild.

Validation: `PYTHONPATH=src:.python_deps python3 -m pytest tests/` passed (621 tests).
