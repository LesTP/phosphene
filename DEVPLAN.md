---
module: REVIEW_HARDENING
phase: 2
phase_title: "Pre-Module-7 Hardening Phase B: unresolvedness composite utility + network diagnostics"
step: 1
mode: Build
blocked: null
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
  - **No ripgrep** — `rg` is not installed in the Codex container. Use `find` and `grep` instead. Do not attempt `rg` on first command.
  - **Subagent context** — when spawning Explore or review subagents, include in the prompt: (1) source tree layout is `src/phosphene/<module>/`, not `src/<module>/`; (2) the working test command is `PYTHONPATH=src:.python_deps python3 -m pytest`; (3) `.python_deps/` contains all pip dependencies. Subagents have no memory of the parent's environment discovery.

## Current Status

- **Phase** — Pre-Module-7 Hardening: Phase B in progress.
- **Focus** — Step 1: unresolvedness composite utility.
- **Blocked/Broken** — None

## Pre-Module-7 Hardening

*These two phases implement the "Now" items from the external review (phosphene.md Section 7.10). They harden the existing codebase before Module 7 (Feedback Collector) begins.*

### Phase A (complete): Attention Filter additions

Delivered ARCH-specified wild-card accepts and near-miss recording for the Attention Filter, with config/type validation, filter partitioning, export coverage, review, and full-suite verification. See DEVLOG "Phase REVIEW_HARDENING.1 Completion" entry.

### Phase B (in progress): Unresolvedness composite utility + network diagnostics tool

Adds the unresolvedness composite scorer (phosphene.md Section 7.3) and the network diagnostics tool (phosphene.md Section 7.7). These are new code — no existing module modifications.

**Step 1 (next): Unresolvedness composite utility**

Create `src/phosphene/scoring/__init__.py` and `src/phosphene/scoring/unresolvedness.py`:

```python
def compute_unresolvedness(
    note: MemoryNote,
    density_metrics: DensityMetrics,
    similar_notes: list[MemoryNote],  # from search_by_embedding
) -> float:
```

The function computes a composite [0.0, 1.0] from the following subcomponents:
- **Rising links without promotion:** `min(1.0, note.link_count / 5.0)` when `note.tier == 1`. A Tier 1 note with 5+ links that hasn't been clustered is strongly unresolved. Zero contribution if promoted.
- **Reappearance signal:** count of `similar_notes` with high similarity (>0.7) that are themselves unresolved (unresolvedness > 0.3). Normalized to [0.0, 1.0].
- **Conflicting alignments:** count of `similar_notes` where the note is linked to notes that have friction targets pointing at each other. Requires checking `friction_target` on connected notes. Normalized.
- **Survival signal:** `min(1.0, days_since_creation / tier1_base_retention_days)` — how close to decay deadline without promotion. Higher = more unresolved.

Composite: weighted average with configurable weights, default equal. Output clamped to [0.0, 1.0].

This is a pure function with no side effects. It does not call Memory Store — the caller passes in the data. This keeps it testable without any store fixture.

Tests (`tests/scoring/test_unresolvedness.py`):
- Zero inputs → 0.0.
- High link count on Tier 1 note → high subcomponent.
- Promoted note (Tier 2) → zero link-without-promotion contribution.
- Similar unresolved notes present → high reappearance signal.
- Near-decay-deadline note → high survival signal.
- Composite is clamped to [0.0, 1.0].
- Custom weights shift the composite.

**Step 2 (pending): Network diagnostics tool**

Create `tools/network_diagnostics.py` — a standalone script that reads Memory Store and computes health metrics. Not a module — no ARCH file, no exports, no module dependencies beyond Memory Store.

Input: `MemoryStoreConfig` (vault path). Output: printed report to stdout.

Metrics to compute (from phosphene.md Section 7.7):

| Metric | Computation |
|--------|-------------|
| **Cluster diversity** | Load all Tier 2 notes, group by `cluster_group`, compute mean pairwise embedding distance between cluster centroids. Report: count of clusters, mean inter-cluster distance. |
| **Outlier ratio** | For each Tier 1 note with an embedding, compute max similarity to all Tier 2 cluster centroids. Report: fraction with max_sim < 0.3. |
| **Bridge-node density** | Notes with similarity > 0.4 to 2+ clusters where those clusters have low mutual similarity (< 0.5). Report: count and fraction. |
| **Unresolvedness distribution** | Load all notes, histogram unresolvedness in 5 bins: [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0]. Report counts per bin. |
| **Compression damage** | Count notes with links pointing to note_ids that no longer exist in the store (orphaned links). Report: count and fraction. |
| **RAPTOR-Louvain divergence** | Build a graph from Memory Store wikilinks, run Louvain community detection (`networkx` + `community` / `python-louvain`), compare resulting communities against RAPTOR's embedding-based `cluster_group` assignments on Tier 2 notes. Report: fraction of notes whose Louvain community differs from their nearest RAPTOR cluster. High divergence = the link structure is saying something the embeddings aren't capturing (bridge notes, cross-topic structural clusters). Requires ≥10 linked notes to produce meaningful output; below that threshold report "N/A — insufficient link density". |
| **Note/tier summary** | Tier counts, mean link degree, total notes — wraps `get_density_metrics()`. |

