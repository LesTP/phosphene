# Phosphene — Development Log Archive

## Active log entries archived 2026-05-08 before MVP.1 close

### Phase 7.1 Completion: Feedback Collector contract and immediate feedback foundation

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 7 Phase 1. Final verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/feedback_collector -q`
(27 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -q`
(574 passed).

Phase 7.1 delivered the ARCH-aligned Feedback Collector public contract,
in-memory output registration, immediate Gateway reaction/reply/forward
normalization, Tier 1 `source="feedback"` Memory Store note writes, silence
event recording, bounded record pruning, and positive-feedback unresolvedness
bumps for linked Tier 1 source notes. Delayed engagement remains deferred to
Phase 7.2.

DEVLOG learning review: Phase 7.1 landed linearly through planning, five
implementation steps, and review. No repeated trial-and-error pattern needs
promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 7.1 entries recorded no contract changes. D-48
documents the immediate-feedback boundary and delayed-engagement deferral
without upstream contract propagation.
DEVPLAN cleanup: reduced Phase 7.1 to a one-line completion summary and set
frontmatter blocked state.
ARCHITECTURE.md: updated Feedback Collector status to "Phase 7.1 complete".
DECISIONS.md and PROJECT.md: no open decisions or project risks were resolved
by this phase.

### Phase 7.1 Review: Feedback Collector contract and immediate feedback foundation

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Phase 7.1 against `ARCH_feedback_collector.md`. Must fix: none.
Should fix: none. Optional: none deferred. The implementation preserves the
Phase 7.1 scope: ARCH-aligned public dataclasses and exports, in-memory output
tracking, immediate Gateway feedback normalization, Tier 1 Memory Store
feedback-note writes, silence detection, bounded pruning, and Tier 1
unresolvedness bumps for positive feedback.

