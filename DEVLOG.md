# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Each step gets a structured entry. This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD --> -->

<!-- Module 1 (Memory Store) entries archived 2026-04-29 — see DEVLOG_archive.md -->

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

<!-- HISTORY --> <!-- do not read past this line. Completed entries kept for audit. -->

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