The script uses `argparse` with `--vault-path` and `--embedding-path` arguments. It instantiates a `MemoryStore`, calls the read API, computes metrics, and prints a formatted report.

Mirror index and free-play value ratio require Generator output logs which don't exist yet — these are stubbed with "N/A — requires Generator output logs" in the report.

Tests (`tests/tools/test_network_diagnostics.py`):
- Smoke test: runs against an empty vault, produces a report without crashing.
- Populated vault: create a small Memory Store fixture with known structure, verify metric values.
- Orphaned link detection: store notes with links to non-existent IDs, verify compression damage count.
- Louvain divergence: create a fixture with two RAPTOR clusters and cross-cluster links forming a different Louvain community; verify divergence fraction is non-zero. Below-threshold fixture (< 10 linked notes) reports N/A.

**Step 3 (pending): Integration and cross-module regression**

- Run full test suite: `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -v`.
- Verify no import errors from the new `scoring` package.
- Verify the diagnostics tool runs as a script: `PYTHONPATH=src:.python_deps python3 tools/network_diagnostics.py --vault-path /tmp/test_vault`.

## Module 1: Memory Store (complete)

Four-phase plan (matching ARCH_memory_store.md public API surface) — all phases complete.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (complete)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`. See DEVLOG "Phase 4 Completion" entry.

## Module 2: Attention Filter (complete)

Planned phases follow `ARCH_attention_filter.md`: first stabilize the public contract (including `ScoringConfig`) and deterministic geometric scoring helpers, then add Memory Store retrieval/embedding integration, then LLM Phase 1 scoring (precision_surplus) and assertion extraction (friction), then full batch orchestration with triple-gate blend.

### Phase 1 (audited complete): Attention Filter contract and scoring foundation

Delivered ARCH-aligned public dataclasses/exports, default precision-surplus criteria, config validation, triple-gate blend helpers, deterministic Phase 2 geometric scoring helpers, and focused tests. Audited complete. See DEVLOG "Phase 2.1 Completion" and "Phase 2.1 Audit Closure" entries.

### Phase 2 (reviewed complete): Memory Store retrieval and embedding integration

Delivered embedding boundary integration, Memory Store density reads, similar-note retrieval contexts, Memory Store-backed structural preparation, and non-LLM public-path wiring without Memory Store writes or premature LLM/annotation behavior. Reviewed complete. See DEVLOG "Phase 2.2 Completion" and "Phase 2.2 Audit Closure".

### Phase 3 (complete): LLM Phase 1 scoring and assertion extraction

Delivered private LLM prompt scoring, precision-surplus composite integration, incoming assertion extraction, friction-preparation records, and public-path regression coverage while preserving the no-accepted-fragments boundary before orchestration. Reviewed and completed. See DEVLOG "Phase 2.3 Review" and "Phase 2.3 Completion" entries.

### Phase 4 (complete): Full batch orchestration and annotation output

Delivered annotation generation, acceptance and auto-accept decisions, public `AnnotatedFragment` assembly, rejected counts, batch metadata, and Phase 2 assertion-extraction gating while preserving read-only Memory Store behavior. Reviewed and completed. See DEVLOG "Phase 2.4 Review" and "Phase 2.4 Completion" entries.

## Module 3: Source Ingestion (complete)

Planned phases follow `ARCH_source_ingestion.md`: first stabilize the public contract, manager orchestration, adapter registry boundary, shared content normalization, and state-marker abstraction without live network adapters; then add concrete autonomous adapters, human-share handling, corpus import adapters, and persistence/integration hardening.

### Phase 1 (complete): Source Ingestion contract and adapter foundation

Delivered ARCH-aligned public dataclasses/exports, config validation, adapter protocol/registry, manager polling orchestration, per-adapter error reporting, in-memory last-seen marker handoff, deterministic normalization helpers, and focused unit tests. Reviewed and completed. See DEVLOG "Phase 3.1 Review" and "Phase 3.1 Completion" entries.

### Phase 1.5 (complete): Coverage tooling infra

Added `pytest-cov` dev tooling and captured the full-suite baseline: 310 tests pass, 98% total coverage, no tracked module below 80%. Reviewed and completed. See DEVLOG "Phase 3.1.5 Review" and "Phase 3.1.5 Completion" entries.

### Phase 2 (complete): Concrete adapters, human-share, and corpus import

Delivered shared adapter utilities, RSS/Atom, local and structured corpus adapters, human-share, Telegram channel, Reddit, Source Ingestion-owned durable marker persistence, and cross-adapter manager coverage while keeping public dataclasses stable and avoiding a Memory Store dependency. Reviewed and completed. See DEVLOG "Phase 3.2 Completion" entry.

## Module 4: Gateway (complete)

Planned phases followed `ARCH_gateway.md`: first stabilize the public Gateway contract, validation, adapter registry, outbound routing, local log adapter, and listener callback semantics with fake/local adapters; then add concrete Telegram delivery and polling behavior through the toolkit boundary.

### Phase 1 (complete): Gateway contract and adapter foundation

Delivered ARCH-aligned Gateway dataclasses/errors/exports, config validation, internal adapter registry/lifecycle, outbound routing, local log delivery, fake inbound/feedback dispatch, callback exception isolation, and bounded in-memory delivery tracking. Reviewed and completed. See DEVLOG "Phase 4.1 Completion" entry.

### Phase 2 (complete): Telegram adapter delivery and polling

Delivered concrete Telegram adapter construction behind an injectable toolkit boundary, outbound text/markdown/thread/telegraph delivery, non-blocking polling and inbound normalization, feedback normalization for replies/reactions/edits, mixed Telegram/log integration hardening, and regression coverage for unsupported Telegraph delivery. Reviewed and completed. See DEVLOG "Phase 4.2 Completion" entry.

## Module 5: Generator + Output Router (complete)

Planned phases followed `ARCH_generator.md`: first stabilize the public contract, errors, exports, Memory Store context-loading boundary, empty-personality behavior, and deterministic Output Router behavior without live generation; then add LLM generation/response/free-play behavior, skeptical memory verification, and prompt/parse hardening.

### Phase 1 (complete): Contract and routing foundation

Delivered ARCH-aligned public dataclasses/errors/exports, stateless Memory Store personality context loading, empty-personality behavior, optional Tier 2 enrichment behind Memory Store boundaries, deterministic Output Router delivery decisions, and credential-free fake integration coverage. Reviewed and completed. See DEVLOG "Phase 5.1 Completion" entry.

### Phase 2 (complete): LLM generation modes and skeptical memory

Delivered prompted, response, and free-play generation behind fakeable toolkit/llm_client boundaries; skeptical memory verification with read-only recent Tier 1 checks; provider-failure rotation fallback; parse hard stops; source attribution and response threading preservation; and cross-mode integration coverage. Reviewed and completed. See DEVLOG "Phase 5.2 Review" and "Phase 5.2 Completion" entries.

## Module 6: Distillation (complete)

Planned phases follow `ARCH_distillation.md`: first stabilize the public contract, validation, Memory Store read/write boundary helpers, in-process lock, persisted run metadata, and deterministic gate evaluation without live clustering or LLM synthesis; then add T1->T2 RAPTOR promotion and assertion cache; then add T2->T3 reflect-evolve with supersession and criteria-adjustment output.

- **Phase 1 (complete)** — Delivered ARCH-aligned public dataclasses/errors/exports, config and Memory Store boundary validation, persisted run metadata, in-process locking, deterministic gate evaluation, deferred public distillation method stubs, and integration coverage proving no toolkit calls or Memory Store note writes outside metadata. Reviewed and completed. See DEVLOG "Phase 6.1 Review" and "Phase 6.1 Completion" entries.

- **Phase 2 (complete)** — Delivered ARCH-aligned `distill_t1_to_t2(config)`: toolkit boundary seams, feedback-aware Tier 1 selection, RAPTOR coherence gating, Tier 2 Memory Store writes with cluster links, assertion-cache JSON persistence, and successful-run metadata updates. Reviewed and completed. See DEVLOG "Phase 6.2 Completion" entry.

- **Phase 3 (complete)** — Delivered ARCH-aligned `distill_t2_to_t3(config)`: audited reflection output, evolution proposal parsing with version-count inertia, personality supersession and unchanged-version writeback, compression limits, feedback-derived criteria adjustments, success-only metadata updates, and end-to-end integration coverage. Reviewed and completed. See DEVLOG "Phase 6.3 Completion" entry.

<!--
HISTORY — Do not read past this marker.
Completed phase history below.
-->
