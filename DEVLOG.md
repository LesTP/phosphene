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
