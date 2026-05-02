# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Each step gets a structured entry. This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD --> -->

<!-- Module 1 (Memory Store) entries archived 2026-04-29 — see DEVLOG_archive.md -->

## Module 2 Phase 1 Plan

**Date:** 2026-05-02
**Decision:** Planned Attention Filter Phase 1 as a Build phase for the public contract and deterministic scoring foundation.

Updated `DEVPLAN.md` to activate Module 2 Phase 1 with five implementation steps: package/dataclass scaffold, default criteria and validation, blend-weight calculation, structural scoring helpers, and focused unit tests. Updated `ARCHITECTURE.md` to mark Attention Filter in progress and logged D-16 in `DECISIONS.md`.

No source implementation was changed in this planning action.

## Module 1 Audit Closure

**Date:** 2026-05-02
**Decision:** Human audit recorded; Module 1 (Memory Store) is accepted as audited and complete.

Updated `DEVPLAN.md` Current Status to reflect that Module 1 is no longer only phase-complete but also audited complete. No implementation changes, test changes, or architecture changes were required.

## D-13: Remove Seeding Module

**Date:** 2026-05-01
**Decision:** D-13 Closed — eliminate the standalone Seeding module.

Corpus ingestion now happens through Source Ingestion adapters (5 new corpus adapter types: `corpus_livejournal`, `corpus_twitter`, `corpus_blog`, `corpus_conversations`, `corpus_text`). Personality develops exclusively through Distillation — the same mechanism used for day-to-day content. No separate batch pipeline.

The `seed_weight` config (fixed multiplier for Seeding-derived personality files) was replaced by **version-count inertia**: personality files that survive multiple T2→T3 cycles earn proportionally more resistance to change. Config: `inertia_per_cycle: float = 0.25`, `max_inertia: float = 3.0`. Effective weight = `min(max_inertia, 1.0 + (version_count - 1) * inertia_per_cycle)`. Superseded files reset to version_count=1; surviving files increment each cycle.

Bootstrap behavior documented in Orchestrator: when Tier 3 is empty, run ingestion and distillation activations, skip generation. Attention Filter operates on prompt criteria alone at zero density (`prompt_weight ≈ 1.0`). Corpus sources listed in `auto_accept_sources` bypass acceptance threshold during initial import.

**Files changed:** DECISIONS.md, ARCHITECTURE.md, ARCH_distillation.md, ARCH_attention_filter.md, ARCH_generator.md, ARCH_source_ingestion.md, ARCH_memory_store.md, ARCH_orchestrator.md, PROJECT.md, DEVPLAN.md, CLAUDE.md, CODEX.md, .llms/rules/phosphene.md.
**File deleted:** ARCH_seeding.md.
**Implementation sequence renumbered:** 10 modules → 9. Module 2 is now Attention Filter.
