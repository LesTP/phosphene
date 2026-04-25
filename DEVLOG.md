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
