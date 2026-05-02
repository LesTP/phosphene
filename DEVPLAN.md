---
module: 2
phase: 1
phase_title: Attention Filter contract and scoring foundation
step: 2.1.1
mode: autonomous
blocked: false
regime: Build
review_done: false
---

# Phosphene — Development Plan

<!-- This file is the primary state document for autonomous iteration.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses. -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step. -->

- **What this is** — Autonomous personality agent with hierarchical memory, attention filtering, and personality development through distillation.
- **Key constraints** — Python 3.12+. Depends on toolkit/ (sibling project, all modules complete). Obsidian-compatible markdown storage. LLM API costs managed via subscription rotation and model tier system. Runs on Raspberry Pi 5 (orchestration only, inference via API).
- **Gotchas** —
  - toolkit/ is an external dependency — import from it, never modify it
  - Memory Store uses consumer-provided embeddings (no toolkit/embedding dependency in the store itself)
  - All 9 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — Module 2 (Attention Filter), Phase 1: Attention Filter contract and scoring foundation.
- **Focus** — Build the public Attention Filter package contract and deterministic scoring foundation before adding live embedding/LLM calls.
- **Blocked/Broken** — None

## Module 1: Memory Store (complete)

Four-phase plan (matching ARCH_memory_store.md public API surface) — all phases complete.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (complete)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`. See DEVLOG "Phase 4 Completion" entry.

## Module 2: Attention Filter (in progress)

Planned phases follow `ARCH_attention_filter.md`: first stabilize the public contract (including `ScoringConfig`) and deterministic geometric scoring helpers, then add Memory Store retrieval/embedding integration, then LLM Phase 1 scoring (precision_surplus) and assertion extraction (friction), then full batch orchestration with triple-gate blend.

### Phase 1 (in progress): Attention Filter contract and scoring foundation

Regime: Build

Outcome: a testable `phosphene.attention_filter` package exposing the ARCH-defined dataclasses (including `ScoringConfig`), errors, default prompt criterion (precision_surplus), config validation, triple-gate Phase 2 activation check, prompt/structure blend calculation with `phase2_max_weight` cap, and deterministic Phase 2 geometric scoring helpers. This phase deliberately excludes live toolkit embedding calls and LLM prompt execution; those are later phases.

Steps:

- [ ] **2.1.1** — Scaffold `phosphene.attention_filter` package exports and public dataclasses matching `ARCH_attention_filter.md`: `ContentItem`, `FilterCriterion`, `ScoringConfig`, `AttentionFilterConfig`, `AnnotatedFragment`, `FilterResult`. Add `InvalidScoreError`. `ScoringConfig` carries Phase 2 criterion weights (7), scoring thresholds (`link_density_sim_threshold`, `gap_factor_exponent`, `assertion_alignment_threshold`), triple-gate thresholds (`note_count_threshold`, `cluster_count_threshold`), and `phase2_max_weight`.
- [ ] **2.1.2** — Add default prompt criterion construction (precision_surplus only) and config validation: `acceptance_threshold` in [0.0, 1.0], `density_crossover` > 0, `ScoringConfig` weights non-negative, `phase2_max_weight` in [0.0, 1.0], triple-gate thresholds positive.
- [ ] **2.1.3** — Implement triple-gate check and blend calculation from `DensityMetrics`. Triple gate: Phase 2 activates when `note_count >= threshold` AND `cluster_count >= threshold` AND `mean_link_degree >= density_crossover × 0.5`. Blend: `structure_weight` ramps linearly from 0.0 to `phase2_max_weight` as `mean_link_degree` goes from `density_crossover × 0.5` to `density_crossover × 2.0`, capped at `phase2_max_weight`. `prompt_weight = 1.0 - structure_weight`. Cover edge cases: empty memory (gate fails → pure prompt), high density (cap hit), exactly-at-threshold.
- [ ] **2.1.4** — Implement deterministic Phase 2 geometric scoring helpers. Each takes pre-computed embeddings/similarities and returns a score in [0.0, 1.0]:
  - `score_liminality(text_sims_to_centroids)` — inter-cluster gap formula with `gap_factor_exponent`
  - `score_friction(topical_sim, assertion_alignment)` — product of similarity and misalignment (assertion extraction itself is a later-phase LLM call; this helper takes pre-computed alignment)
  - `score_unexpected_connection(text_sims_to_centroids, cluster_pairwise_sims)` — max bridge score over cluster pairs
  - `score_structural_insight(text_sim_to_meta_cluster)` — direct similarity pass-through
  - `score_link_density(note_similarities, threshold)` — count above `link_density_sim_threshold`
  - `score_cluster_novelty(text_sims_to_centroids)` — `1 - max_sim`
  - `score_unresolvedness_affinity(note_similarities, note_unresolvedness_scores)` — weighted sum
  - `compute_phase2_composite(scores, scoring_config)` — weighted average using `ScoringConfig` weights
- [ ] **2.1.5** — Focused unit tests: package exports match ARCH types, `ScoringConfig` defaults, validation failures, triple-gate activation logic, blend weight edge cases, each geometric scoring helper (boundary values, degenerate inputs like zero/one cluster, empty note list), composite score with non-uniform weights.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