Delayed engagement remains intentionally deferred to Phase 7.2 per DEVPLAN.
Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest
tests/feedback_collector` (27 passed) and
`PYTHONPATH=src:.python_deps python3 -m pytest tests/` (574 passed).

### Step 7.1.5: Integration and regression

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added Feedback Collector phase integration coverage that exercises the real
Gateway `DeliveryResult` / `FeedbackSignal`, Generator `GeneratorOutput` /
Output Router, and Memory Store `NoteInput` / `NotePatch` boundaries together.
The new regression stores a Tier 1 source note, routes a generated output
through a fake Gateway boundary, registers the delivered message, processes a
reply signal, verifies the stored Tier 1 `source="feedback"` note, checks
retention-criteria propagation, and confirms positive-feedback unresolvedness
updates persist through Memory Store.

Added public-boundary import coverage so Feedback Collector imports cleanly
alongside the Gateway, Generator, and Memory Store types it consumes. No runtime
contract changes were made. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/feedback_collector`
(27 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/`
(574 passed).

### Step 7.1.4: Silence detection and unresolvedness updates

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `FeedbackCollector.check_silence()` for tracked outputs that pass
the configured silence window without feedback. The collector now records a
single Tier 1 `source="feedback"` silence note per eligible output, marks the
record as silence-recorded, returns the generated `FeedbackEvent`, and prunes
records older than twice the silence window.

Positive immediate feedback now calls
`update_unresolvedness_on_feedback()`, which reloads linked source notes,
bumps unresolvedness by `0.1` only for notes still in Tier 1, and caps the
value at `1.0` through the Memory Store `NotePatch` boundary. Replies and
forwards honor the existing config flags when deciding whether they are
positive for unresolvedness purposes.

Added focused tests for silence-event storage, one-shot silence behavior,
feedback suppression of silence, old-record pruning, Tier 1-only
unresolvedness bumps, and capping. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/feedback_collector`
(25 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/`
(572 passed).

### Step 7.1.3: Immediate Gateway feedback signal processing

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `FeedbackCollector.process_signal()` for tracked Gateway feedback.
The collector now ignores unknown message ids, unsupported signal types, and
unrecognized reactions; classifies positive reactions as likes, negative
reactions as dislikes, and Gateway replies/forwards as immediate feedback
events; appends returned `FeedbackEvent` objects to the in-memory output
record; and stores each event as a Tier 1 Memory Store `NoteInput` with
`source="feedback"`, ARCH tags, source-note links, and signal-specific
importance.

Added focused tests covering positive reaction note storage, dislike/reply/
forward classification, and ignored untracked or unsupported signals.
Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest
tests/feedback_collector` (20 passed) and `PYTHONPATH=src:.python_deps python3
-m pytest tests/` (567 passed).

### Step 7.1.2: Output registration and retention criteria

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `FeedbackCollector.register_output()` for the successful Gateway
delivery path. The collector now ignores failed deliveries and successful
deliveries without a `message_id`, maps tracked message ids to `OutputRecord`
metadata from `GeneratorOutput`, stamps the in-memory delivery time, and keeps
tracking state only in the collector's `output_records` map.

Retention criteria are derived from Memory Store source-note tags using the
known Attention Filter retention criteria, preserving first-seen source order
and deduplicating repeated criteria. Missing or unreadable source notes are
ignored so registration remains non-throwing per the ARCH contract.
Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/`
(560 passed).

### Step 7.1.1: Feedback Collector public package contract

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the `phosphene.feedback_collector` package with ARCH-aligned
`FeedbackEvent`, `FeedbackCollectorConfig`, `OutputRecord`, and
`FeedbackCollector` exports. The collector now exposes the public constructor
and method signatures for output registration, signal processing, silence
checks, delayed-engagement checks, and unresolvedness updates while later
steps fill in behavior.

Added focused tests for package exports, dataclass field order, default values,
collector construction, method availability, and config validation for timing
windows, reaction lists, and boolean policy flags. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/` (556 passed).

### Phase 7.1 Plan: Feedback Collector contract and immediate feedback foundation

**Date:** 2026-05-07
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Activated Module 7 Phase 1 as a Build phase. The phase is scoped to the
Feedback Collector public contract, in-memory output registration, immediate
Gateway feedback normalization, Memory Store Tier 1 feedback-event writes,
silence detection, record pruning, and positive-feedback unresolvedness bumps
for linked Tier 1 source notes.

Delayed engagement is explicitly deferred to Module 7 Phase 2 because it
depends on later graph/reference heuristics rather than the immediate
Gateway callback path. Updated ARCHITECTURE.md to mark Feedback Collector
in progress and logged scope decision D-48. No tests were run because this
was a planning-only action.

### Phase REVIEW_HARDENING.1 Completion: Attention Filter additions

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Pre-Module-7 Hardening Phase A. Final verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter -v`
(134 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -v`
(533 passed).

Phase A delivered the ARCH-specified Attention Filter hardening additions:
`wild_card_ratio` and `near_miss_margin` config validation,
`FilterResult.near_misses` and `FilterResult.wild_cards`, below-threshold
wild-card sampling tagged with `retention_criteria=["wild_card"]`, fully
annotated near misses within the configured margin, and `rejected_count`
accounting that excludes both exploratory buckets.

DEVLOG learning review: Phase A landed linearly across three implementation
steps and review. No repeated trial-and-error pattern needs promotion to
DEVPLAN Gotchas.
Contract Changes scan: Step 1 recorded public dataclass alignment with the
already-updated `ARCH_attention_filter.md` contract; no unpropagated upstream
document or built-consumer contract work remains.
Log review: loop logs show successful progression through the three steps and
review. No repeated tool failures or wasted-turn patterns were found beyond the
already documented no-`rg` environment constraint.
DEVPLAN cleanup: reduced Phase A to a one-line completion summary and set
frontmatter to await human audit before Phase B.
ARCHITECTURE.md: no Implementation Sequence status change was needed; the
Attention Filter module was already marked Complete before this hardening phase.

### Phase REVIEW_HARDENING.1 Review: Attention Filter additions

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Pre-Module-7 Hardening Phase A against `ARCH_attention_filter.md`.
Must fix: none. Should fix: none. Optional: no optional changes deferred.

The implemented contract surface includes `wild_card_ratio` and
`near_miss_margin` on `AttentionFilterConfig`, `near_misses` and `wild_cards`
on `FilterResult`, below-threshold wild-card sampling tagged with
`retention_criteria=["wild_card"]`, near-miss annotation for remaining
within-margin candidates, and `rejected_count` exclusion for both buckets.
Attention Filter remains read-only against Memory Store.

Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter -v`
(134 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -v`
(533 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete
is the next action.

### Step REVIEW_HARDENING.1.3: Export and integration check

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Verified the Attention Filter hardening additions at the package-contract and
cross-module boundaries. `tests/attention_filter/test_exports.py` confirms the
public dataclass surface includes `wild_card_ratio` and `near_miss_margin` on
`AttentionFilterConfig`, plus `near_misses` and `wild_cards` on `FilterResult`;
`src/phosphene/attention_filter/__init__.py` continues to export the
ARCH-specified public config/result classes.

No implementation changes were needed in this step. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter -v`
(134 passed) and the cross-module regression
`PYTHONPATH=src:.python_deps python3 -m pytest tests/ -v` (533 passed).

### Step REVIEW_HARDENING.1.2: Filter logic

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the Attention Filter below-threshold partitioning for wild-card
accepts and near-miss recording. `filter_content` now samples wild cards from
below-threshold candidates, preserves result order after sampling, annotates
wild cards with `retention_criteria=["wild_card"]`, annotates near misses from
the remaining within-margin candidates, and keeps true rejects as count-only.

Added focused regression coverage for zero wild-card ratio, full wild-card
admission, wild-card tagging and annotation, near-miss margin selection,
zero near-miss margin, rejected-count exclusion, unchanged accepted/auto-accepted
behavior, and no Memory Store writes. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter -v`
(134 passed).

### Step REVIEW_HARDENING.1.1: Config and types

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** Attention Filter public dataclasses now match the ARCH-specified hardening fields.

Added `wild_card_ratio` and `near_miss_margin` to `AttentionFilterConfig` with
unit-interval and non-negative validation respectively. Added `near_misses` and
`wild_cards` to `FilterResult`, and updated the current `filter_content` return
paths to populate empty lists until the Step 2 partitioning logic is
implemented.

Updated Attention Filter config/export tests for the new dataclass fields,
defaults, and validation boundaries. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter -v`
(130 passed).

### Step 6.3.1: Reflection input preparation and feedback metrics

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the first T2->T3 preparation boundary inside `DistillationEngine`.
`distill_t2_to_t3(config)` now acquires the consolidation lock, queries Tier 2
pattern notes in chronological order, raises `NoPatternDataError` before
feedback work when no patterns exist, and prepares optional Tier 1
`source="feedback"` events without LLM calls, Memory Store writes, personality
context reads, supersession, or run-metadata updates.

Added deterministic per-criterion feedback metrics for the later
criteria-adjustment path. Feedback tags of the form `criterion:<name>` or
`criterion=<name>` are normalized into criterion names, `friction_target`
events contribute to the `friction` criterion, and each metric records feedback
count, engaged count, engagement rate, and mean engagement from bounded
importance/unresolvedness scores. Focused tests cover pattern querying,
disabled feedback, absent-pattern errors, concurrent lock rejection, lock
release, no-write behavior, and criterion metric normalization. Verification
passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation`
(53 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (496 passed).

### Step 6.3.2: Reflection LLM prompt and parsing

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the reflection LLM boundary for the T2->T3 path. `distill_t2_to_t3(config)` now prepares Tier 2 patterns and feedback metrics under the consolidation lock, builds a strict JSON reflection request, calls the private fakeable LLM completion seam at `config.reflection_tier`, and captures request messages, raw response, and parsed `ReflectionInsight` records as a private audit artifact before the later evolution/writeback steps.

Added strict reflection parsing for the ARCH insight shape: non-empty content, known `source_pattern_ids`, allowed insight types (`recurring_tension`, `new_pattern`, `evolution`, `contradiction`), and probability-bounded confidence. Malformed reflection payloads fail with `DistillationError`; provider failures propagate from the LLM seam; no Memory Store writes, personality context reads, supersession, cache writes, or T2->T3 metadata updates occur in this step. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (62 passed).

### Step 6.3.3: Evolution request, inertia, and proposal parsing

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the evolution proposal boundary for the T2->T3 path. After the
reflection audit artifact is parsed, `distill_t2_to_t3(config)` now loads the
current Memory Store personality context, normalizes personality files, computes
effective version-count inertia with the ARCH formula, builds the evolution LLM
request with reflection insights and personality content, calls the fakeable LLM
completion seam at `config.evolution_tier`, and parses proposals before any
Memory Store writeback.

Added strict evolution-response parsing for supersede, unchanged, and criteria
adjustment proposals. Malformed JSON, unknown or duplicated personality ids,
invalid actions, missing supersession content/title/summary, and malformed
criteria-adjustment fields now fail with `DistillationError` before supersession,
unchanged-note updates, run metadata updates, or criteria output assembly. Focused
tests cover inertia calculation, request payload shape, evolution-tier LLM
wiring, proposal parsing, malformed-response rejection, lock release, and the
no-write/no-metadata-update boundary. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (73 passed).

### Step 6.3.4: Personality writeback and metadata

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the T2->T3 personality writeback path. `distill_t2_to_t3(config)` now
applies accepted supersession proposals through `memory_store.supersede`, returns
`SupersessionRecord` audit records with old ids, new ids, and change summaries,
increments unchanged personality files by updating `version_count:<n>` tags
through `memory_store.update_note`, and advances only the T2->T3 run timestamp
after all writes succeed.

Added pre-write compression validation for supersession proposals. The engine
computes the reduction across superseded personality content and raises
`DistillationError` before any Memory Store write when the reduction exceeds
`config.max_compression_ratio`, preserving the existing metadata timestamp and
releasing the consolidation lock. Focused tests cover unchanged writeback,
supersession audit records, compression rejection before writes, and successful
metadata updates. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (75 passed) and
`PYTHONPATH=src:.python_deps python3 -m pytest` (518 passed).

### Step 6.3.5: Criteria adjustments and end-to-end integration

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Completed `EvolutionResult` assembly for the T2->T3 path by deriving returned
`CriteriaAdjustment` records from deterministic feedback evidence instead of
trusting criteria proposals from the evolution LLM response. Criteria with at
least two feedback events are compared against the eligible feedback baseline;
consistently above-baseline criteria receive bounded weight increases, and
below-baseline criteria receive bounded decreases with evidence strings
recording mean engagement, feedback count, and baseline.

Added focused end-to-end coverage for mixed superseded/unchanged personality
output, feedback-derived criteria adjustments, unchanged version-count
increments, supersession audit records, success-only metadata updates, and lock
release. Added failure coverage proving evolution provider errors propagate
without Memory Store writes or T2->T3 metadata updates and release the
consolidation lock. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (78 passed)
and `PYTHONPATH=src:.python_deps python3 -m pytest` (521 passed).

### Phase 6.3 Review: T2->T3 reflect-evolve

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Distillation Phase 3 against `ARCH_distillation.md`. Must fix: the
evolution proposal parser allowed an LLM response to omit an existing
personality file, which meant omitted files would neither supersede nor receive
the unchanged `version_count` increment required by the T2->T3 cycle. Added
strict coverage validation so every current personality file must appear as
`supersede` or `unchanged` before any writeback can proceed.

Should fix: none beyond the required parser hardening. Optional: no optional
changes deferred. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (79 passed)
and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (522 passed).
DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next
action.


### Phase 6.3 Completion: T2->T3 reflect-evolve

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 6 Phase 3 and Module 6 Distillation. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (79 passed).

Phase 3 delivered the `distill_t2_to_t3(config)` implementation behind the `ARCH_distillation.md` public contract: deterministic Tier 2 and feedback preparation, reflection LLM request/parsing with auditable `ReflectionInsight` output, evolution request/proposal parsing with version-count inertia, strict proposal coverage for every personality file, personality supersession through Memory Store, unchanged-note `version_count` increments, compression-cap enforcement before writes, feedback-derived criteria adjustments, success-only T2->T3 metadata updates, and end-to-end integration coverage.

DEVLOG learning review: Phase 6.3 landed linearly across five implementation steps and review. Review found one must-fix parser coverage issue: omitted personality files could skip both supersession and unchanged `version_count` increments. The fix was applied during review by requiring every current personality file to be proposed as `supersede` or `unchanged` before writeback. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 6.3 step, review, and completion entries recorded "Contract changes: None"; D-45 and D-46 document the reflect-evolve boundary and coverage validation without upstream contract propagation.
Log review: Phase 6.3 loop logs show successful progression through plan, five steps, and review. No repeated tool failures or wasted-turn patterns were found beyond the already documented no-`rg` environment constraint.
DEVPLAN cleanup: reduced Module 6 Phase 3 to a one-line completion summary and set frontmatter to await human audit before Module 7 planning.
ARCHITECTURE.md: Distillation row in the Implementation Sequence table updated from "Phase 2 complete" to "Complete".

### Phase 6.1 Plan: Distillation contract, gates, and metadata foundation

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 6 Phase 1 as a Build phase over the Distillation control-plane foundation: public dataclasses, errors, exports, config validation, Memory Store boundary checks, in-process consolidation lock, persisted run metadata, deterministic gate evaluation, and no-toolkit-call integration hardening.

Scope decision recorded in D-43: Phase 1 keeps RAPTOR clustering, embedding calls, LLM reflection/evolution, assertion-cache writes, and Tier 2/Tier 3 Memory Store mutations out of scope so later synthesis phases build on a credential-free, tested run-control boundary.

### Step 6.1.1: Public dataclasses, errors, and exports

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the initial `phosphene.distillation` package with ARCH-aligned public dataclasses for `DistillationConfig`, `GateStatus`, `TierPromotionResult`, `ReflectionInsight`, `SupersessionRecord`, `CriteriaAdjustment`, and `EvolutionResult`. Added the Distillation error hierarchy and a constructor-only `DistillationEngine` shell that stores the Memory Store dependency without performing validation, toolkit calls, gate checks, metadata writes, or synthesis behavior.

Export coverage now verifies the public package surface, dataclass field order, default values, constructor behavior, and error inheritance. `DistillationConfig` is keyword-only so the ARCH field order can be preserved while keeping required toolkit configs after defaulted fields. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (3 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (446 passed).

### Step 6.1.2: Config validation and engine construction

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added Distillation config validation for required toolkit config objects, non-null LLM rotation entries, non-negative run cadence, positive Tier 1 volume and T2->T3 cycle thresholds, non-negative inertia growth, minimum max-inertia bounds, and probability-bounded compression/coherence thresholds. Validation is local and does not import or call toolkit services.

Added `DistillationEngine` construction checks for the Memory Store read/write surface needed by later metadata, gate, and promotion steps: `query_notes`, `store_note`, `update_note`, `add_links`, `get_personality_context`, `supersede`, and a `vault_path` attribute for persisted distillation metadata. Focused tests cover invalid config values, rotation presence checks, valid fake-store construction, missing store methods, and missing metadata vault path. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (15 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (458 passed).

### Step 6.1.3: Distillation metadata persistence

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added private Distillation run metadata helpers backed by a JSON file at `.phosphene/distillation_runs.json` under the Memory Store vault. The helper record tracks last T1->T2 and T2->T3 run timestamps, creates the metadata directory on write, writes through a temporary file before replace, and treats missing, unreadable, invalid JSON, non-object, or field-level malformed metadata as never-run values instead of failing gate evaluation setup.

Focused tests cover missing metadata, round-trip persistence, malformed file handling, independent malformed field handling, and the boundary that metadata helpers do not call Memory Store note APIs. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (19 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (462 passed).

### Step 6.1.4: Lock boundary

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added a private in-process consolidation lock helper to `DistillationEngine` for future T1->T2 and T2->T3 operations. The helper acquires non-blocking, raises `DistillationLockError` when another run is active, releases deterministically through a context manager, and exposes a private lock-state check for next-step gate reporting without touching Memory Store notes or toolkit services.

Focused tests cover acquire/release behavior, nested acquisition rejection, exception-safe release, and the no-Memory-Store-note-API boundary. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (22 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (465 passed).

### Step 6.1.5: Gate evaluation

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented public `DistillationEngine.check_gates(config) -> GateStatus` using persisted run metadata, Memory Store `NoteQuery` reads, and the in-process lock state. Gate evaluation now reports never-run behavior, elapsed time since the latest distillation run, pending Tier 1 volume since the last T1->T2 run, monthly T2->T3 readiness when Tier 2 patterns exist, aggregate volume readiness, and lock-gate blocking without acquiring the run lock.

Kept the boundary credential-free and read-only against Memory Store note state: `check_gates` performs only tier queries and metadata reads, with no toolkit calls or Memory Store writes. Focused tests cover never-run T1 readiness, Tier 1 since-filtering, recent-run time blocking, monthly T2->T3 readiness, and lock-gate reporting. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (27 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (470 passed).

### Step 6.1.6: Foundation integration hardening

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added phase-level Distillation foundation integration coverage that exercises engine construction, metadata persistence, and `check_gates()` together while using callable toolkit sentinels that fail if invoked. The integration store records query shape and rejects all Memory Store content-write methods, verifying the Phase 1 boundary remains credential-free and read-only against note state except for the private metadata file.

Added public error export coverage for the Distillation error hierarchy so `DistillationConfigError`, `DistillationLockError`, `InsufficientDataError`, and `NoPatternDataError` remain available from the package API and continue to share `DistillationError` as their base class. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (29 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (472 passed).

### Phase 6.1 Review: Distillation contract, gates, and metadata foundation

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Distillation Phase 1 against `ARCH_distillation.md`. Must fix: `DistillationEngine` exposed `check_gates()` but not the two ARCH-declared public distillation methods, which would produce `AttributeError` for callers before the synthesis phases. Added explicit `distill_t1_to_t2(config)` and `distill_t2_to_t3(config)` stubs with ARCH return annotations and clear deferred-phase failures, preserving the public method surface without adding toolkit calls or Memory Store note writes.

Should fix: none beyond refreshing the engine docstring to describe the current Phase 1 control-plane boundary. Optional: no optional changes deferred. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (32 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (475 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next action.

### Phase 6.1 Completion: Distillation contract, gates, and metadata foundation

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 6 Phase 1. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (32 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (475 passed).

Phase 1 delivered the Distillation control-plane foundation behind the `ARCH_distillation.md` public contract: public dataclasses, error exports, config validation, Memory Store boundary checks, private metadata persistence, in-process consolidation locking, deterministic gate evaluation, explicit deferred public distillation method stubs, and phase-level integration coverage proving no toolkit calls or Memory Store note writes outside private metadata.

DEVLOG learning review: Phase 6.1 landed linearly across planning, six implementation steps, and review. Review found one must-fix public-surface gap: `DistillationEngine` needed explicit `distill_t1_to_t2` and `distill_t2_to_t3` stubs before synthesis phases. The fix was applied during review; no repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 6.1 plan, step, review, and completion entries recorded "Contract changes: None"; D-43 documents the foundation boundary without upstream contract propagation.
Log review: Phase 6.1 loop logs show successful step progression and no new repeated tooling failure beyond the already documented no-`rg` environment constraint.
DEVPLAN cleanup: reduced Module 6 Phase 1 to a one-line completion summary and set frontmatter to await human audit before Module 6 Phase 2 planning.
ARCHITECTURE.md: Distillation row in the Implementation Sequence table updated from "In progress" to "Phase 1 complete".

### Phase 6.2 Plan: T1->T2 RAPTOR promotion and assertion cache

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 6 Phase 2 as a Build phase over `DistillationEngine.distill_t1_to_t2(config)`: toolkit boundary wrappers, Tier 1 selection and feedback preparation, RAPTOR clustering and coherence gating, Tier 2 note writes and cluster links, assertion-cache JSON persistence, and phase-level integration hardening.

Scope decision recorded in D-44: Phase 2 is limited to T1->T2 promotion. T2->T3 reflect-evolve behavior, personality supersession, version-count inertia, compression caps, and criteria-adjustment output remain deferred to Phase 3 so cluster formation and assertion-cache ownership can stabilize first.

### Step 6.2.1: Toolkit boundary and prompt helpers

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added private Distillation toolkit seams for embedding, RAPTOR clustering, and LLM completion with lazy imports so `phosphene.distillation` remains import-compatible when `toolkit` is absent. Added RAPTOR callback factories for cluster summarization and summary re-embedding, plus JSON prompt builders for Tier 1 cluster summaries and Tier 2 assertion-cache extraction.

Focused tests cover the private import seams, fakeable LLM and embedding callback wiring, vector extraction from embedding results, and strict assertion-cache prompt shape without making live toolkit calls. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (37 passed).

### Step 6.2.2: Tier 1 input selection and feedback preparation

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the lock-protected `distill_t1_to_t2` entry path through the scoped Phase 2 preparation boundary. The method now acquires the consolidation lock, reads last T1->T2 metadata, queries pending Tier 1 notes in chronological order, filters feedback events out of cluster input material, raises `InsufficientDataError` before downstream work when content volume is too low, and releases the lock on both normal deferred continuation and errors.

Added deterministic feedback boost preparation for `source="feedback"` Tier 1 events when enabled. Feedback links and `friction_target` references contribute bounded importance boosts to referenced input notes without Memory Store writes, toolkit calls, run metadata updates, or cluster synthesis. Focused tests cover since-query shape, disabled feedback, insufficient data, concurrent lock rejection, no-write behavior, and boost clamping. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (40 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (483 passed).

### Step 6.2.3: RAPTOR clustering and coherence gating

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the T1->T2 clustering path through the scoped Step 6.2.3 boundary. `distill_t1_to_t2(config)` now embeds prepared Tier 1 note content through the private embedding seam, constructs RAPTOR clustering callbacks, passes note texts into the clustering seam, normalizes cluster outputs, computes mean pairwise cosine similarity per cluster, and returns `TierPromotionResult` counts for coherent promoted members, explicit/unassigned noise, incoherent clusters, tree depth, and processed feedback events.

Kept Tier 2 Memory Store writes, cluster links, assertion-cache persistence, and run metadata updates deferred to later Phase 2 steps. Added focused clustering tests for callback wiring, coherent versus incoherent split behavior, noise labels, and no-write behavior, while updating preparation tests now that the public method advances past the previous deferred stub. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (42 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (485 passed).

### Step 6.2.4: Tier 2 note writes and cluster links

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented Tier 2 Memory Store writes for coherent T1->T2 clusters. `distill_t1_to_t2(config)` now builds promotion records with source Tier 1 note ids, summary text, mean importance/unresolvedness, coherence-derived attractor relevance, and centroid embeddings. New clusters are written with `NoteInput(tier=2)`, `cluster_group`, source links, and a distilled-pattern tag; existing Tier 2 notes with the same `cluster_group` are updated through `NotePatch` while preserving existing title, links, and tags.

Added related-cluster wiring after all coherent clusters are materialized by calling `add_links` between promoted Tier 2 note ids. Noise and incoherent Tier 1 notes remain unmodified, and assertion-cache persistence and run metadata updates remain deferred to later Phase 2 steps. Updated clustering/preparation tests to cover new cluster creation, existing cluster updates, source-link preservation, related-cluster links, label-result fallback summaries, and the new Tier 2 query. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (43 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (486 passed).

### Step 6.2.5: Assertion cache persistence

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented Tier 2 assertion-cache persistence for coherent T1->T2 cluster promotions. `distill_t1_to_t2(config)` now extracts assertions from each new or updated cluster summary through the private LLM completion seam, validates strict JSON assertion payloads, writes per-cluster cache files under `vault/tier2/{cluster_group}.json`, and returns refreshed cluster groups in `TierPromotionResult.assertion_cache_updated`.

Malformed assertion extraction payloads now fail with clear `DistillationError` messages before any cache file is written for the batch, and each cache write uses a temporary file followed by replace. Focused tests cover cache content, cache update result ids, fake LLM boundary wiring in existing T1->T2 paths, and malformed-payload atomicity. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (44 passed).

### Step 6.2.6: Phase integration hardening

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added phase-level T1->T2 integration coverage using fake Memory Store, embedding, clustering, and LLM completion services. The integration path now exercises Tier 1 selection through coherent cluster promotion, Tier 2 note creation, source links, assertion-cache writes, result counts, and successful run metadata persistence while preserving any existing T2->T3 run timestamp.

Hardened success-only metadata behavior by updating `last_t1_to_t2_run` only after Memory Store writes and assertion-cache persistence complete. Added regression coverage that toolkit embedding failures propagate unchanged, do not write Tier 2 notes or links, do not advance T1->T2 run metadata, and release the consolidation lock. Added explicit coverage that `distill_t2_to_t3(config)` remains deferred to Phase 3. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (490 passed).

### Phase 6.2 Review: T1->T2 RAPTOR promotion and assertion cache

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Distillation Phase 2 against `ARCH_distillation.md`. Must fix: assertion extraction happened after Tier 2 Memory Store writes, so a malformed assertion-cache LLM payload could leave cluster notes written while run metadata remained unadvanced. Moved assertion-cache payload extraction before Tier 2 note writes so the synthesis phase fails before Memory Store mutation, then kept cache-file writes after notes are materialized.

Should fix: tightened the malformed assertion-cache regression to assert no Tier 2 note writes, no cluster links, no cache directory, and lock release on failure. Optional: no optional changes deferred. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (490 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next action.

### Phase 6.2 Completion: T1->T2 RAPTOR promotion and assertion cache

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 6 Phase 2. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/distillation` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (490 passed).

Phase 2 delivered the `distill_t1_to_t2(config)` implementation behind the `ARCH_distillation.md` public contract: private toolkit boundary seams for embedding, RAPTOR clustering, and LLM calls with lazy imports for import-time compatibility; feedback-aware Tier 1 selection with importance boost preparation; RAPTOR coherence gating with mean pairwise similarity per cluster; Tier 2 Memory Store note creation and update with source Tier 1 links and related-cluster wiring; assertion-cache JSON persistence with atomic writes and pre-write extraction validation; and successful-run metadata updates only after all Memory Store writes and cache files complete.

DEVLOG learning review: Phase 6.2 landed linearly across planning, six implementation steps, and review. Review found one must-fix ordering issue: assertion-cache LLM extraction was happening after Tier 2 Memory Store writes, so a malformed payload could leave cluster notes written while run metadata remained unadvanced. The fix was applied during review — move extraction before writes, keep cache-file writes after notes are materialized. No repeated trial-and-error patterns across steps; no new Gotchas to promote.
Contract Changes scan: All Phase 6.2 step, review, and completion entries record "Contract changes: None"; D-44 documents the scope boundary without upstream contract propagation.
Log review: Iteration 132 (review) ran 51 turns, which is high. No new repeated tool failures beyond the already-documented no-`rg` constraint. Iteration 133 exited immediately (exit=1, 0 turns) — that aborted run is the predecessor to this completion iteration; no pattern to promote.
DEVPLAN cleanup: reduced Module 6 Phase 2 to a one-line completion summary and updated frontmatter to `blocked: "awaiting-human-audit"` before Phase 3 planning.
ARCHITECTURE.md: Distillation row in the Implementation Sequence table updated from "Phase 1 complete" to "Phase 2 complete".


(Module 5 Phase 2 and earlier entries archived to DEVLOG_archive.md on 2026-05-06.)

## Pre-Module-7 Hardening archived 2026-05-07

### Phase REVIEW_HARDENING.2 Completion: Unresolvedness composite utility + network diagnostics

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Pre-Module-7 Hardening Phase B. Final verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/ -q` (547 passed).

Phase B delivered the pure caller-fed `phosphene.scoring.compute_unresolvedness()`
utility, configurable `UnresolvednessWeights`, and `tools/network_diagnostics.py`
as a standalone Memory Store diagnostic report for density, cluster diversity,
outlier ratio, bridge-node density, unresolvedness distribution, compression
damage, and RAPTOR-vs-structural divergence.

DEVLOG learning review: Phase B landed linearly through planning, three
implementation steps, and review. The review found two small should-fix cleanups
that were resolved in the review iteration; no repeated trial-and-error pattern
needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase B entries recorded no contract changes. D-47 keeps
the scorer and diagnostics outside existing module contracts; no upstream
document or built-consumer propagation remains.
Log review: loop summary entries for iterations 148-152 show successful Phase B
planning, steps, and review. No repeated tool failures or wasted-turn patterns
were found beyond the already documented no-`rg` environment constraint.
DEVPLAN cleanup: reduced Phase B to a one-line completion summary and set
frontmatter to await human audit before Module 7 planning.
ARCHITECTURE.md: no Implementation Sequence status change was needed; this was
pre-module hardening, and Module 7 remains Not started.
DECISIONS.md and PROJECT.md: no open decisions or project risks were resolved by
this phase.

### Phase REVIEW_HARDENING.2 Review: Unresolvedness composite utility + network diagnostics

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Pre-Module-7 Hardening Phase B against phosphene.md Sections 7.3,
7.7, and 7.10. Must fix: none. Should fix: align the unresolvedness helper's
public type annotation with its supported Memory Store search-result tuple
inputs, and make the diagnostics Louvain path fall back cleanly when an
installed `community` package lacks `best_partition`. Optional: no optional
changes deferred.

Applied the should-fix cleanup in `src/phosphene/scoring/unresolvedness.py`,
`tools/network_diagnostics.py`, and
`tests/tools/test_network_diagnostics.py`. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/scoring/test_unresolvedness.py tests/tools/test_network_diagnostics.py -q`
(14 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -q`
(547 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase
Complete is the next action.

### Step REVIEW_HARDENING.2.3: Integration and cross-module regression

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Completed the Phase B integration and regression check. The full test suite
passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -v`
(546 passed), including the new `phosphene.scoring` package tests and existing
module suites.

Verified that `phosphene.scoring` imports cleanly and exports
`UnresolvednessWeights` and `compute_unresolvedness`. Also verified the
diagnostics tool runs as a standalone script against `/tmp/test_vault` with
`PYTHONPATH=src:.python_deps python3 tools/network_diagnostics.py --vault-path /tmp/test_vault`,
producing the empty-vault diagnostic report without errors.

### Step REVIEW_HARDENING.2.2: Network diagnostics tool

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added `tools/network_diagnostics.py`, a standalone Memory Store diagnostic
script with `--vault-path` and `--embedding-path` arguments and a formatted
stdout report. The tool computes note/tier density summary, Tier 2 centroid
cluster diversity, Tier 1 outlier ratio, bridge-node density, unresolvedness
histogram, orphaned-link compression damage, and RAPTOR-vs-structural community
divergence. Mirror index and free-play value ratio are reported as N/A until
Generator output logs exist.

The Louvain path uses `networkx` and `python-louvain` when available and falls
back to deterministic connected structural communities in this environment,
where those optional graph packages are not installed. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/tools/test_network_diagnostics.py -q`
(5 passed).

### Step REVIEW_HARDENING.2.1: Unresolvedness composite utility

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the shared `phosphene.scoring` package with a pure
`compute_unresolvedness()` utility and configurable `UnresolvednessWeights`.
The scorer computes the Phase B composite from rising Tier 1 links without
promotion, unresolved reappearance among high-similarity notes, mutually
friction-targeted connected notes, and Tier 1 survival toward the base decay
deadline. It remains caller-fed and does not call Memory Store.

The exact DEVPLAN signature lacks similarity scores and retention-day config,
so the implementation preserves the three positional inputs while supporting
keyword-only weights, retention days, deterministic `now`, and pass-through
`(MemoryNote, similarity)` search-result tuples. Verification passed with
`PYTHONPATH=src:.python_deps python3 -m pytest tests/scoring/test_unresolvedness.py tests/memory_store/test_types.py -q`
(18 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests/ -q`
(541 passed).

### Phase REVIEW_HARDENING.2 Plan: Unresolvedness composite utility + network diagnostics

**Date:** 2026-05-06
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Activated Pre-Module-7 Hardening Phase B as a Build phase. The phase is scoped
to a pure `phosphene.scoring` unresolvedness composite utility, a standalone
Memory Store network diagnostics tool, and one integration/regression step.

The scorer stays caller-fed and side-effect-free, and the diagnostics script
remains an operator tool rather than a new ARCH module or exported runtime
dependency. Logged scope decision D-47. No tests were run because this was a
planning-only action.

## Module 4 Phase 2 archived 2026-05-05

### Phase 4.2 Plan: Telegram adapter delivery and polling

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 4 Phase 2 as a Build phase over concrete Telegram Gateway behavior behind the existing internal adapter protocol. The plan starts by replacing the pending Telegram adapter with an injectable toolkit boundary, then implements outbound delivery, polling/inbound normalization, feedback normalization, and mixed-platform integration hardening.

Scope decision recorded in D-38: Phase 2 must keep public Gateway dataclasses stable and use credential-free fake toolkit clients for tests. Live credential smoke tests remain outside the autonomous loop until credentials and an integration harness exist.

### Step 4.2.1: Telegram adapter construction and toolkit boundary

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Replaced the pending Telegram placeholder with a concrete internal `TelegramGatewayAdapter` registered under the existing `telegram` adapter type. The adapter constructs and holds a toolkit-backed client through a private injectable factory while preserving the public Gateway dataclasses and existing adapter protocol.

Added a default toolkit import boundary that raises `PlatformConfigError` when `toolkit.telegram_client` is unavailable, and normalized private factory failures through Gateway construction as `PlatformConfigError`. Focused tests cover credential-free construction with a fake client, non-callable factory rejection, factory failure wrapping, and valid Telegram/log config construction without live credentials. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (37 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (383 passed).

### Step 4.2.2: Outbound Telegram delivery

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented Telegram outbound delivery behind the existing internal adapter protocol. The adapter now routes `text` and `thread` messages through toolkit-style `send_message`, routes `markdown` through the toolkit API boundary with Telegram parse-mode payload support, and prefers supported long-message/Telegraph client helpers for `telegraph` before falling back to normal delivery.

The delivery path maps platform message IDs into `DeliveryResult`, preserves reply metadata in Telegram payloads, keeps intent tags available through Gateway recent-delivery tracking, supports async toolkit methods, and converts client/API failures into failed delivery results. Focused fake-client tests cover text, thread, markdown, telegraph, metadata preservation, recent-delivery attribution, and failure conversion. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (41 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (387 passed).

### Step 4.2.3: Polling listener lifecycle and inbound normalization

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented non-blocking Telegram listener polling behind the existing internal adapter protocol. The Telegram adapter now starts a daemon polling thread, supports idempotent start/stop through Gateway lifecycle state, honors `listen=False` at the Gateway boundary, and signals toolkit polling shutdown when the client exposes `stop_polling`.

Added private normalization helpers for toolkit-normalized Telegram updates and raw Bot API update dictionaries, producing Gateway `InboundMessage` values with content, platform, message ID, sender, timestamp, reply target, reactions when present, and raw payload metadata. Callback exception isolation remains Gateway-owned through the existing dispatch wrappers. Focused fake-client tests cover polling delivery, inbound normalization, non-blocking/idempotent lifecycle behavior, `listen=False`, and callback exception recording. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (45 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (391 passed).

### Step 4.2.4: Telegram feedback signal normalization

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Extended the Telegram polling path to normalize feedback events alongside inbound messages without changing public Gateway dataclasses. Raw Telegram reaction updates now emit `FeedbackSignal(signal_type="reaction")`, reply messages emit `signal_type="reply"` against the replied-to message ID, and edited messages emit `signal_type="edit"` against the edited message ID. Toolkit-normalized feedback objects are also supported through the same private boundary.

The adapter now forwards `on_feedback` through the existing Gateway-owned dispatch wrapper, so feedback callback failures are isolated and recorded consistently with inbound callback failures. Raw update dictionaries are preserved on emitted feedback signals as adapter-owned metadata for downstream attribution while the public dataclass field list remains stable. Focused fake-client tests cover reactions, replies, edits, sender/timestamp normalization, raw metadata preservation, and feedback callback exception isolation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (393 passed).

### Step 4.2.5: Gateway Telegram integration hardening

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added end-to-end fake-client Gateway coverage for mixed Telegram/log platform configs. The new tests verify Telegram default delivery through the injected toolkit boundary, local log delivery in the same Gateway instance, recent-delivery tracking keyed by Telegram platform message IDs, and log-adapter tracking without cross-platform interference.

Added mixed-platform listener cleanup coverage showing Gateway starts both enabled adapters, stops the Telegram polling thread through the fake toolkit client's shutdown hook, clears all listening platform state, and leaves the output-only log adapter without file side effects. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (49 passed).

### Phase 4.2 Review: Telegram adapter delivery and polling

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Gateway Phase 2 against `ARCH_gateway.md`. Must fix: prevent requested `telegraph` delivery from silently falling back to plain Telegram sends when the toolkit client does not expose a supported long-content/Telegraph method. Should fix: none beyond that correctness hardening. Optional: no optional changes deferred.

Added focused regression coverage for unsupported Telegraph delivery and verified the full Gateway suite with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (50 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next action.

### Phase 4.2 Completion: Telegram adapter delivery and polling

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 4 Phase 2. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (50 passed).

Phase 2 delivered concrete Telegram Gateway behavior behind the existing internal adapter protocol: injectable toolkit-client construction, credential-free fake-client coverage, outbound `text`, `markdown`, `thread`, and `telegraph` delivery with platform message IDs, non-blocking polling lifecycle, inbound message normalization, feedback normalization for reactions/replies/edits, mixed Telegram/log integration coverage, listener cleanup, and bounded recent-delivery tracking. The Phase Review must-fix for unsupported Telegraph delivery was resolved with regression coverage; requested `telegraph` sends now fail explicitly when no supported long-content/Telegraph client method exists.

DEVLOG learning review: Phase 4.2 landed linearly across plan, five implementation steps, and review. The only review finding was a correctness hardening for unsupported Telegraph delivery, fixed in review with a focused regression test. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 4.2 plan, step, and review entries recorded "Contract changes: None"; D-38 documents the existing-adapter-contract boundary, and no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 4 Phase 2 iterations 91-97 completed without repeated tool failures or wasted-turn patterns. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 2 to a one-line completion summary and set frontmatter to await human audit before Module 5 planning.
ARCHITECTURE.md: Gateway row in the Implementation Sequence table updated from "Phase 2 in progress" to "Complete".

## Module 3 Phase 1.5 archived 2026-05-05

### Step 3.1.5.infra: Coverage tooling baseline

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added `pytest-cov` to the project dev dependency set and installed it into the existing `.python_deps/` target for the documented non-venv test workflow. No `src/` or `tests/` files were modified.

Captured the baseline coverage report with `PYTHONPATH=src:.python_deps python3 -m pytest tests/ --cov=src/phosphene --cov-report=term-missing`; 310 tests pass. Overall coverage is 98%.

Module coverage baseline:
- `memory_store`: 507 statements, 8 missed, 98% coverage.
- `attention_filter`: 485 statements, 14 missed, 97% coverage.
- `source_ingestion`: 197 statements, 2 missed, 99% coverage.

No module is below the 80% follow-up threshold.

## Phase 3.1.5 Review — Coverage Tooling Infra

**Date:** 2026-05-04
**Regime:** Build
**Mode:** autonomous
**Outcome:** Reviewed Module 3 Phase 1.5 against its instrumentation-only scope; no must-fix or should-fix changes were required.

Validated that the phase added `pytest-cov` to project dev dependencies, captured a reproducible baseline coverage report, and avoided `src/` or `tests/` modifications. The baseline remains above the 80% follow-up threshold for `memory_store`, `attention_filter`, and `source_ingestion`.

Tests passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/ --cov=src/phosphene --cov-report=term-missing` (310 passed, 98% total coverage).

### Findings
- Must fix: none.
- Should fix: none.
- Optional: none recorded.

### Phase 3.1.5 Completion: Coverage tooling infra

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed the Module 3 Phase 1.5 coverage-tooling infra boundary. Final verification ran the full test suite with the coverage command: `PYTHONPATH=src:.python_deps python3 -m pytest tests/ --cov=src/phosphene --cov-report=term-missing`; 310 tests pass with 98% total coverage.

Phase 1.5 retired the deferred coverage-tooling investment in `ARCHITECTURE.md`: `pytest-cov` is now part of dev dependencies, the existing `.python_deps` workflow supports coverage runs, and the baseline records `memory_store` at 98%, `attention_filter` at 97%, and `source_ingestion` at 99%. No module is below the 80% follow-up threshold.
DEVLOG learning review: Phase 3.1.5 landed linearly across one instrumentation step and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 3.1.5 step and review entries recorded no contract changes. D-32 documents the instrumentation-only acceptance; no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 3 Phase 1.5 iterations 70-71 completed without escalations or repeated tool failures. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 1.5 to a one-line completion summary, kept Module 3 active, and cleared active frontmatter pending human audit before Module 3 Phase 2 planning.
ARCHITECTURE.md: Source Ingestion row in the Implementation Sequence table updated from "Phase 1 complete" to "Phase 1.5 complete"; Deferred Test Investments coverage-tooling row marked complete with baseline numbers.

<!-- Archived module entries from DEVLOG.md.
     Active development entries live in DEVLOG.md; only completed-module
     entries are moved here per the archival rule in GOVERNANCE.md. -->

## Module 1: Memory Store

### Step 1: Project bootstrap, types, and errors

Mode: Build
Outcome: Complete
Contract changes: None

Created the Python package skeleton for `phosphene.memory_store`, including `pyproject.toml`, the public package exports, the Memory Store dataclasses, and the exception hierarchy required by `ARCH_memory_store.md`. Added focused tests for dataclass defaults and construction, full `NoteInput` optional-field acceptance, and exception construction/catching through `MemoryStoreError`.

The step introduced no contract changes. Verification passed for the targeted tests under the available Python 3.11 interpreter because Python 3.12 is not installed in this container.

### Step 2: Vault I/O primitives

Mode: Build
Outcome: Complete
Contract changes: None

Implemented the private `phosphene.memory_store.vault` helpers for deterministic note id generation, tiered markdown paths, YAML-frontmatter serialization, and parsing back to `MemoryNote`. Markdown bodies are preserved literally, including wikilinks, YAML-looking content, unicode, multiline text, and `---` lines. Embeddings are intentionally omitted from markdown and parse back as `None`, matching the Phase 1 boundary.

Added focused vault tests for id format, stability, distinct timestamp inputs, slug truncation, tier path construction, minimal and fully populated round-trips, embedding omission, and special-character content preservation. Verification passed for `tests/memory_store` under the available Python 3.11 interpreter with isolated dependencies because Python 3.12 is not installed in this container.

### Step 3: `MemoryStore` constructor and `store_note`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `phosphene.memory_store.store.MemoryStore` with vault initialization, tier directory creation, writable-path validation, accepted-but-unused `embedding_path`, and `store_note` persistence through the existing vault serializer. `store_note` now validates tier, title length, importance, and unresolvedness; generates note ids from the creation timestamp; writes notes to the configured tier directory; and sets Phase 1 computed fields with outbound-only `link_count` and no `decay_deadline`.

Exported `MemoryStore` from the package public API and added focused tests for constructor behavior, tiered writes, serialized note fields, validation failures, boundary values, and deterministic same-second distinct ids. Verification passed for `tests/memory_store` under Python 3.11 with dependencies installed into `/tmp/phosphene-testdeps`; Python 3.12 is still not installed in this container.

### Step 4: `get_note` and `update_note`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `MemoryStore.get_note` and `MemoryStore.update_note` for vault-backed single-note reads and partial updates. `get_note` searches all three tier directories and raises `NoteNotFoundError` when absent. `update_note` validates patched titles and score fields, applies non-`None` patch values, replaces `links` and `tags` wholesale, refreshes `updated_at`, recomputes Phase 1 outbound-only `link_count`, writes the note back to markdown, and returns the updated `MemoryNote`.

Added `tests/memory_store/test_crud.py` covering store/get round-trips, independent field updates, full replacement of links and tags, empty patch timestamp refresh, missing-note errors, invalid patch validation, and file content persistence. Verification passed for `tests/memory_store` under Python 3.11 with dependencies installed into `/tmp/phosphene-testdeps`; Python 3.12 is still not installed in this container.

### Phase 1 Review: Core data model and CRUD

Mode: Build
Outcome: Review complete
Contract changes: None

Reviewed the Phase 1 Memory Store implementation against `ARCH_memory_store.md` and the DEVPLAN phase boundary. The public dataclasses and exception hierarchy are present, `MemoryStore` exposes the Phase 1 constructor, `store_note`, `get_note`, and `update_note` signatures, vault-backed markdown persistence matches the documented tier layout, and deferred Phase 2/3/4 behaviors remain outside the implementation surface.

Findings:
- Must fix: None.
- Should fix: None.
- Optional: None.

Verification could not run in this container because `pytest` is not installed and the available interpreter is Python 3.11.2 while the project requires Python 3.12+.

### Phase 1 Completion: Core data model and CRUD

Mode: Build
Outcome: Complete
Contract changes: None

Closed Phase 1 of Memory Store. Final verification ran the full `tests/memory_store` suite via the documented gotcha pattern (`PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`); 49 tests pass. The earlier review entry's "verification could not run" note reflected the pre-gotcha state of this container; the gotcha now lives in the DEVPLAN Cold Start Summary, so future iterations can run the suite directly.

DEVLOG learning review: no trial-and-error patterns across Steps 1–4. Each step landed on first implementation. The only operational friction recorded was the Python 3.11/`.python_deps/` install pattern, which is already captured as a Cold Start Gotcha — no new Gotchas to promote.

Contract Changes scan: every Phase 1 entry recorded "Contract changes: None". `ARCH_memory_store.md` already encodes the deferred Phase 2/3/4 surface; no upstream propagation required.

DEVPLAN cleanup: reduced the Phase 1 detail block to a one-line summary referencing this entry. The four-phase Module 1 outline at the head of the section is preserved for orientation, with Phase 1 marked complete and Phase 2 marked next.

ARCHITECTURE.md: Memory Store row in the Implementation Sequence table updated from "In progress (Phase 1)" to "Phase 1 complete".

Frontmatter reset for next phase: `phase: 2`, `phase_title: Index layer and queries`, `step: null`, `mode: Discuss`, `review_done: false`.

### Step 1: Index data model, rebuild on init, `get_index`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented the private `phosphene.memory_store.index` module with an `Index` object that tracks note metadata, markdown paths, outbound links, and derived inbound counts. `MemoryStore` now rebuilds the index during construction, refreshes it after `store_note` and `update_note`, raises `VaultError` on duplicate note ids across tier directories, and exposes `get_index(tier=None)` with tier validation, public `IndexEntry` projection, inbound-plus-outbound `link_count`, and newest-first ordering.

Added `tests/memory_store/test_index.py` covering empty vaults, constructor rebuild across tiers, tier filtering and invalid tier errors, immediate store/update visibility, duplicate id detection, and inbound count refresh after link changes. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store` under Python 3.11.2 using the repo-local dependency target documented in DEVPLAN.

### Step 2: Inbound link counts on `MemoryNote`; index-backed reads

Mode: Build
Outcome: Complete
Contract changes: None

Retrofitted `MemoryStore.get_note` and `MemoryStore.update_note` to resolve notes through the in-memory index path rather than scanning tier directories. Returned `MemoryNote.link_count` now reflects inbound plus outbound links while markdown frontmatter remains outbound-only, preserving stable disk round trips. `update_note` writes the outbound-only count, refreshes the index, and returns the inbound-augmented note.

Extended `tests/memory_store/test_index.py` for `get_note` inbound counts, link-removal propagation through `update_note`, and restart recovery after deliberate in-memory inbound-count drift. Existing CRUD missing-note and outbound-only fixture behavior remains covered. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store` under Python 3.11.2 using the repo-local dependency target documented in DEVPLAN.

### Step 3: `query_notes`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `MemoryStore.query_notes` against the in-memory index, including tier validation, index-side filtering for tier, minimum scores, tags, source, and created-at windows, full note loading for matches, inbound-augmented `link_count`, validated ordering, descending/ascending sort direction, and limit truncation.

Added `tests/memory_store/test_query.py` with fixed-timestamp vault fixtures spanning all tiers. Coverage includes each independent filter, combined filters, all supported ordering fields in both directions, limit behavior, invalid tier and invalid `order_by` rejection, empty result sets, and returned-note link counts. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store` under Python 3.11.2 using the repo-local dependency target documented in DEVPLAN.

### Phase 2 Completion: Index layer and queries

Mode: Build
Outcome: Complete
Contract changes: None

Closed Phase 2 of Memory Store. Final verification ran the full `tests/memory_store` suite via `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 75 tests pass.

Phase 2 delivered the in-memory index layer, startup index rebuild, incremental index refresh after writes, duplicate note-id detection, public `get_index`, index-backed `get_note` and `update_note`, inbound-plus-outbound `MemoryNote.link_count`, restart recovery from in-memory inbound drift, and `query_notes` filtering, ordering, and limiting.

DEVLOG learning review: no trial-and-error implementation pattern appeared across the Phase 2 step entries. Each step recorded successful verification with the documented `.python_deps` test invocation.

Contract Changes scan: Phase 2 entries recorded "Contract changes: None". The phase fulfilled the existing `ARCH_memory_store.md` Phase 2 contract; no upstream document propagation was required.

Log review: the loop log shows one failed Claude iteration caused by an organization monthly usage limit before repository changes were made. The next Codex review iteration reconstructed state from files and completed cleanly. No project gotcha was promoted because this was an external quota interruption, not a repeatable repository workflow issue.

DEVPLAN cleanup: reduced the Phase 2 step plan to a one-line completion summary referencing this entry. The four-phase Module 1 outline remains as the active Memory Store roadmap, with Phase 3 ready for its own Phase Plan.

ARCHITECTURE.md: Memory Store row in the Implementation Sequence table updated from "Phase 1 complete" to "Phase 2 complete".

Frontmatter reset for next phase: `phase: 3`, `phase_title: Embedding search and graph operations`, `step: null`, `mode: Discuss`, `review_done: false`.

### Step 1: Embedding persistence (binary storage)

Mode: Build
Outcome: Complete
Contract changes: None

Implemented private sidecar embedding persistence in `phosphene.memory_store.embeddings` using `numpy.save` and `numpy.load` keyed by note id. `MemoryStore.store_note` and `MemoryStore.update_note` now write embeddings when both an embedding vector and `embedding_path` are present, while `embedding_path=None` preserves the existing accepted-but-discarded behavior. `get_note`, `query_notes`, and `update_note` return notes hydrated from sidecar files, leaving markdown frontmatter unchanged.

Added `tests/memory_store/test_embedding_persistence.py` for store/get round-trips, update overwrite behavior, missing embeddings, mixed query results, null embedding paths, restart loading, and lazy sidecar directory creation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 82 tests pass.

### Step 2: `search_by_embedding`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `MemoryStore.search_by_embedding` over the existing index and sidecar embedding store. The method validates optional tier filters, returns an empty list when no embedding storage is configured, skips notes without stored vectors, excludes zero-norm query or stored vectors from results, checks vector shapes before comparison, computes cosine similarity with numpy, loads full `MemoryNote` objects through the existing read path, and returns similarity-ranked tuples truncated by `limit`.

Added `tests/memory_store/test_search.py` for cosine ranking, tier filtering, limit truncation, mixed embedded/plain vaults, dimension mismatch errors, missing embedding storage, vaults with no stored embeddings, invalid tier validation, zero-norm exclusion, returned embeddings, and inbound-augmented link counts. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 92 tests pass.

### Step 3: `add_links`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `MemoryStore.add_links` for index-validated graph writes. The method treats empty target lists as a no-op, validates the source and all non-self targets before touching disk, preserves existing outbound link order, appends only new target ids, silently drops self-links, refreshes `updated_at` on real changes, serializes the source note, and re-registers it so inbound counts update immediately.

Added `tests/memory_store/test_links.py` covering outbound link addition, duplicate and existing-link deduplication, inbound-plus-outbound link counts, missing-source and missing-target atomicity, empty-list no-op behavior, self-link dropping, and restart reload of augmented links. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 100 tests pass.

### Step 4: `get_linked`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented graph traversal for `MemoryStore.get_linked`. The method validates depth in the ARCH-defined range, raises `NoteNotFoundError` for unknown origins, performs breadth-first traversal across both outbound links and inbound sources, excludes the origin and already visited notes, ignores dangling outbound ids that are not present in the index, and returns full `MemoryNote` objects through the existing read path so embeddings and inbound-augmented `link_count` are populated.

Added `Index.inbound_for(note_id)` as a private helper exposing inbound source ids from the existing index state. Extended `tests/memory_store/test_links.py` for direct inbound/outbound neighbors, depth-2 and depth-3 traversal, BFS ordering, deduplication across paths, cycles, origin exclusion, invalid depth, missing origins, isolated notes, and returned embeddings/link counts. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 109 tests pass.

### Step 5: `get_personality_context`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented `MemoryStore.get_personality_context` for current Tier 3 personality files. The method rebuilds the index on each call so it reads the vault fresh, excludes Tier 3 notes superseded by another Tier 3 note's `supersedes` pointer, loads returned notes through the existing read path so embeddings and inbound-augmented `link_count` are populated, and derives a deterministic SHA-1 `version_id` from sorted `note_id|updated_at` pairs.

Extended the private `IndexedNote` record with `supersedes` while leaving the public `IndexEntry` contract unchanged. Added `tests/memory_store/test_personality_context.py` for empty contexts, Tier 3 inclusion, supersession exclusion, Tier 1/2 exclusion, stable and changing version ids, returned embeddings/link counts, and fresh disk reads between calls. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 117 tests pass.

### Phase 3 Review: Embedding search and graph operations

Mode: Review
Outcome: Review complete
Contract changes: None

Reviewed Phase 3 Memory Store implementation against `ARCH_memory_store.md`, the DEVPLAN Phase 3 step plan, and the prior decision log. All five steps land their public surfaces with matching signatures and error semantics: `search_by_embedding` (cosine ranking, tier filter, dimension check, zero-norm exclusion, empty-when-no-store), `add_links` (atomic pre-validation, dedup, self-link drop, empty no-op, restart durability), `get_linked` (BFS over outbound and inbound, depth bounds, dangling-id filtering, origin exclusion, cycle safety), `get_personality_context` (fresh per-call rebuild, supersession exclusion via `IndexedNote.supersedes`, deterministic SHA-1 `version_id`, empty-state hash matches `da39…0709`). Embedding persistence is wired through `store_note`, `update_note`, `get_note`, `query_notes`, `search_by_embedding`, `get_linked`, and `get_personality_context`; `embedding_path=None` preserves Phase 1's accepted-but-not-persisted behavior. No frontmatter format change; D-11's outbound-only on-disk `link_count` rule still holds (inbound augmentation only happens at the public read boundary). The `Index.inbound_for` helper is private; `IndexEntry` public contract is unchanged.

Verification: `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store` — 117 tests pass on Python 3.11.2 with `.python_deps`.

Findings:
- Must fix: None.
- Should fix: None.
- Optional (skipped — see D-12):
  - `update_note` (store.py:192) sets `note.link_count = len(note.links)` inside the `patch.links is not None` branch, then unconditionally re-sets it at line 205. Dead but harmless.
  - `search_by_embedding` (store.py:154 + 167) loads each matched note's embedding twice — once explicitly to score, then again via `_load_note`. Performance-only; sidecar reads are cheap.
  - `get_linked` (store.py:258) calls `_load_note(current_id)` during BFS expansion when `self._index.entries[current_id].links` would suffice. Performance-only; the terminal `_load_note` for returned ids is correct since they need full `MemoryNote` materialization.

DEVPLAN frontmatter updated: `review_done: true`. No upstream contract propagation required (Contract Changes scan: every Phase 3 step entry recorded "Contract changes: None"; ARCH already encoded the Phase 3 surface). Phase Complete is the next action.

### Phase 3 Completion: Embedding search and graph operations

Mode: Build
Outcome: Complete
Contract changes: None

Closed Phase 3 of Memory Store. Final verification ran the full suite with the documented test command: `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 117 tests pass on Python 3.11.2 with `.python_deps`.

DEVLOG learning review: Phase 3 landed linearly across five implementation steps and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas. The optional review cleanups were explicitly skipped in D-12, not failed attempts.

Contract Changes scan: every Phase 3 step and review entry recorded "Contract changes: None". Phase 3 fulfilled the existing `ARCH_memory_store.md` contract for sidecar embeddings, embedding search, graph operations, and personality context loading; no upstream propagation required.

Log review: `logs/loop/summary.log` shows Phase 3 iterations 14-20 completed successfully without repeated tool failures. No transcripts were present under the project tree. No Phase 3 operational Gotchas to promote.

DEVPLAN cleanup: removed the Phase 3 step plan from active DEVPLAN content and left a one-line completion summary referencing this entry. `DEVLOG.md` is 205 lines before this entry, below the archive threshold, so no archive was created.

ARCHITECTURE.md: Memory Store row in the Implementation Sequence table updated from "Phase 2 complete" to "Phase 3 complete".

Frontmatter reset for next phase: `phase: 4`, `phase_title: Decay, supersession, and density metrics`, `step: null`, `mode: Discuss`, `review_done: false`.

### Step 1: `get_density_metrics`

Mode: Build
Outcome: Complete
Contract changes: None

Implemented index-backed density metrics for Memory Store Phase 4. `IndexedNote` now carries private `cluster_group` metadata populated from `MemoryNote`, with no public `IndexEntry` change. `MemoryStore.get_density_metrics()` computes note count, always-present tier counts, mean inbound-plus-outbound link degree, Tier 2 distinct cluster count, strict unresolvedness threshold count, and max unresolvedness directly from the in-memory index without markdown reads.

Added `tests/memory_store/test_density.py` covering empty vault zeros, mixed-tier counts, hand-computed link-degree averaging, Tier 2-only cluster counting, strict `unresolvedness > 0.5`, max unresolvedness across tiers, and immediate metric updates after storing notes and calling `add_links`. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 124 tests pass.

### Step 2: `supersede`

Mode: Build
Outcome: Complete
Contract changes: `MemoryNote.change_summary` added; `ARCH_memory_store.md` updated; D-14 logged.

Implemented Tier 3 supersession for the Memory Store. `MemoryNote` now carries a defaulted `change_summary` field that round-trips through markdown frontmatter. `MemoryStore.supersede()` validates source existence, Tier 3 scope, duplicate supersession, and replacement title length before writing; creates a new Tier 3 note with inherited metadata and embedding sidecar; records the old note id in `supersedes`; stores the audit summary on the new version; and schedules the old version for decay using `tier3_superseded_retention_days`.

Added `tests/memory_store/test_supersede.py` covering readable old/new versions, change-summary placement, metadata and embedding carry-forward, old-note decay deadlines, error paths, no-write title validation, personality-context replacement semantics, and parse/reload persistence. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 136 tests pass.

### Step 3: `run_decay` Tier 1 rules

Mode: Build
Outcome: Complete
Contract changes: None

Implemented the first `MemoryStore.run_decay()` slice for Tier 1 notes and the `DecayReport` return path. Tier 1 retention now uses the configured base window, switches to the extended window when inbound links meet `link_density_threshold`, applies the attractor multiplier, expires only on strict `now - created_at > retention`, and reports extended-but-surviving notes separately from expired notes.

Added private embedding and note expiry cleanup: `delete_embedding()` removes sidecar vectors as a no-op when absent or disabled, and `MemoryStore._expire_note()` deletes markdown, deletes the sidecar, removes the index entry, and rebuilds inbound counts. Added `tests/memory_store/test_decay.py` covering empty reports, base expiry, link-density extension, extended-window expiry, attractor extension, exact-boundary survival, deleted-id/index consistency, idempotent reruns, and survivor sidecars. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 145 tests pass.

### Step 4: `run_decay` Tier 2 and Tier 3 rules

Mode: Build
Outcome: Complete
Contract changes: `MemoryStoreConfig.tier2_cycle_window_days` added; `ARCH_memory_store.md` updated; D-15 logged.

Extended `MemoryStore.run_decay()` to cover all tiers. Tier 2 notes now expire strictly after two configured cycle windows from `created_at`, independent of inbound links or attractor relevance. Tier 3 notes expire only when they carry a `decay_deadline` and the current time is past it, so current non-superseded personality files remain pinned. `DecayReport.expired_ids`, `expired_count`, and `tier_breakdown` now aggregate expirations across tiers 1, 2, and 3 while `extended_count` remains Tier 1-only.

Extended `tests/memory_store/test_decay.py` for Tier 2 window expiry/survival, Tier 2 link and attractor irrelevance, Tier 3 superseded/current retention semantics, mixed-tier reports, Tier 1-only extension counting, and density metrics after a sweep. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 154 tests pass.

### Phase 4 Review: Decay, supersession, and density metrics

Mode: Review
Outcome: Review complete
Contract changes: `ARCH_memory_store.md` Tier 2 decay rule cell rewritten to match D-15 (doc-only correction; no code or signature change).

Reviewed Phase 4 Memory Store implementation against `ARCH_memory_store.md`, the DEVPLAN Phase 4 step plan, and decisions D-14/D-15. All four steps land their public surfaces with matching signatures and error semantics: `get_density_metrics` (index-only, all six fields, all three tier keys always present, strict `unresolvedness > 0.5`, distinct Tier 2 cluster groups, post-store/post-`add_links` immediacy), `supersede` (Tier 3 only, AlreadySupersededError on re-supersede, TitleTooLongError before write, metadata + embedding carry-forward, `change_summary` only on the new version, `decay_deadline = now + tier3_superseded_retention_days` on the old version, `get_personality_context` excludes superseded and includes new), and `run_decay` (Tier 1 base/extended/attractor multiplicative window with strict `>` boundary, Tier 1 extended-but-surviving counted in `extended_count`, Tier 2 strict age-only at `2 × tier2_cycle_window_days`, Tier 3 expiry only when `decay_deadline` is set and past, embedding sidecars deleted alongside markdown, idempotent reruns). Public-API drift is bounded to `MemoryNote.change_summary` (D-14) and `MemoryStoreConfig.tier2_cycle_window_days` (D-15) — both pre-approved by the step plan. `IndexedNote.cluster_group` is private; `IndexEntry` is unchanged. Supersession chain semantics align with `get_personality_context`: a Tier 3 note is treated as superseded iff some other Tier 3 entry's `supersedes` points at it, which means a freshly stored `supersedes != None` new version is the visible one and the old id drops out of the personality set.

Verification: `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store` — 154 tests pass on Python 3.11.2 with `.python_deps`.

Findings:
- Must fix: None.
- Should fix:
  - `ARCH_memory_store.md` Tier 2 decay rule cell said "Distillation may extend retention via `update_note` (importance/attractor_relevance) ahead of the second window", but D-15 and the implementation ignore inbound links and `attractor_relevance` for Tier 2 expiry, and `update_note` cannot patch `created_at`. Rewrote the cell to read "Tier 2 expiry is age-only — inbound links and `attractor_relevance` are ignored (D-15). Distillation must promote, retier, or otherwise act on the note before the second window if it should be retained." Documentation-only correction; no code or test change.
- Optional (skipped — same posture as D-12, performance-only with no measured hotspot):
  - `run_decay` calls `self._load_note(note_id)` for every entry to read `attractor_relevance` and `decay_deadline`, even though Tier 2 expiry only needs the index entry. Saves at most one sidecar/markdown read per Tier 2 note per sweep; revisit if a consumer profiles run_decay.
  - `_expire_note` calls `self._index.rebuild_inbound()` once per expired note, making a single sweep O(N × E) where E is the per-call rebuild cost. Only matters when many notes expire simultaneously; current expected per-sweep expiration counts are a handful of Tier 1/2 notes.

D-12's Phase 3 optional skips were re-checked: Phase 4's `get_density_metrics` is purely index-driven and does not restructure `_load_note` or per-entry index access, so there was no opportunity to fold those cleanups in during this phase. They remain skipped under D-12.

DEVPLAN frontmatter updated: `review_done: true`. No upstream contract propagation required (Steps 1–4 contract changes are confined to D-14, D-15, and the ARCH cell rewrite, all already encoded in `ARCH_memory_store.md`). Phase Complete is the next action.

### Phase 4 Completion: Decay, supersession, and density metrics

Mode: Build
Outcome: Complete
Contract changes: None (all Phase 4 contract changes — D-14 `MemoryNote.change_summary`, D-15 `MemoryStoreConfig.tier2_cycle_window_days`, and the ARCH Tier 2 decay-rule rewrite — are already encoded in `ARCH_memory_store.md`).

Closed Phase 4 of Memory Store, which is also Module 1's final phase. Final verification ran the full suite with the documented test command: `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`; 154 tests pass on Python 3.11.2 with `.python_deps`.

Phase 4 delivered `get_density_metrics` (index-only, six fields, all three tier keys always present, strict `unresolvedness > 0.5`, distinct Tier 2 cluster groups), Tier 3 `supersede` (Tier 3 only, AlreadySupersededError on re-supersede, metadata + embedding carry-forward, `change_summary` only on the new version, retention deadline on the old version, `get_personality_context` exclusion of superseded notes), and `run_decay` (Tier 1 base/extended/attractor multiplicative window with strict `>` boundary, Tier 1 extended-but-surviving counted in `extended_count`, Tier 2 strict age-only at `2 × tier2_cycle_window_days`, Tier 3 expiry only when `decay_deadline` is set and past, embedding sidecars deleted alongside markdown, idempotent reruns).

DEVLOG learning review: Phase 4 landed linearly across four implementation steps and one review. No trial-and-error pattern needs promotion to DEVPLAN Gotchas. The review surfaced one documentation inconsistency (ARCH Tier 2 decay-rule cell pre-dating D-15) which was corrected in-review without code or test change. Optional review cleanups were skipped under D-12 posture, not failed attempts.

Contract Changes scan: Step 2 declared `MemoryNote.change_summary` (D-14), Step 4 declared `MemoryStoreConfig.tier2_cycle_window_days` (D-15), and the Phase 4 Review applied a documentation-only ARCH cell correction. All three are already encoded in `ARCH_memory_store.md`. No external module currently consumes Memory Store, so no downstream propagation is required; the additive `change_summary` field and new config option preserve all prior call sites.

Log review: `logs/loop/summary.log` shows Phase 4 iterations 22–27 (one Phase Plan, four Step, one Review) completed cleanly with no escalations, no repeated tool failures, and no wasted-turn patterns. No new operational Gotchas to promote.

DEVPLAN cleanup: reduced the Phase 4 step plan to a one-line completion summary referencing this entry. Module 1's four-phase outline now reads complete on all phases. `DEVLOG.md` is well below the 500-line archive threshold; no archive created.

ARCHITECTURE.md: Memory Store row in the Implementation Sequence table updated from "Phase 3 complete" to "Complete" — Module 1 is the first module to reach final-phase status.

Frontmatter reset: Module 1 final phase complete, so frontmatter is cleared (`module: null`, `phase: null`, `phase_title: null`, `step: null`, `mode: null`, `blocked: null`, `regime: null`, `review_done: null`). The next module's planning iteration will repopulate it.

<!-- Entries above archived from Module 1, 2026-04-29 -->

<!-- Entries archived from DEVLOG on 2026-05-05: Gateway Phase 4.1 and prior completed history -->

### Phase 4.1 Plan: Gateway contract and adapter foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 4 Phase 1 as a Build phase over the Gateway public contract and internal adapter foundation. The plan starts with ARCH-aligned dataclasses, errors, package exports, and config validation, then builds the adapter protocol/registry lifecycle, outbound send routing, local log delivery, and inbound/feedback callback dispatch using fake/local adapters only.

Scope decision recorded in D-36: live Telegram behavior is deferred to a later Gateway phase. Phase 1 should establish the reusable message-bus shape and local/fake testing surface without requiring credentials or external platform calls.

### Step 4.1.1: Public contract, errors, exports, and config validation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the `phosphene.gateway` package scaffold with ARCH-aligned public dataclasses, package exports, and a Gateway exception hierarchy. Added Gateway construction-time config validation for duplicate platform names, default-platform presence and enabled state, supported adapter types, required Telegram/log fields, enabled-platform filtering, and supported output format lists.

Kept this step to the public contract and validation boundary: adapter construction, listener lifecycle, outbound delivery, and callback dispatch remain deferred to the later Phase 1 steps already listed in DEVPLAN. Focused tests cover dataclass field order/defaults, package exports, valid Telegram/log configs, validation failures, and disabled non-default platform behavior. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (16 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (362 passed).

### Step 4.1.2: Adapter protocol, registry, and Gateway lifecycle foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the internal Gateway adapter protocol, immutable adapter factory registry, default fake/log/pending adapter factories, and Gateway-owned enabled-adapter construction without adding public API exports. Gateway construction now validates adapter support through the internal registry and normalizes private registry/factory failures to `PlatformConfigError`.

Implemented listener state bookkeeping with idempotent `start_listener`/`stop_listener`, `listen=False` handling, callback storage handoff to adapters, and platform connection error propagation via `PlatformConnectionError`. Kept outbound delivery and fake callback dispatch deferred to the later Phase 1 steps already listed in DEVPLAN. Focused tests cover fake adapter construction, invalid private factory rejection, listener start/stop idempotence, disabled listening, and connection failure wrapping. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (21 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (367 passed).

### Step 4.1.3: Outbound send routing and default delivery

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `Gateway.send` over the internal adapter protocol with enabled-platform lookup, output-format validation, outbound message handoff, and adapter delivery failure conversion into failed `DeliveryResult` values. `send_to_default` now uses the same route through the configured default platform while preserving format and intent tag fields on the outbound message.

Extended the internal fake/output-only adapter surface with deterministic send behavior for local tests while leaving real log-file delivery to Step 4.1.4. Focused tests cover target-platform routing, reply metadata and intent-tag preservation, platform-not-found and disabled-platform failures, unsupported format rejection, adapter delivery error conversion, and default-platform delivery. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (26 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (372 passed).

### Step 4.1.4: Local log adapter

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the concrete `log` Gateway adapter for local development output behind the existing internal adapter registry. The adapter uses `params["log_path"]`, creates parent directories as needed, appends one JSON record per outbound message, preserves content, format, reply target, intent tag, and metadata, and returns deterministic local message IDs for feedback attribution tests.

Kept the adapter output-only: listener start/stop hooks are no-ops and do not create inbound activity or persistent listener state beyond the Gateway lifecycle bookkeeping already established in Step 4.1.2. Focused tests cover log file creation, append ordering, metadata serialization, missing log-path validation through existing config coverage, and listener no-op behavior. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (29 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (375 passed).

### Step 4.1.5: Inbound and feedback callback dispatch harness

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added Gateway-owned inbound and feedback dispatch wrappers for listener adapters. The wrappers preserve adapter-provided `InboundMessage` and `FeedbackSignal` metadata, ignore dispatch after listener stop, and isolate callback exceptions by recording them on the Gateway so adapter listener loops can continue.

Extended the fake Gateway adapter with deterministic in-process inbound and feedback dispatch helpers, and added bounded in-memory recent-delivery tracking keyed by platform/message ID for later feedback attribution work. No persistent state or public API surface was added. Focused tests cover inbound dispatch, feedback dispatch, callback exception isolation, stopped-listener suppression, and bounded recent message mapping. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (34 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (380 passed).

### Phase 4.1 Review: Gateway contract and adapter foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Gateway Phase 1 against `ARCH_gateway.md`. Must fix: none. Should fix: removed one unused internal helper and import from `gateway.py`. Optional: no optional changes deferred.

The phase remains scoped to the public Gateway contract, validation, internal adapter registry, fake/local adapters, outbound routing, listener lifecycle, callback dispatch, and bounded in-memory delivery tracking. Live Telegram delivery and polling remain deferred to the later Gateway phase as planned in D-36.

### Phase 4.1 Completion: Gateway contract and adapter foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 4 Phase 1. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/gateway` (34 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (380 passed).

Phase 1 delivered the Gateway public contract and local/fake adapter foundation: ARCH-aligned dataclasses/errors/exports, config validation, internal adapter protocol and registry, lifecycle bookkeeping, outbound send routing, local log delivery, fake inbound and feedback callback dispatch, callback exception isolation, and bounded in-memory delivery tracking. Live Telegram delivery and polling remain deferred to the later Gateway phase per D-36.

DEVLOG learning review: Phase 4.1 landed linearly across plan, five implementation steps, and review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 4.1 plan, step, and review entries recorded "Contract changes: None"; D-36 and D-37 document the local/fake foundation boundary, and no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 4 Phase 1 iterations 83-89 completed without repeated tool failures or wasted-turn patterns. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 1 to a one-line completion summary and set frontmatter to await human audit before Gateway Phase 2 planning.
ARCHITECTURE.md: Gateway row in the Implementation Sequence table updated from "In progress" to "Phase 1 complete".

### Phase 3.2 Plan: Concrete adapters, human-share, and corpus import

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 3 Phase 2 as a Build phase over concrete Source Ingestion adapters while preserving the Phase 1 public manager/result contract. The plan starts with shared adapter utilities and registry hardening, then builds RSS/Atom, local corpus text/blog, structured corpus exports, human-share, Telegram channel, Reddit, and persistence/integration hardening.

Scope decision recorded in D-33: durable marker persistence remains Source Ingestion-owned during this phase. If implementing durable markers would require a Memory Store dependency or public cross-module contract change, the worker should record the issue during review rather than expanding dependencies inside the phase.

### Step 3.2.1: Shared adapter utilities and registry hardening

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added an internal `AdapterRegistry` seam for concrete/fake factory construction without changing the public `SourceIngestion(config)` API. The manager now validates and creates adapters through an immutable internal registry snapshot while preserving the existing private `_ADAPTER_REGISTRY` test override path.

Added shared Source Ingestion adapter utilities for URL fetching, HTML-to-text extraction, page title/link extraction, deterministic marker ordering, and adapter-local exception-to-error conversion. Link extraction continues to run before content truncation so linked URLs survive max-content clipping.

Focused tests cover concrete factory overrides, invalid factory rejection, adapter error conversion, HTML extraction, URL fetch success/failure behavior, truncation/link preservation, and marker ordering edge cases. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (41 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (318 passed).

### Step 3.2.2: RSS/Atom adapter

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the concrete `rss` adapter behind the existing Source Ingestion manager and registry contract. The adapter fetches feed XML with stdlib HTTP, parses RSS and Atom fixtures with stdlib XML, normalizes entry content through the shared HTML-to-text/link utilities, preserves title/author/url/timestamp metadata, advances deterministic last-seen markers, and reports fetch or parse failures inside `IngestionResult.errors`.

Kept the public `SourceIngestion(config)` API stable while allowing internal concrete factories to receive the global `IngestionConfig`; existing one-argument fake factory seams continue to work. Focused tests cover RSS fixtures, Atom fixtures, duplicate suppression by marker, malformed feed/error reporting, network failure conversion, and disabled adapter behavior. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (45 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (322 passed).

### Step 3.2.3: Local corpus text and blog adapters

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented local-file `corpus_text` and `corpus_blog` adapters behind the existing Source Ingestion manager/registry contract. The text adapter imports UTF-8 `.txt`/`.text` files from a file or recursive directory and splits content on paragraph boundaries. The blog adapter imports markdown or HTML archives according to the existing `params.format` value, preserving titles, author metadata where available, ISO publication timestamps where discoverable, local source paths, stable source fields, and extracted links.

Adapter failures remain inside `IngestionResult.errors`, including invalid archive paths and per-file parse/read errors. Last-seen marker advancement is deterministic for local archive items, and content truncation continues to happen through the shared normalization path so links survive max-content clipping. Focused tests cover plain text, markdown frontmatter, HTML metadata/link extraction, recursive directory import, invalid path reporting, marker suppression, and max-content truncation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (51 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (328 passed).

### Step 3.2.4: Structured corpus adapters

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented `corpus_livejournal`, `corpus_twitter`, and `corpus_conversations` behind the existing Source Ingestion manager/registry contract. LiveJournal imports reuse the local HTML archive parser with the `corpus_livejournal` source. Twitter/X imports support representative JSON and JavaScript archive files, normalize tweet timestamps/authors, fetch linked article content when available, preserve tweet text as `human_annotation`, keep expanded URLs in linked context, and report inaccessible linked URLs as per-item errors with an annotation fallback item. Conversation imports support JSON and text archives while preserving conversation title and message author metadata where available.

No public dataclasses or manager signatures changed. Last-seen markers remain adapter-local and deterministic for archive items. Focused tests cover minimal LiveJournal export parsing, linked-tweet fetch behavior, retweet/no-comment handling, inaccessible linked URL fallback, conversation metadata preservation, and marker advancement. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (57 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (334 passed).

### Step 3.2.5: Human-share adapter

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the concrete `human_share` adapter behind the existing Source Ingestion manager/registry contract. The adapter polls a dedicated Telegram toolkit boundary lazily, normalizes URL-only, URL-plus-text, and text-only share messages, preserves human annotations and sender metadata where available, fetches primary shared URLs through the shared page-fetch utility, and reports page-fetch failures as per-item errors while still producing a fallback `ContentItem` when the share itself has signal.

No public dataclasses or manager signatures changed. Last-seen markers remain manager-owned and adapter-local, and the toolkit dependency stays behind an internal boundary so tests use fake Telegram clients without importing external services. Focused tests cover fake Telegram messages for all three message shapes, page fetch success/failure, annotation/link preservation, marker advancement, and ignored non-target chats. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (62 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (339 passed).

### Step 3.2.6: Telegram channel and Reddit adapters

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented concrete `telegram_channel` and `reddit` adapters behind the existing Source Ingestion manager/registry contract. Telegram channel polling stays behind the toolkit Telegram client boundary, normalizes text, captions, and forwarded message content, extracts links through shared normalization, and reports API failures inside `IngestionResult.errors`.

Added a small internal Reddit HTTP/API boundary that normalizes subreddit listing posts for the existing `new`, `hot`, and `top` sort values. The Reddit adapter preserves self-post and link-post titles, bodies, authors, timestamps, and URLs without ingesting comments, and converts API failures into adapter-local errors. No public dataclasses or manager signatures changed.

Focused tests cover fake Telegram and Reddit clients, marker advancement, caption/forwarded-content normalization, Reddit self/link post handling, sort propagation, and API failure conversion. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (66 passed).

### Step 3.2.7: Persistence and integration hardening

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added optional durable last-seen marker persistence owned entirely by Source Ingestion. Managers now load and save per-adapter markers to a JSON marker store when adapters share a `params["marker_store_path"]`; without that setting, existing in-memory marker behavior is unchanged. Marker writes are atomic, marker types are preserved for datetime/string/numeric/bool/None values, and no Memory Store import or public dataclass/signature change was introduced.

Added cross-adapter manager coverage for mixed adapter polling, per-adapter marker preservation across manager instances, and marker type restoration. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (69 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest --cov=phosphene --cov-report=term-missing` (346 passed, 94% total coverage; Source Ingestion modules remain above 80%).

### Phase 3.2 Completion: Concrete adapters, human-share, and corpus import

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 3 Phase 2 and the Source Ingestion module. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (69 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest --cov=phosphene --cov-report=term-missing` (346 passed, 94% total coverage).

Phase 2 delivered the concrete Source Ingestion adapter set behind the existing manager contract: shared fetch/extraction and marker utilities, RSS/Atom polling, local text/blog imports, LiveJournal/Twitter/conversation corpus imports, human-share polling, Telegram channel polling, Reddit polling, and Source Ingestion-owned durable marker persistence. Public dataclass shapes and manager signatures stayed stable, and no Memory Store import was introduced.

DEVLOG learning review: Phase 3.2 landed linearly across plan, seven implementation steps, and review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 3.2 plan and step entries recorded "Contract changes: None"; D-33 and D-34 document internal scope decisions, and no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 3 Phase 2 iterations 73-81 completed without repeated tool failures. Review iteration 81 applied two code fixes and escalated for the normal human audit gate; no new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 2 to a one-line completion summary, marked Module 3 complete, and set frontmatter to await human audit before Module 4 Gateway planning.
ARCHITECTURE.md: Source Ingestion row in the Implementation Sequence table updated from "Phase 1.5 complete" to "Complete"; Source Ingestion real-adapter test investment marked partially complete with live external-service testing still deferred.
## Module 3 Phase 1 Plan

**Date:** 2026-05-03
**Decision:** Planned Source Ingestion Phase 1 as a Build phase for the public contract and adapter foundation.

Updated `DEVPLAN.md` to activate Module 3 Phase 1 with five implementation steps: package/dataclass scaffold, config validation and adapter lookup semantics, internal adapter protocol and manager polling orchestration, shared normalization helpers, and focused unit tests. Updated `ARCHITECTURE.md` to mark Source Ingestion in progress and logged D-30 in `DECISIONS.md`.

No source implementation was changed in this planning action.

### Step 3.1.1: Source Ingestion public package scaffold

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the initial `phosphene.source_ingestion` package surface with ARCH-defined public dataclasses, Source Ingestion errors, package exports, and a constructor-compatible `SourceIngestion` manager stub. The scaffold covers `ContentItem`, `AdapterConfig`, `IngestionConfig`, `IngestionResult`, and `IngestionError` with the field order and defaults specified in `ARCH_source_ingestion.md`.

The manager stores its `IngestionConfig` but leaves polling behavior intentionally unimplemented for later Phase 1 steps, where validation, adapter lookup, registry orchestration, and normalization are explicitly scoped. Added focused export/default tests for the new public surface.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion tests/attention_filter tests/memory_store`; 280 tests pass.

### Step 3.1.2: Config validation and adapter lookup semantics

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added Source Ingestion manager config validation for the ARCH-listed adapter types, duplicate source labels, required params, required credentials, and constrained enum params for Reddit sort and corpus formats. The manager now indexes configs by source label, provides internal label lookup, filters disabled adapters when polling all adapters, returns an empty result list when no enabled adapters exist, and raises `AdapterNotFoundError` for unknown specific labels before the later polling implementation runs.

Kept live adapter fetching out of scope for this step: `poll()` and `poll_once()` still defer real adapter execution to the upcoming registry/orchestration step after completing lookup validation. Added focused tests for valid adapter configs, unknown adapter types, duplicate labels, missing params/credentials, invalid enum params, disabled filtering, and unknown-label errors.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion tests/attention_filter tests/memory_store`; 295 tests pass.

### Step 3.1.3: Internal adapter protocol and manager polling orchestration

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the internal Source Ingestion adapter boundary with `SourceAdapter`, `AdapterPollResult`, `AdapterItemError`, and an adapter factory registry. ARCH-listed live adapter types now resolve to explicit pending placeholders, while tests can register deterministic fake adapters without changing the public `SourceIngestion(config)` constructor.

Replaced the manager polling stubs with ordered enabled-adapter polling, specific-adapter polling, per-adapter `IngestionResult` assembly, in-memory last-seen marker handoff, adapter-level exception wrapping, and adapter item-error conversion into public `IngestionError` records. Live network/API fetching remains intentionally out of scope for this foundation phase.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion`; 21 tests pass.

### Step 3.1.4: Shared content normalization helpers

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added shared Source Ingestion normalization helpers for deterministic HTTP(S) URL extraction, configured content truncation, duplicate link removal, and `ContentItem` assembly that preserves timestamps and metadata without performing any network fetching. The helper keeps explicit adapter-provided links, optionally extracts links from content and human annotations according to `IngestionConfig.extract_links`, and applies `IngestionConfig.max_content_length` before emitting the public dataclass.

Added focused normalization tests covering ordered URL extraction, empty text handling, truncation behavior, negative length rejection, metadata/timestamp preservation, human annotation link extraction, and disabled automatic link extraction.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion`; 27 tests pass.

### Step 3.1.5: Focused Source Ingestion unit tests

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Expanded focused Source Ingestion coverage across the Phase 1 foundation without changing implementation. Added tests for the alternate Telegram channel-id config path, empty source-label rejection, empty adapter polling, explicit polling of disabled adapters, pending ARCH adapter error wrapping, zero-length truncation, and link deduplication across explicit and extracted sources.

The existing public export/default, config validation, manager orchestration, adapter error, normalization, and empty/no-enabled polling coverage now anchors the Phase 1 contract before review. Live network/API fetching and corpus parsing remain out of scope for this phase.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion`; 33 tests pass.

## Phase 3.1 Review — Source Ingestion Contract and Adapter Foundation

**Date:** 2026-05-04
**Regime:** Build
**Mode:** autonomous
**Outcome:** Reviewed Module 3 Phase 1 against `ARCH_source_ingestion.md`; no must-fix or should-fix code changes were required.

Validated that Phase 1 remains limited to the public Source Ingestion dataclasses and exports, config validation, adapter registry boundary, manager polling orchestration, per-adapter error reporting, in-memory last-seen marker handoff, and shared normalization helpers. Live Telegram/RSS/Reddit/API fetching, human-share URL fetching, corpus archive parsing, and persisted marker storage remain out of scope for this foundation phase.

Tests passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion` (33 passed).

### Findings
- Must fix: none.
- Should fix: none.
- Optional: none recorded.

### Phase 3.1 Completion: Source Ingestion contract and adapter foundation

**Date:** 2026-05-04
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Phase 1 of Module 3 (Source Ingestion). Final verification ran the Source Ingestion slice with the documented dependency path: `PYTHONPATH=src:.python_deps python3 -m pytest tests/source_ingestion`; 33 tests pass.

Phase 1 delivered the Source Ingestion public package foundation: ARCH-aligned dataclasses and exports, config validation, adapter protocol and registry boundary, manager polling orchestration, per-adapter error reporting, in-memory last-seen marker handoff, deterministic content/link normalization helpers, and focused unit tests. Live Telegram/RSS/Reddit/API fetching, human-share URL fetching, corpus archive parsing, and persisted marker storage remain deferred to later Source Ingestion phases.
DEVLOG learning review: Phase 3.1 landed linearly across one plan, five implementation steps, and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 3.1 step entries and review recorded no contract changes. D-30 and D-31 document the accepted adapter-foundation scope; no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 3 Phase 1 iterations 62-68 completed without escalations or repeated tool failures. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 1 to a one-line completion summary, kept Module 3 active, and cleared active frontmatter pending human audit before Module 3 Phase 2 planning.
ARCHITECTURE.md: Source Ingestion row in the Implementation Sequence table updated from "In progress" to "Phase 1 complete".

## Phase 2.4 Plan: Full batch orchestration and annotation output

**Date:** 2026-05-03
**Decision:** Planned Module 2 Phase 4 as four Build steps: annotation generation boundary, acceptance and retention decision helpers, `AnnotatedFragment` assembly, and public `filter_content` batch regression coverage.

This phase is scoped to completing the public Attention Filter output path over the private evaluation records delivered by Phases 2-3. It will produce accepted fragments, rejected counts, generated annotations, and batch metadata while preserving the read-only Memory Store boundary. Cluster-cache scoring that depends on Distillation-owned centroid/assertion files remains deferred behind the existing friction-preparation records until that cache contract has an implementation owner. See D-28.


### Step 2.4.1: Annotation generation boundary and parsing

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the private accepted-candidate annotation LLM boundary for Attention Filter Phase 4. The implementation builds a structured `generate_attention_filter_annotation` payload from the private `_ItemEvaluation` record, including original content metadata, composite/prompt/structure scores, prompt and structural score maps, friction preparation, connections, and similar-note context. Annotation calls reuse `config.llm_config` and `config.llm_tier`, matching the existing prompt-scoring tier boundary.

Added annotation parsing with JSON-object validation, non-empty string enforcement, whitespace normalization, and unchanged propagation of LLM provider errors. The new `_generate_annotations` helper wraps already-accepted private evaluations without deciding acceptance or assembling public `AnnotatedFragment` objects, preserving the step boundary for later Phase 4 work.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`; 113 tests pass.

### Step 2.4.2: Acceptance decisions and retention criteria

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added deterministic private retention decisions for Attention Filter Phase 4. The implementation now applies the composite-score acceptance threshold with exact-edge inclusion, supports `auto_accept_sources` as a threshold bypass, derives stable retention criteria from non-zero prompt and structural score maps, and computes batch rejected counts from the resulting decisions.

The public non-empty `filter_content` path now reports `rejected_count` from those decisions while still returning no accepted fragments until Step 2.4.3 assembles `AnnotatedFragment` objects. The Attention Filter remains read-only against Memory Store; the new regression coverage verifies no write APIs are called.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`; 119 tests pass.

### Step 2.4.3: AnnotatedFragment assembly

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added public `AnnotatedFragment` assembly for accepted Attention Filter evaluations. The new helpers map generated annotations and retention decisions into consumer-ready fragments with original content metadata, composite importance score, unresolvedness affinity, prompt and structural scores, friction target, connections, linked URLs, and the precomputed embedding.

The non-empty public `filter_content` path now generates annotations for accepted evaluations and returns assembled fragments while preserving accurate rejected counts and read-only Memory Store behavior. Regression coverage verifies exact field mapping, accepted-decision retention criteria propagation, annotation call ordering, embedding passthrough, connection mapping, and no Memory Store write API calls.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`; 275 tests pass.

### Step 2.4.4: Public batch orchestration regression

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added public end-to-end regression coverage for the full non-empty `AttentionFilter.filter_content` orchestration path. The new test drives a mixed batch through fake embedding and LLM boundaries with one threshold-accepted RSS item, one rejected RSS item, and one low-score `human_share` item accepted through `auto_accept_sources`.

The regression verifies deterministic LLM call ordering across prompt scoring, assertion extraction, and annotation generation; config and tier propagation for each LLM boundary; per-item embedding search limits and embedding passthrough; prompt/structure blend metadata; rejected counts; retention criteria attribution; read-only Memory Store behavior; and the existing empty-batch stability alongside the Attention Filter plus Memory Store slices.

Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`; 276 tests pass.

## Phase 2.4 Review - Attention Filter Full Batch Orchestration

**Date:** 2026-05-03
**Regime:** Build
**Mode:** autonomous
**Outcome:** Reviewed Module 2 Phase 4 against `ARCH_attention_filter.md`; one architecture/cost issue was fixed.

Validated the public `filter_content` path for annotation generation, acceptance and auto-accept decisions, accepted `AnnotatedFragment` assembly, rejected counts, batch metadata, and read-only Memory Store behavior. Fixed the Phase 2 boundary so incoming assertion extraction and friction preparation run only after the triple gate activates Phase 2; prompt-only bootstrap mode now avoids the friction LLM call while still scoring prompt criteria and generating annotations for accepted content.

Tests passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store` (277 passed).

### Findings
- Must fix: Gate assertion extraction behind Phase 2 activation; fixed in `src/phosphene/attention_filter/filter.py` with regression coverage.
- Should fix: Remove stale scaffold wording from `AttentionFilter` class docstring; fixed.
- Optional: none recorded.

### Phase 2.4 Completion: Full batch orchestration and annotation output

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Phase 4 of Module 2 (Attention Filter). Final verification ran the Attention Filter plus Memory Store slices with the documented dependency path: `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`; 277 tests pass.

Phase 4 delivered the full public `filter_content` output path: annotation generation, threshold and auto-accept decisions, accepted `AnnotatedFragment` assembly, rejected counts, prompt/structure blend metadata, and read-only Memory Store behavior. Review fixes gate incoming assertion extraction behind Phase 2 activation and remove stale scaffold wording.
DEVLOG learning review: Phase 4 landed linearly across one plan, four implementation steps, and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 4 step entries and review recorded no contract changes. D-28 is closed by this completion and D-29 records the Phase 2 assertion-extraction gating fix; no upstream contract propagation is required.
Log review: `logs/loop/summary.log` shows Module 2 Phase 4 iterations 52-57 completed without escalations or repeated tool failures. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 4 to a one-line completion summary, marked Module 2 complete, and cleared active frontmatter pending human audit before Module 3 planning.
ARCHITECTURE.md: Attention Filter row in the Implementation Sequence table updated from "Phase 3 complete" to "Complete".

## Phase 2.3 Plan: LLM Phase 1 scoring and assertion extraction

**Date:** 2026-05-03
**Decision:** Planned Module 2 Phase 3 as five Build steps: LLM prompt scoring boundary, precision-surplus prompt composite integration, incoming assertion extraction boundary, friction preparation against the assertion-cache contract, and public-path regression coverage.

This phase is scoped to live LLM enrichment of the existing private Attention Filter evaluation path. It adds Phase 1 precision-surplus scoring and incoming-text assertion extraction while keeping accepted fragments, rejection decisions, generated annotations, final public batch orchestration, and Memory Store writes deferred to the next Attention Filter phase. See D-26.

### Step 2.3.1: LLM prompt scoring boundary and score parsing

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added a private toolkit LLM boundary for Phase 1 prompt-criterion scoring and deterministic parser coverage.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md` and keeps the new scoring path private.

Added `_toolkit_complete()` as the Attention Filter's private boundary to `toolkit.llm_client.complete`, with request construction that passes configured prompt criteria, incoming content metadata, and retrieved similar-note context to the LLM. Added `_score_prompt_criteria()` and JSON score parsing that requires one numeric `[0.0, 1.0]` score per configured criterion and raises `InvalidScoreError` for malformed or incomplete payloads while leaving LLM exceptions unwrapped.

The existing non-LLM public `filter_content` behavior remains unchanged for this step; prompt composite wiring is deferred to Step 2.3.2. Focused fake-call tests cover request construction, `llm_config` and `llm_tier` propagation, multi-score parsing, invalid payload handling, unchanged LLM error propagation, and the no-criteria no-call case. The Attention Filter slice passes with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`.

### Step 2.3.2: Precision-surplus prompt composite integration

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Wired Phase 1 prompt scoring into the private per-item Attention Filter evaluation path. The evaluator now preserves the existing embedding, Memory Store retrieval, and structural-score context, calls the configured prompt scoring LLM boundary, computes a weighted prompt composite from configured criteria, and blends it with the current structural score using the density-derived prompt/structure weights.

Precision surplus uses both the per-criterion weight and `ScoringConfig.precision_surplus_weight`, keeping the public scoring knob effective while allowing future prompt criteria to use their own weights. The public non-empty `FilterResult` behavior remains intentionally annotation-free: no accepted fragments are emitted and no Memory Store writes occur before the later orchestration/annotation phase.

Focused verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store` (241 passed).

### Step 2.3.3: Incoming assertion extraction boundary

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added a private incoming assertion-extraction LLM boundary and threaded structured assertions into private item evaluations.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md` and keeps assertion extraction private until friction preparation is wired.

Added `_IncomingAssertion`, assertion-extraction request construction, JSON parsing, and `_extract_incoming_assertions()` as the private toolkit LLM boundary for future friction scoring. The boundary uses `config.assertion_extraction_tier`, passes `config.llm_config` unchanged, returns normalized assertion records with text and confidence, ignores empty extracted text, accepts a `claim` alias for noisy-but-usable payloads, and raises `InvalidScoreError` for malformed JSON, non-list assertions, invalid assertion objects, and out-of-range confidence values. LLM exceptions remain unwrapped.

The private `_evaluate_items()` path now carries extracted incoming assertions alongside retrieval, structural, and prompt scoring context. Public non-empty `FilterResult` behavior remains intentionally unchanged: no accepted fragments, annotation generation, rejection counts, or Memory Store writes are produced in this phase step.

Focused verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter` (100 passed).

### Step 2.3.4: Friction preparation from assertions and cached-cluster contract

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added private friction-preparation records that pair incoming assertions with retrieved cluster cache references.
**Contract changes:** None — implementation follows the existing private Attention Filter path and the Distillation assertion-cache contract without changing public dataclasses.

Added `_CachedClusterReference` and `_FrictionPreparation` as private records for the future friction scorer. `_prepare_friction_from_assertions()` now groups retrieved similar notes by non-empty `cluster_group`, carries the incoming assertions from the extraction boundary, preserves note ids per cluster, records each cluster's maximum retrieved similarity, and names the Distillation assertion-cache location as a Tier 2 JSON file keyed by cluster group.

The change remains read-only and preparatory: it does not read assertion-cache files yet, does not write to Memory Store, does not change public Attention Filter dataclasses, and does not produce accepted fragments or annotations. Focused tests cover assertion pairing, deterministic cluster grouping, assertion-cache path formation, missing-cluster handling, and private evaluator wiring.

Focused verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter` (102 passed).

### Step 2.3.5: Phase 3 public-path regression coverage

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added public `filter_content` regression coverage for the complete Phase 3 fake-backed path.
**Contract changes:** None

Expanded the non-empty public `filter_content` regression test so it now verifies embedding calls, Memory Store similarity retrieval, prompt-scoring LLM calls, assertion-extraction LLM calls, LLM config/tier propagation, prompt payload retrieval metadata, assertion payload content metadata, blend weights, read-only Memory Store behavior, and the deliberate absence of accepted fragments or rejection decisions before the orchestration/annotation phase.

The regression uses an accepting configuration (`acceptance_threshold=0.0` and auto-accept source) to make the current phase boundary explicit: even high-scoring or auto-accepted items still do not emit annotations or accepted fragments until the next Attention Filter phase implements final public orchestration.

Focused verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter` (102 passed).

## Phase 2.2 Plan: Memory Store retrieval and embedding integration

**Date:** 2026-05-03
**Decision:** Planned Module 2 Phase 2 as four Build steps: embedding bridge and empty-batch results, similar-note retrieval context, Memory Store-backed structural scores, and partial non-LLM pipeline wiring.

This phase is scoped to deterministic embedding/retrieval plumbing. Live LLM prompt scoring, assertion extraction, Distillation assertion-cache reads, acceptance decisions, and annotation generation remain deferred to later Attention Filter phases. See D-24.

### Step 2.2.4: Partial non-LLM pipeline wiring

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Wired density, embedding, retrieval, blend weights, and Memory Store-backed structural calculations into a private non-LLM item evaluation path.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md` and leaves LLM-dependent acceptance and annotation deferred.

Added `_ItemEvaluation` and `_evaluate_items_non_llm()` as private preparation records for later LLM scoring. The path embeds each non-empty content item, retrieves similar Memory Store notes, computes the currently available structural signals, and carries the run's prompt/structure blend weights alongside the per-item context.

Updated public non-empty `filter_content` behavior so it performs deterministic preparation work and returns `FilterResult` batch metadata without producing accepted fragments, rejection decisions, annotations, live LLM scoring, assertion extraction, or Memory Store writes. The embedding boundary now resolves its default callable at runtime, which preserves the production toolkit boundary while allowing public-path regression tests to monkeypatch deterministic fakes.

Focused tests cover non-empty density/embedding/retrieval work, configured similarity limits, read-only Memory Store behavior, and the absence of manufactured annotations or rejected counts before the LLM phase. The Memory Store and Attention Filter test slices pass with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`.

### Step 2.2.1: Embedding bridge and empty-batch result

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added the private toolkit embedding boundary and implemented empty-batch `filter_content` results backed by Memory Store density metrics.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md`.

Added `_embed_content()` as an isolated boundary around `toolkit.embedding.embed`, passing `ContentItem.content` as a one-item batch and `config.embedding_config` through unchanged. The toolkit import stays inside the default embedding callable so the package remains importable without the sibling toolkit checkout, while tests can inject fakes directly. Embedding exceptions are not wrapped.

Implemented the empty-list public path for `AttentionFilter.filter_content`: it reads `memory_store.get_density_metrics()`, computes prompt/structure blend weights with the existing density helpers, and returns an empty `FilterResult` with zero totals. Non-empty filtering remains explicitly deferred to later Phase 2 steps.

Focused tests cover empty-batch counts, density snapshot and blend metadata, embedding pass-through, and unchanged embedding error propagation. The Memory Store and Attention Filter test slices pass with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`.

### Step 2.2.2: Similar-note retrieval context

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added private retrieval contexts for non-empty Attention Filter items backed by one embedding call and one Memory Store similarity search per item.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md` and keeps the context private.

Added `_SimilarNoteContext` and `_ItemRetrievalContext` as private normalization records for similar-note retrieval. `_prepare_retrieval_contexts()` embeds each incoming content item once, calls `memory_store.search_by_embedding(embedding, limit=config.similarity_candidates)`, and preserves the returned candidate order while carrying note ids, similarity scores, unresolvedness scores, and selected note metadata for later structural scoring.

The retrieval path is read-only: it calls Memory Store search only, does not touch vault files directly, and does not call Memory Store write APIs. The public non-empty `filter_content` path now prepares the retrieval context before raising the existing deferred-implementation error, leaving scoring, acceptance, and annotation for later Phase 2 steps.

Focused tests cover per-item embedding/search calls with configured limits, ordered preservation of note ids/similarities/unresolvedness values and metadata, and empty retrieval candidates. The Memory Store and Attention Filter test slices pass with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`.

### Step 2.2.3: Memory-backed structural scores

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Added private Memory Store-backed structural evaluation over retrieval contexts.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md` and keeps the evaluation context private.

Added `_MemoryStructuralEvaluation` and `_compute_memory_structural_evaluation()` for the structural signals available before Distillation centroid/assertion caches exist. The helper computes `link_density` from retrieved candidate similarities, computes `unresolvedness_affinity` from retrieved similarities paired with candidate unresolvedness metadata, emits connection ids only for candidates above `scoring.link_density_sim_threshold`, and keeps `friction_target` unset because ARCH friction requires assertion extraction and cached cluster assertions.

Cluster-dependent criteria remain outside this private Memory Store-backed helper until the planned cache integration. Focused tests cover candidate-derived structural inputs, threshold-filtered connections, and empty candidates producing zero structural score with no connections. The Attention Filter slice passes with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`; the required Memory Store plus Attention Filter slices pass with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store tests/attention_filter`.

## Phase 2.1 Audit Closure

**Date:** 2026-05-03
**Decision:** Human audit recorded; Module 2 Phase 1 (Attention Filter contract and scoring foundation) is accepted as audited and complete.

Updated `DEVPLAN.md` Current Status and the Module 2 Phase 1 summary to reflect audit closure for 2.1. No implementation changes, test changes, or architecture changes were required.

### Phase 2.1 Completion: Attention Filter contract and scoring foundation

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Phase 1 of Module 2 (Attention Filter). Final verification ran the full Attention Filter test slice with the documented dependency path: `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`; 61 tests pass.

Phase 1 delivered the public `phosphene.attention_filter` package contract, ARCH-aligned dataclasses and exports, `InvalidScoreError`, default precision-surplus prompt criteria, config validation, triple-gate Phase 2 activation, prompt/structure blend weights, deterministic geometric scoring helpers for all seven Phase 2 criteria, weighted Phase 2 composite scoring, and focused unit coverage.

DEVLOG learning review: Phase 1 landed linearly across five implementation steps and one review. The review found and fixed one field-order drift against `ARCH_attention_filter.md`; no repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.

Contract Changes scan: Phase 1 step entries recorded "Contract changes: None"; the review also recorded no contract changes. The phase fulfilled the existing `ARCH_attention_filter.md` contract, so no upstream document propagation is required.

Log review: `logs/loop/summary.log` shows Module 2 Phase 1 iterations 29-35 completed cleanly with no escalations, no repeated tool failures, and no wasted-turn patterns. No new operational Gotchas to promote.

DEVPLAN cleanup: reduced the Phase 1 step plan to a one-line completion summary referencing this entry. Module 2 remains in progress, with Phase 2 ready for its own Phase Plan.

ARCHITECTURE.md: Attention Filter row in the Implementation Sequence table updated from "In progress" to "Phase 1 complete".

Frontmatter reset for next phase: `phase: 2`, `phase_title: Memory Store retrieval and embedding integration`, `step: null`, `mode: Discuss`, `review_done: false`.

### Phase 2.1 Review: Attention Filter contract and scoring foundation

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Reviewed Module 2 Phase 1 against `ARCH_attention_filter.md` and marked the phase review done.
**Contract changes:** None — corrected implementation/test field order to match the existing ARCH contract.

Findings:
- Must fix: `AttentionFilterConfig` field order drifted from `ARCH_attention_filter.md`; corrected the keyword-only dataclass and export test expectation so the public contract order is authoritative.
- Should fix: None.
- Optional: None.

The full test suite passes with `PYTHONPATH=src:.python_deps python3 -m pytest`.

### Step 2.1.5: Attention Filter focused unit tests

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Added focused unit coverage for the Attention Filter public package contract, `ScoringConfig` defaults, and deterministic Phase 2 scoring helpers.
**Contract changes:** None — tests verify the existing `ARCH_attention_filter.md` contract.

Added export and dataclass field tests for the public `phosphene.attention_filter` API surface, including construction checks for ARCH-defined data models and exception inheritance. Added geometric scoring tests covering boundary values, degenerate zero/one-cluster inputs, empty note lists, clamping behavior, mapping and matrix pairwise cluster similarities, and non-uniform Phase 2 composite weights.

The Attention Filter test slice passes with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`.

### Step 2.1.1: Attention Filter public contract scaffold

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Added the initial `phosphene.attention_filter` package surface with ARCH-defined dataclasses, `ScoringConfig` defaults, `InvalidScoreError`, and an `AttentionFilter` constructor stub.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md`.

Created `types.py`, `errors.py`, `filter.py`, and package exports for Module 2. The dataclass scaffold covers `ContentItem`, `FilterCriterion`, `ScoringConfig`, `AttentionFilterConfig`, `AnnotatedFragment`, and `FilterResult`, with `DensityMetrics` and `ndarray` wiring matching downstream contracts. `filter_content` is intentionally left unimplemented because scoring, validation, and live embedding/LLM behavior belong to later Phase 1 steps.

The local checkout does not include the documented sibling toolkit `llm_client` and `embedding` modules, so the scaffold uses import-time compatibility fallbacks for `LLMConfig`, `EmbeddingConfig`, and `ModelTier` while preserving the public field names and defaults.

### Step 2.1.2: Default prompt criterion and config validation

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Added precision-surplus default prompt criterion construction and fail-fast validation for Attention Filter scoring/config thresholds.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md`.

Added `default_prompt_criteria()` with the ARCH-defined precision-surplus criterion and made `AttentionFilterConfig` default to a fresh precision-surplus-only list. Added validation for `acceptance_threshold`, `density_crossover`, non-negative `ScoringConfig` weights, `phase2_max_weight`, and positive triple-gate thresholds.

Focused tests now cover default criterion construction, fresh-list behavior, config defaulting, accepted boundary values, and representative invalid values. The full suite passes with `PYTHONPATH=src:.python_deps python3 -m pytest`.

### Step 2.1.3: Phase 2 gate and blend weights

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Added deterministic Phase 2 triple-gate activation and prompt/structure blend weight calculation from `DensityMetrics`.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md`.

Implemented `phase2_is_active()` for the note count, cluster count, and half-crossover mean link degree gate. Implemented `compute_blend_weights()` so structure weight stays at zero before the gate, ramps linearly from `density_crossover * 0.5` to `density_crossover * 2.0`, caps at `phase2_max_weight`, and keeps prompt weight as the complement.

Added focused edge-case tests for empty memory, each missing gate threshold, exactly-at-threshold behavior, linear ramping, high-density capping, and custom crossover settings. The Attention Filter test slice passes with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`.

### Step 2.1.4: Phase 2 geometric scoring helpers

**Date:** 2026-05-02
**Mode:** autonomous
**Outcome:** Added deterministic Phase 2 helper functions for all seven geometric Attention Filter criteria plus weighted Phase 2 composite scoring.
**Contract changes:** None — implementation follows `ARCH_attention_filter.md`.

Implemented helpers for liminality, friction, unexpected connection, structural insight, link density, cluster novelty, and unresolvedness affinity. Helpers accept pre-computed similarities or alignment values, clamp returned scores to `[0.0, 1.0]`, normalize link density by candidate count, and clamp unresolvedness affinity after summing weighted note tensions.

Added `compute_phase2_composite()` for `ScoringConfig`-weighted averages across available Phase 2 scores and exported the helper surface from `phosphene.attention_filter`. Existing Attention Filter tests and the full project suite pass with `PYTHONPATH=src:.python_deps python3 -m pytest`.

## Documentation Reconciliation — D-13, 3.3a, 5.9 Sync

**Date:** 2026-05-02
**Regime:** Refine

Reconciled all project documentation after two parallel workstreams: D-13 closure (seeding module elimination) and conceptual additions (Section 3.3a geometric formalizations, Section 5.9 configurable parameters). Work proceeded in four stages:

**Stage 1 — phosphene.md D-13 cleanup (12 edits):**
Sections 2.5, 3.3a, 4.1, 4.2, 4.6, 5.7, 5.9, 6.3 updated to reflect D-13. Exemplar pairs removed per human decision. Corpus-to-knowledge-graph technique moved to new Appendix A. "Seeding Process" → "Corpus Ingestion and Bootstrap." Seed overweighting → version-count inertia throughout.

**Stage 2 — Architecture impact analysis:**
Read all 9 ARCH files against updated phosphene.md. Identified 6 sync issues (S-1 through S-6) where 3.3a and 5.9 diverged from ARCH specs. Created temporary SYNC_ISSUES.md for structured resolution.

**Stage 3 — Decision resolution (D-17 through D-22):**
- **D-17 (Critical):** Section 3.3a adopted as implementation spec. Phase 1 = precision_surplus (LLM, intrinsic quality). Phase 2 = 7 geometric criteria: liminality, friction, unexpected_connection, structural_insight (from 3.3a) + link_density, cluster_novelty, unresolvedness_affinity (retained from ARCH). New `ScoringConfig` dataclass separates processing tuning from contract.
- **D-18:** `phase2_max_weight = 0.7` — prompt criteria always retain ≥30% weight.
- **D-19:** Triple-gate Phase 2 activation (note_count AND cluster_count AND mean_link_degree).
- **D-20:** Dropped `slop_sensitivity` — redundant with existing criteria.
- **D-21:** Deferred proactive budget — keep as conceptual note, implement when needed.
- **D-22:** Assertion cache — Distillation extracts cluster assertions during T1→T2 for friction scoring.

**Additional design work during resolution:**
- **Novelty-addiction risk analysis:** Identified self-reinforcing feedback loop from overweighted liminality. Added two mitigations: (1) revised deployment weights prioritizing depth/challenge over novelty (friction=1.5 > structural_insight=1.3 > liminality=1.0 > cluster_novelty=0.8), (2) `min_cluster_coherence` gate in Distillation preventing weak clusters from becoming reference centroids.
- **Precision surplus formalization options:** Evaluated 4 geometric proxy approaches (embedding specificity, information density, claim-evidence detection, compression resistance). All insufficient — precision surplus is genuinely intrinsic. Recorded as future reference, not pursued.

**Stage 4 — Propagation and cleanup:**

**Files changed:**
- `phosphene.md` — D-13 cleanup (12 edits), slop_sensitivity removed from 5.9, deployment weights revised, stale "seed overweighting" fixed
- `ARCH_attention_filter.md` — ScoringConfig dataclass, Phase 1/2 split, triple-gate activation, phase2_max_weight cap, novelty-addiction risk note, updated usage example
- `ARCH_distillation.md` — assertion cache step and result field, min_cluster_coherence gate and result field, assertion cache in State and Downstream sections
- `DEVPLAN.md` — Module 2 Phase 1 steps 2.1.1–2.1.5 rewritten for new ARCH spec
- `DECISIONS.md` — D-17 through D-22 recorded
- `ARCHITECTURE.md` — decision log reference updated to D-22
- `prior_art.md` — 6 stale MiroFish/seeding references updated

**File deleted:** `SYNC_ISSUES.md` (all items resolved and propagated).

### Contract Changes
- `ARCH_attention_filter.md`: new `ScoringConfig` type, revised `AttentionFilterConfig` fields (`scoring`, `assertion_extraction_tier`), `filter_content` behavior rewritten (triple gate, Phase 1/2 split, 7 geometric criteria), prompt criteria reduced to precision_surplus only, structural criteria replaced by Phase 2 geometric criteria table
- `ARCH_distillation.md`: new `min_cluster_coherence` config field, new `incoherent_cluster_count` and `assertion_cache_updated` result fields, new behavior steps 6 (coherence gate) and 8 (assertion cache extraction), new State entry (assertion cache)

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

## Phase 2.2 Review — Attention Filter Memory Retrieval Integration

**Date:** 2026-05-03
**Regime:** Build
**Mode:** autonomous
**Outcome:** Reviewed Module 2 Phase 2 against `ARCH_attention_filter.md`; no must-fix or should-fix code changes were required.

Validated that Phase 2 remains limited to embedding, Memory Store density reads, similar-note retrieval, and Memory Store-backed structural preparation. The public non-empty `filter_content` path still avoids accepted fragment production, rejected-count manufacture, LLM scoring, assertion extraction, annotation generation, and Memory Store writes, matching the phase boundary recorded in D-24.

Tests passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store` (225 passed).

### Findings
- Must fix: none.
- Should fix: none.
- Optional: none recorded.

### Phase 2.2 Completion: Memory Store retrieval and embedding integration

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Phase 2 of Module 2 (Attention Filter). Final verification ran the required Attention Filter plus Memory Store test slices with the documented dependency path: `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter tests/memory_store`; 225 tests pass.

Phase 2 delivered the private toolkit embedding boundary, empty-batch `FilterResult` behavior backed by Memory Store density metrics, per-item similar-note retrieval contexts, Memory Store-backed structural scores for `link_density` and `unresolvedness_affinity`, connection id extraction above the configured similarity threshold, and partial non-LLM pipeline wiring. The public non-empty `filter_content` path now performs deterministic density, embedding, retrieval, and structural preparation while intentionally leaving accepted fragments, rejected counts, LLM annotations, final scoring, assertion extraction, and Memory Store writes for later Attention Filter phases.

DEVLOG learning review: Phase 2 landed linearly across one plan, four implementation steps, and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.

Contract Changes scan: Phase 2 step entries recorded "Contract changes: None"; the review also recorded no contract changes. D-24 and D-25 document the retrieval-only phase boundary, but no upstream contract propagation is required.

Log review: `logs/loop/summary.log` shows Module 2 Phase 2 iterations 37-42 completed cleanly with no escalations, no repeated tool failures, and no wasted-turn patterns. No new operational Gotchas to promote.

DEVPLAN cleanup: reduced the Phase 2 step plan to a one-line completion summary referencing this entry. Module 2 remains in progress, with Phase 3 ready for its own Phase Plan after human audit.

ARCHITECTURE.md: Attention Filter row in the Implementation Sequence table updated from "Phase 1 complete" to "Phase 2 complete".

Frontmatter reset for next phase: `phase: 3`, `phase_title: LLM Phase 1 scoring and assertion extraction`, `step: null`, `mode: Discuss`, `review_done: false`.

## Phase 2.2 Audit Closure — Attention Filter Memory Retrieval Integration

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Accepted

**Decision:** Human review recorded; Module 2 Phase 2 (Attention Filter Memory Store retrieval and embedding integration) is accepted as reviewed complete.

Updated `DEVPLAN.md` Current Status to move Module 2 from awaiting human audit to ready for Phase 3 planning. No implementation changes, test changes, or architecture changes were required.

## Phase 2.3 Review — Attention Filter LLM Phase 1 Scoring and Assertion Extraction

**Date:** 2026-05-03
**Regime:** Build
**Mode:** autonomous
**Outcome:** Reviewed Module 2 Phase 3 against `ARCH_attention_filter.md`; no must-fix or should-fix code changes were required.

Validated that Phase 3 remains limited to private LLM enrichment of per-item evaluation: precision-surplus prompt scoring, incoming assertion extraction at `assertion_extraction_tier`, prompt composite scoring, friction preparation against retrieved cluster groups, and public-path regression coverage. The public non-empty `filter_content` path still returns no accepted fragments and performs no Memory Store writes before the next orchestration/annotation phase.

Tests passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter` (102 passed).

### Findings
- Must fix: none.
- Should fix: none.
- Optional: none recorded.

### Phase 2.3 Completion: LLM Phase 1 scoring and assertion extraction

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Phase 3 of Module 2 (Attention Filter). Final verification ran the Attention Filter test slice with the documented dependency path: `PYTHONPATH=src:.python_deps python3 -m pytest tests/attention_filter`; 102 tests pass.

Phase 3 delivered the private toolkit LLM boundary for prompt-criterion scoring, weighted precision-surplus prompt composite integration in the private per-item evaluation path, incoming assertion extraction through `config.assertion_extraction_tier`, friction-preparation records pairing incoming assertions with retrieved cluster identifiers and the Distillation assertion-cache contract, and public-path regression coverage for the fake-backed non-empty `filter_content` path. The phase intentionally preserves the pre-orchestration boundary: no accepted fragments, no annotation generation, and no Memory Store writes from the public non-empty path.

DEVLOG learning review: Phase 3 landed linearly across one plan, five implementation steps, and one review. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.

Contract Changes scan: Phase 3 step entries recorded "Contract changes: None"; the review also recorded no contract changes. D-26 documents the LLM-enrichment-only phase boundary, but no upstream contract propagation is required.

Log review: `logs/loop/summary.log` shows Module 2 Phase 3 iterations 44-50 completed cleanly with no escalations, no repeated tool failures, and no wasted-turn patterns. No new operational Gotchas to promote.

DEVPLAN cleanup: reduced the Phase 3 step plan to a one-line completion summary referencing this entry. Module 2 remains in progress, with Phase 4 ready for its own Phase Plan after human audit.

ARCHITECTURE.md: Attention Filter row in the Implementation Sequence table updated from "Phase 2 complete" to "Phase 3 complete".

Frontmatter reset for next phase: `phase: 4`, `phase_title: Full batch orchestration and annotation output`, `step: null`, `mode: Discuss`, `review_done: true`.

## Phase 2.3 Audit Closure — Attention Filter LLM Phase 1 Scoring and Assertion Extraction

**Date:** 2026-05-03
**Mode:** autonomous
**Outcome:** Accepted

**Decision:** Human review recorded; Module 2 Phase 3 (Attention Filter LLM Phase 1 scoring and assertion extraction) is accepted as reviewed complete.

Updated `DEVPLAN.md` Current Status to move Module 2 from awaiting human audit to ready for Phase 4 planning. No implementation changes, test changes, or architecture changes were required.

Frontmatter reset for next phase: `phase: 4`, `phase_title: Full batch orchestration and annotation output`, `step: null`, `mode: Discuss`, `review_done: true`.

## DEVLOG Archive Addition — 2026-05-06

(Entries below were moved from DEVLOG.md history during Module 6 Phase 3 completion cleanup.)
### Phase 5.2 Plan: LLM generation modes and skeptical memory

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 5 Phase 2 as a Build phase over live Generator behavior behind the existing public contract. The plan starts with an internal toolkit/llm_client call and JSON parsing boundary, then implements prompted generation, absent-topic selection, response generation with router threading metadata, free-play generation with lateral affordances, skeptical memory verification, and cross-mode integration hardening.

Scope decision recorded in D-40: Phase 2 keeps Generator stateless and read-only against Memory Store, uses fake LLM and fake Memory Store boundaries for deterministic coverage, preserves Phase 1 public dataclasses and Output Router behavior, and excludes new platform routing scope.

### Step 5.2.1: LLM client boundary and response parsing

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added private Generator LLM boundary helpers that call `toolkit/llm_client.complete` at `GeneratorConfig.generation_tier`, normalize toolkit response content and `TokenUsage`, and translate provider/import/runtime failures to `LLMAPIError`. The helpers are injectable for deterministic tests and do not change the public Generator API or start prompted/response/free-play orchestration.

Added JSON parsing for model output into bounded `GeneratorOutput` fields: non-empty content and intent tag, request-matching output mode, boolean lateral flag, probability-bounded importance, source-note attribution with fallback IDs, parsed contradiction objects, preserved token usage, and optional response threading metadata. Focused tests cover generation tier propagation, token usage preservation, provider failure wrapping, valid parsing, fallback attribution, and malformed/missing/invalid payload rejection. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (35 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (431 passed).

### Step 5.2.2: Prompted generation orchestration

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented live prompted `Generator.generate()` orchestration behind the existing public contract. The method now loads a fresh Tier 3 personality snapshot per call, includes configured Tier 2 enrichment, optionally loads unresolved-thread notes by ID, builds a deterministic JSON prompt with ambient context and source material, calls the generation LLM boundary, parses the JSON response into `GeneratorOutput`, preserves token usage, and falls back to source attribution from personality, pattern, and unresolved-thread notes when the model omits attribution.

Kept the Generator stateless and read-only against Memory Store: the prompted path uses only `get_personality_context()`, Tier 2 query/search reads, and optional `get_note()` reads. Added fake-LLM and fake-store coverage for prompt contents, generation tier/config propagation, unresolved-note loading, source-note fallback, token usage preservation, and no Memory Store writes. Updated the foundation integration test now that `generate()` is implemented for prompted generation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (36 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (432 passed).

### Step 5.2.3: Topic selection when prompt topic is absent

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added deterministic prompted-generation topic selection for absent or blank prompt topics. The Generator now selects the first loaded unresolved-thread note when unresolved IDs are present, otherwise selects the highest-importance Tier 2 pattern from the fresh snapshot, and includes explicit `topic_selection` metadata in the LLM prompt before generation. If no prompt topic, unresolved thread, or Tier 2 pattern is available, the prompt carries `topic: null` with `source: no_bootstrap_material` after the required Tier 3 personality context check.

Kept the behavior stateless and read-only against Memory Store: selection reuses existing `get_personality_context()`, Tier 2 query/search reads, and optional `get_note()` reads without adding writes or public API changes. Added fake-LLM coverage for explicit prompt metadata, unresolved-thread bootstrap, high-importance Tier 2 fallback, and empty-material behavior. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (39 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (435 passed).

### Step 5.2.4: Response generation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented live `Generator.respond()` orchestration behind the existing public contract. The response path loads a fresh personality snapshot, reads relevant Memory Store context from inbound-message embeddings when present or a bounded query fallback otherwise, builds a deterministic JSON prompt containing the inbound message, ambient context, personality files, Tier 2 patterns, relevant notes, and required response output metadata, then calls the generation LLM boundary and parses the generated response.

Preserved router threading by setting `GeneratorOutput.originating_message_id` from `InboundMessage.message_id`, and kept the Generator stateless and read-only against Memory Store with no public API changes. Added fake-LLM/fake-store coverage for prompt contents, config and tier propagation, token usage preservation, source-note fallback across personality/pattern/relevant notes, no Memory Store writes, and response threading metadata. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (40 passed).

### Step 5.2.5: Free-play generation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented live `Generator.free_play()` orchestration behind the existing public contract. The free-play path loads a fresh personality snapshot, reads trigger notes by ID, builds a deterministic JSON prompt carrying trigger note IDs, lateral budget, affordances, ambient context, personality files, Tier 2 patterns, trigger notes, contradictions, and required free-play output metadata, then calls the generation LLM boundary and parses the generated output.

Preserved lateral semantics by requiring `output_mode="free_play"` and `is_lateral=True`, preserved trigger/source note attribution fallback across personality, pattern, and trigger notes, and kept the Generator stateless and read-only against Memory Store with no public API changes. Added fake-LLM/fake-store coverage for prompt contents, config and tier propagation, token usage preservation, trigger-note loading, no Memory Store writes, lateral flags, and source attribution. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (41 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (437 passed).

### Step 5.2.6: Skeptical memory verification

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented skeptical memory verification behind `GeneratorConfig.skeptical_memory`. The Generator now performs verification-tier LLM claim extraction for each Tier 3 personality file, reads recent Tier 1 notes through a bounded `NoteQuery` using `skeptical_window_days`, checks extracted claims against that recent evidence with a verification-tier LLM call, and records resulting `Contradiction` objects in the `PersonalitySnapshot`.

Merged snapshot contradictions into `GeneratorOutput.contradictions_noted` for prompted, response, and free-play paths while preserving any contradictions returned by the generation LLM. The path remains stateless and read-only against Memory Store, with no public API changes. Added focused fake-LLM/fake-store coverage for verification-tier propagation, recent Tier 1 query shape, prompt inclusion of contradictions, output contradiction reporting, and disabled skeptical-memory behavior in existing tests. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (44 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (440 passed).

### Step 5.2.7: Prompt/parse hardening and phase integration

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added internal LLM config rotation fallback for provider-call failures using the existing `GeneratorConfig.llm_configs_rotation` field. Generation and verification calls now try the primary config first, then configured fallback configs at the same requested tier; malformed toolkit/model responses still fail immediately instead of rotating, so parse hardening remains deterministic.

Added focused boundary tests for rotation fallback, tier propagation, token usage preservation, and malformed-completion behavior. Added cross-mode integration coverage that exercises prompted generation, response generation, and free-play generation through primary failure plus fallback success, verifying output modes, lateral flags, response threading, source-note fallback attribution, prompt payload shape, and read-only Memory Store behavior. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (443 passed).

### Phase 5.2 Review: LLM generation modes and skeptical memory

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Generator Phase 2 against `ARCH_generator.md`. Must fix: none. Should fix: refreshed a stale `Generator` class docstring that still described LLM generation as future work. Optional: no optional changes deferred.

The phase remains within the planned live-generation boundary: prompted generation, response generation, and free-play generation all load fresh personality context, build deterministic LLM prompt payloads, parse bounded `GeneratorOutput` values, preserve response threading and token usage, use LLM config rotation only for provider-call fallback, and keep Memory Store access read-only. Skeptical memory records contradictions from verification-tier LLM checks without writing them back to Memory Store. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (443 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next action.

### Phase 5.2 Completion: LLM generation modes and skeptical memory

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 5 Phase 2. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (47 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (443 passed).

Phase 2 delivered live Generator behavior behind the Phase 1 public contract: prompted generation, absent-topic selection, response generation with router threading metadata, free-play generation with lateral affordances, skeptical memory verification against recent Tier 1 evidence, provider-failure LLM config rotation fallback, parse-error hard stops, source attribution fallback, token-usage preservation, and deterministic fake-boundary integration coverage across all generation modes.

DEVLOG learning review: Phase 5.2 landed linearly across planning, seven implementation steps, and review. Review found no must-fix issues; the only cleanup was a stale class docstring. No trial-and-error implementation pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 5.2 plan, step, review, and completion entries recorded "Contract changes: None"; D-40, D-41, and D-42 document implementation and review decisions without upstream contract propagation.
Log review: Recent iterations repeatedly tried `rg` before loading the existing no-ripgrep gotcha. DEVPLAN already contains the prescriptive rule, so no new Gotcha was added.
DEVPLAN cleanup: reduced Module 5 Phase 2 to a one-line completion summary and set frontmatter to await human audit before Module 6 planning.
ARCHITECTURE.md: Generator + Output Router row in the Implementation Sequence table updated from "Phase 1 complete" to "Complete".

### Phase 5.1 Plan: Contract and routing foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Planned
**Contract changes:** None

Planned Module 5 Phase 1 as a Build phase over the Generator + Output Router foundation. The plan starts with ARCH-aligned public dataclasses, errors, exports, and validation, then implements stateless Memory Store personality-context loading and empty-personality behavior, deterministic Output Router delivery decisions through fake Gateway instances, and integration coverage proving the foundation stays read-only against Memory Store and credential-free.

Scope decision recorded in D-39: Phase 1 deliberately excludes live LLM generation, skeptical memory verification, and real prompt/parse behavior while preserving interface room for Tier 2 relevance and embedding boundaries. Those behaviors remain for later Generator phases once the public contract and Gateway routing surface are stable.

### Step 5.1.1: Public contract, errors, and exports

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added the `phosphene.generator` package foundation with ARCH-aligned public dataclasses, exception hierarchy, constructor surface, Output Router config types, and package exports. The Generator facade now exposes `generate`, `free_play`, and `respond` signatures without live LLM behavior, and `route()` is present as the Output Router boundary for later deterministic delivery implementation.

Added validation for obvious config and threshold invariants: positive token budgets and window sizes, non-negative Tier 2 limits, probability-bounded output importance, non-empty free-play triggers, and ordered positive routing length thresholds. Focused export and dataclass tests cover the public API surface and fallback import compatibility for toolkit LLM types. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (12 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (408 passed).

### Step 5.1.2: Memory Store context-loading boundary

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the Generator's stateless personality snapshot boundary. Each load calls `memory_store.get_personality_context()`, raises `EmptyPersonalityError` when no Tier 3 personality files exist, carries the ambient context through the snapshot, and preserves contributing personality and Tier 2 pattern note IDs for later output attribution.

Added optional Tier 2 enrichment without introducing live embedding ownership: callers can provide a topic embedding to use `search_by_embedding(tier=2)`, or fall back to `query_notes(NoteQuery(tier=2))` behind the Memory Store boundary. The current public generation methods now perform the required empty-personality check before stopping at the later-phase LLM placeholder. Focused fake-store tests cover fresh context loads, empty-personality behavior, no Memory Store writes, source ID preservation, embedding-search enrichment, query fallback, and disabled enrichment. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (17 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (413 passed).

### Step 5.1.3: Output Router deterministic delivery

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Implemented the Output Router's deterministic `route()` behavior. Intent tags configured for `log` now suppress Gateway delivery and return `None`; other outputs resolve to either an intent-specific platform override or the Gateway default platform. The router selects `text`, `markdown`, or `telegraph` from configured content-length thresholds and threads response outputs by copying `GeneratorOutput.originating_message_id` into `OutboundMessage.reply_to`.

Added focused fake-Gateway coverage for log-only suppression, default-platform text delivery, markdown and Telegraph length boundaries, response threading, platform overrides, and Gateway `DeliveryResult` propagation. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (22 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest tests` (418 passed).

### Step 5.1.4: Phase foundation integration tests

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Added package-level Generator foundation integration coverage using fake Memory Store and fake Gateway objects. The new tests show repeated activations load fresh personality snapshots, preserve Tier 3 and Tier 2 source note IDs, avoid Memory Store writes, route credential-free through a fake Gateway, and produce Gateway-compatible `OutboundMessage` values from `GeneratorOutput`.

Also covered the public `generate()` Phase 1 boundary: it loads personality context before stopping at the later-phase LLM placeholder without requiring live credentials or writing to Memory Store. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (24 passed) and `PYTHONPATH=src:.python_deps python3 -m pytest` (420 passed).

### Phase 5.1 Review: Contract and routing foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Reviewed
**Contract changes:** None

Reviewed Generator Phase 1 against `ARCH_generator.md`. Must fix: none. Should fix: none. Optional: no optional changes deferred.

The phase remains within the planned foundation boundary: public dataclasses/errors/exports match the ARCH contract, Memory Store context loading is stateless and read-only, empty Tier 3 context raises `EmptyPersonalityError`, Tier 2 enrichment stays behind Memory Store query/search boundaries, and Output Router behavior deterministically maps intent, length, and response threading into Gateway-compatible `OutboundMessage` values without live credentials. Verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (24 passed). DEVPLAN frontmatter updated to `review_done: true`; Phase Complete is the next action.

### Phase 5.1 Completion: Contract and routing foundation

**Date:** 2026-05-05
**Mode:** autonomous
**Outcome:** Complete
**Contract changes:** None

Closed Module 5 Phase 1. Final verification passed with `PYTHONPATH=src:.python_deps python3 -m pytest tests/generator` (24 passed).

Phase 1 delivered the Generator + Output Router foundation: ARCH-aligned public dataclasses, public errors and exports, constructor surface, config and threshold validation, stateless Memory Store personality-context loading, `EmptyPersonalityError` for absent Tier 3 context, optional Tier 2 enrichment behind Memory Store query/search boundaries, deterministic intent/length/thread routing through Gateway-compatible `OutboundMessage`, and credential-free fake integration coverage proving the foundation remains read-only against Memory Store.

DEVLOG learning review: Phase 5.1 landed linearly across plan, four implementation steps, and review. Review found no must-fix, should-fix, or optional issues. No repeated trial-and-error pattern needs promotion to DEVPLAN Gotchas.
Contract Changes scan: Phase 5.1 plan, step, review, and completion entries recorded "Contract changes: None"; D-39 documents the foundation boundary, and no upstream contract propagation is required.
Log review: No repeated tool failures or wasted-turn patterns were found for this phase. No new operational Gotchas to promote.
DEVPLAN cleanup: reduced Phase 1 to a one-line completion summary and set frontmatter to await human audit before Generator Phase 2 planning.
ARCHITECTURE.md: Generator + Output Router row in the Implementation Sequence table updated from "In progress" to "Phase 1 complete".


(Module 5 Phase 1 and earlier entries archived to DEVLOG_archive.md on 2026-05-05.)
