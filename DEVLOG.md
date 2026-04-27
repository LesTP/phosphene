# Phosphene — Development Log

<!-- Chronological record of what happened during development.
     Each step gets a structured entry. This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD --> -->

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
