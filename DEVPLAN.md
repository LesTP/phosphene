---
module: MEMORY_STORE
phase: 1
phase_title: Core data model and CRUD
step: 0 of 4
mode: Discuss
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
  - All 10 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`

## Current Status

- **Phase** — 1 — Core data model and CRUD
- **Focus** — Step 1: Project bootstrap, types module, errors module
- **Blocked/Broken** — None

## Module 1: Memory Store

Four-phase plan (matching ARCH_memory_store.md public API surface). Phases 2–4 are sketched here for orientation only and will each get their own Phase Plan when reached.

- **Phase 1 (active)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes.
- **Phase 2** — Index layer and queries: `get_index`, `query_notes`, inbound link counting.
- **Phase 3** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`.
- **Phase 4** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`.

### Phase 1 — Core data model and CRUD

**Regime:** Build. Correctness verifiable by unit tests against the public API in `ARCH_memory_store.md`.

**Scope.** Establish the `phosphene.memory_store` package, port every dataclass and exception named in the ARCH file, and implement vault-backed CRUD for single notes. No querying, no embedding search, no graph traversal, no decay, no supersession — those come in later phases. Memory Store is a leaf module; Phase 1 has no toolkit dependency.

**Out of scope (deferred to later phases).**
- Index layer, `get_index`, `query_notes` — Phase 2
- Inbound link counting (Phase 1 `link_count` reflects outbound links only) — Phase 2
- `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context` — Phase 3
- `supersede`, `run_decay`, `get_density_metrics` — Phase 4

**Dependencies.** `numpy` (for `ndarray` typing in dataclasses), `pyyaml` (frontmatter parsing), `pytest` (tests). No toolkit imports.

**Vault layout decision.** One subdirectory per tier: `<vault>/tier1/`, `<vault>/tier2/`, `<vault>/tier3/`. One `.md` file per note. Filename = `<note_id>.md`. Note ID = slug-of-title + short timestamp suffix, generated in `store_note`.

#### Steps

**Step 1 — Project bootstrap, types, and errors**
- Create `pyproject.toml` (Python 3.12+, deps: `numpy`, `pyyaml`; dev deps: `pytest`).
- Create `src/phosphene/memory_store/__init__.py` exporting the public surface.
- Create `src/phosphene/memory_store/types.py` with every dataclass from `ARCH_memory_store.md` §Public API → Types: `MemoryStoreConfig`, `NoteInput`, `MemoryNote`, `IndexEntry`, `DensityMetrics`, `PersonalityContext`, `NoteQuery`, `NotePatch`, `DecayReport`. Field names, types, and defaults must match the ARCH exactly.
- Create `src/phosphene/memory_store/errors.py` with: `VaultError`, `InvalidTierError`, `TitleTooLongError`, `InvalidScoreError`, `NoteNotFoundError`, `DimensionMismatchError`, `TierMismatchError`, `AlreadySupersededError`. All subclass a common `MemoryStoreError`.
- Tests (`tests/memory_store/test_types.py`, `tests/memory_store/test_errors.py`):
  - Each dataclass instantiates with documented defaults.
  - `NoteInput` accepts the full set of optional fields shown in the ARCH usage example.
  - Each exception is constructable, raises/catches via its base class, and inherits from `MemoryStoreError`.

**Step 2 — Vault I/O primitives**
- Create `src/phosphene/memory_store/vault.py` (module-private — not re-exported from package `__init__`):
  - `generate_note_id(title: str, created_at: datetime) -> str` — `<slug>-<yyyymmddHHMMSS>-<4-char-hash>`. Stable for the same (title, created_at, salt). Slug strips non-alphanumeric, lowercases, joins with hyphens, truncates ≤ 60 chars.
  - `note_path(vault_path: Path, tier: int, note_id: str) -> Path` — returns `<vault>/tier<N>/<note_id>.md`.
  - `serialize_note(note: MemoryNote) -> str` — YAML frontmatter (all metadata) + `\n---\n` separator + markdown body. Wikilinks (`[[...]]`) are left literal in the body — Phase 1 does not parse them.
  - `parse_note(text: str) -> MemoryNote` — inverse of `serialize_note`. Embeddings are not stored in the markdown file (Phase 3 concern); `embedding` parses as `None`.
- Tests (`tests/memory_store/test_vault.py`):
  - `generate_note_id` produces the documented format and is collision-free for distinct (title, created_at) pairs in a tight loop.
  - Round-trip: `parse_note(serialize_note(note)) == note` for a fully-populated `MemoryNote` (every optional field set) and a minimally-populated one. Datetime fields preserve precision to seconds.
  - Special characters in `content` (multiline, unicode, `---` lines, YAML-significant characters) survive round-trip.

**Step 3 — `MemoryStore` constructor and `store_note`**
- Create `src/phosphene/memory_store/store.py` with the `MemoryStore` class.
- `__init__(config: MemoryStoreConfig)`:
  - Creates `vault_path` and the three tier subdirectories if missing.
  - Raises `VaultError` if `vault_path` exists but is not a directory, or is not writable.
  - `embedding_path` is accepted but not exercised in Phase 1 (no embedding writes yet).
- `store_note(note: NoteInput) -> str`:
  - Validates: tier ∈ {1,2,3} else `InvalidTierError`; `len(title) ≤ 150` else `TitleTooLongError`; `0.0 ≤ importance ≤ 1.0` and `0.0 ≤ unresolvedness ≤ 1.0` else `InvalidScoreError`.
  - Sets `created_at = updated_at = now()`, generates `note_id`, sets `link_count = len(note.links)` (outbound only — Phase 1 limitation), `decay_deadline = None` for now (Phase 4 will populate this).
  - Writes the file via `serialize_note`. Returns the `note_id`.
- Tests (`tests/memory_store/test_store_note.py`):
  - Stores notes on each of T1/T2/T3; file appears at the expected tier path; ID returned is the file's basename minus `.md`.
  - Each validation error fires for the right invalid input; valid inputs at the boundaries (title len = 150, importance = 0.0 and 1.0) succeed.
  - Two `store_note` calls with the same title in the same second still produce distinct IDs (covered by the hash suffix).
  - Constructor raises `VaultError` for a path pointing at an existing file.

**Step 4 — `get_note` and `update_note`**
- `get_note(note_id: str) -> MemoryNote`:
  - Searches the three tier subdirectories for `<note_id>.md`. Raises `NoteNotFoundError` if absent.
  - Returns the parsed `MemoryNote`. `link_count` reflects outbound links only (Phase 2 will add inbound counting). `decay_deadline` is `None` (Phase 4).
- `update_note(note_id: str, patch: NotePatch) -> MemoryNote`:
  - Loads the note, applies non-`None` `NotePatch` fields (full replace semantics for `links` and `tags`), refreshes `updated_at`, writes back, and returns the updated note.
  - Validation mirrors `store_note`: range check for `importance`/`unresolvedness`, length check for `title`. Tier is immutable in `NotePatch` (no field).
  - Raises `NoteNotFoundError` for a missing id; `InvalidScoreError`/`TitleTooLongError` for bad patch values.
- Tests (`tests/memory_store/test_crud.py`):
  - Round-trip: store → get → fields match input.
  - Update applies each patchable field independently; non-patched fields are unchanged; `updated_at` advances; file content reflects the update.
  - Empty patch (all `None`) is a no-op aside from `updated_at`.
  - Errors fire correctly for missing id and invalid patch values.

#### Phase 1 exit criteria
- All four steps' tests pass under `pytest`.
- The Memory Store package can be imported from a fresh process without any optional Phase 2/3/4 features being touched.
- Every dataclass and exception named in `ARCH_memory_store.md` is present in code, even if some fields are populated trivially in Phase 1 (e.g., `link_count` is outbound-only, `decay_deadline` is `None`). Later phases will fill in the behavior; the surface is stable.
- No regressions in the ARCH contract: signatures of `store_note`, `get_note`, `update_note`, and the constructor match the ARCH file exactly.

<!-- HISTORY — Worker: stop reading here. Everything below is completed phase history. -->
