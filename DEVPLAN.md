---
module: MEMORY_STORE
phase: 3
phase_title: Embedding search and graph operations
step: null
mode: Review
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
  - **Test environment** — system Python is 3.11.2 with no pytest; `pip install --user` is blocked (externally-managed-environment); `python3 -m venv .venv` creates binaries that can't run on this NTFS-3G mount (no exec bits, can't chmod). Working pattern: `pip install --target .python_deps` (already pre-installed in repo root) and run with `PYTHONPATH=src:.python_deps python3 -m pytest tests/memory_store`. Do NOT recreate `.venv` or reinstall — `.python_deps/` is gitignored and persists.

## Current Status

- **Phase** — 3 — Embedding search and graph operations
- **Focus** — Phase 3 review
- **Blocked/Broken** — None

## Module 1: Memory Store

Four-phase plan (matching ARCH_memory_store.md public API surface). Phase 4 is sketched here for orientation only and will get its own Phase Plan when reached.

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (in progress)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`. Also wires up `embedding_path` (accepted-but-unused since Phase 1) so embeddings actually round-trip through the public API.
- **Phase 4** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`.

### Phase 3 Step Plan

Regime: Build. Five steps. Each step ends with passing `tests/memory_store` and a commit.

**Step 1 — Embedding persistence (binary storage)** — Complete. See DEVLOG "Step 1: Embedding persistence (binary storage)" entry.

- New private module `phosphene.memory_store.embeddings` exposing two helpers backed by `numpy.save` / `numpy.load`:
  - `save_embedding(embedding_path: Path, note_id: str, embedding: ndarray) -> None` — writes `<embedding_path>/<note_id>.npy`. Creates the directory on first use.
  - `load_embedding(embedding_path: Path, note_id: str) -> ndarray | None` — returns the stored vector or `None` if no file exists.
  - Embeddings can only be *set* via `NoteInput.embedding` or `NotePatch.embedding`, never cleared in Phase 3 (`NotePatch` fields apply only when non-None per ARCH). A `delete_embedding` helper is deferred to Phase 4 alongside `run_decay`.
- `MemoryStore.store_note` writes the embedding when both `note.embedding is not None` and `self.embedding_path is not None`. When `embedding_path is None`, the embedding is silently discarded (preserves existing Phase 1 behavior — accepted but not persisted). When `embedding is None` no file is written.
- `MemoryStore.update_note` writes the embedding when `patch.embedding is not None` and `self.embedding_path is not None`. Same null-path rule as above.
- `MemoryStore.get_note` and `MemoryStore.query_notes` populate `MemoryNote.embedding` by calling `load_embedding` after `parse_note` (which still hardcodes `embedding=None`). When `embedding_path is None` or no file exists, the field stays `None`.
- No frontmatter changes; no markdown round-trip changes. Embeddings live entirely in their sidecar files.
- Tests (`tests/memory_store/test_embedding_persistence.py`):
  - store + get round-trip preserves vector values (`numpy.array_equal`)
  - `update_note(NotePatch(embedding=v2))` overwrites the stored vector
  - `get_note` returns `embedding=None` when none was stored
  - `query_notes` populates `embedding` on returned notes (mixed with embedding-less notes in same result set)
  - `embedding_path=None` accepts an embedding on `store_note` and `update_note` without persisting (subsequent `get_note` returns `None`)
  - restart (new `MemoryStore` over same `vault_path` and `embedding_path`) loads embeddings from disk on next `get_note`
  - directory created lazily — passing an `embedding_path` that does not yet exist works on first `store_note`

**Step 2 — `search_by_embedding`** — Complete. See DEVLOG "Step 2: `search_by_embedding`" entry.

- Implement `MemoryStore.search_by_embedding(embedding: ndarray, tier: int | None = None, limit: int = 10) -> list[tuple[MemoryNote, float]]`:
  - Validates `tier` in `{1, 2, 3}` when given; raises `InvalidTierError` otherwise.
  - Iterates index entries (filtered by tier if given) and loads each note's stored embedding via `load_embedding`. Notes without a stored embedding are skipped — not an error.
  - Cosine similarity computed in numpy: `dot(a, b) / (||a|| * ||b||)`. Zero-norm query and zero-norm stored vectors are skipped (return -inf score) so they never pollute results.
  - On the first stored embedding encountered, dimensionality is checked against the query. If they differ, raise `DimensionMismatchError`. (We check on every comparison; the first mismatch raises.)
  - Returns `[(MemoryNote, similarity)]` sorted by similarity descending, truncated to `limit`. Returned notes carry inbound-augmented `link_count` and the loaded `embedding`.
  - Empty list when no notes have stored embeddings (including when `embedding_path` is None — no error).
- Tests (`tests/memory_store/test_search.py`):
  - Ranking: three notes with known orthogonal-ish vectors → query returns them ranked correctly
  - `tier` filter restricts results to the requested tier
  - `limit` truncates correctly (e.g., 5 candidates, limit=2 → 2 results)
  - Mixed vault (some notes with embeddings, some without) → only embedding-bearing notes appear in results
  - `DimensionMismatchError` when query vector has different shape than stored vectors
  - Empty result list when `embedding_path is None`
  - Empty result list when no notes have stored embeddings (vault populated but no `embedding=` arg ever passed)
  - `tier=4` raises `InvalidTierError`
  - zero-norm query and stored vectors are excluded from results
  - returned notes include loaded embeddings and inbound-augmented `link_count`

**Step 3 — `add_links`** — Complete. See DEVLOG "Step 3: `add_links`" entry.

- Implement `MemoryStore.add_links(source_id: str, target_ids: list[str]) -> None`:
  - Validates that source and every target id exist in the index. If any are missing, raise `NoteNotFoundError` *before* any disk write (atomic — no partial application).
  - Loads the source note via the index path, computes the new outbound list as the existing `links` plus any `target_ids` not already present (dedup, order: existing first then new). Self-links (`source_id` in `target_ids`) are silently dropped.
  - Persists the source note via `serialize_note` (refreshing `updated_at` like `update_note` does) and re-registers it with the index — this updates inbound counts for any newly added targets.
  - Empty `target_ids` is a no-op (no disk write, no `updated_at` bump).
- Tests (`tests/memory_store/test_links.py` — new file):
  - Adds new outbound links to a source note; subsequent `get_note(source).links` reflects the union
  - Duplicate target ids in `target_ids` are deduplicated; pre-existing links are not re-added
  - `link_count` on source = inbound + outbound (after the new outbound links land)
  - `link_count` on each new target increments by exactly 1 inbound from this source
  - `NoteNotFoundError` when source is unknown — no writes happen
  - `NoteNotFoundError` when *any* target is unknown — no writes happen (atomicity check: confirm source's `links` and `updated_at` are unchanged)
  - Empty `target_ids` → no-op (source `updated_at` unchanged)
  - Self-link target silently dropped
  - Restart (`new MemoryStore` over same vault) reloads the augmented links

**Step 4 — `get_linked`** — Complete. See DEVLOG "Step 4: `get_linked`" entry.

- Implement `MemoryStore.get_linked(note_id: str, depth: int = 1) -> list[MemoryNote]`:
  - Validates `depth` in `[1, 3]` — `depth < 1` or `depth > 3` raises `ValueError`.
  - `NoteNotFoundError` if `note_id` is not in the index.
  - BFS frontier starting from `note_id`. At each level, expand to the union of outbound links (`note.links`) and inbound edges (`index.inbound_for(note_id)` — entries that list this id in their outbound `links`). Exclude already-visited ids and the starting id itself.
  - Returns the deduplicated `MemoryNote` list of all notes reached at depths 1..N (excluding origin), each with inbound-augmented `link_count` and loaded `embedding`. Order is BFS visitation order (depth-1 first, then depth-2, etc.).
  - Index needs a small helper: `Index.inbound_for(note_id) -> list[str]` returning ids of notes whose outbound `links` contain `note_id`. The current Index already tracks this internally via inbound counts; this just exposes the source ids.
- Tests (`tests/memory_store/test_links.py` — extend):
  - Depth=1 returns direct outbound and direct inbound neighbours (e.g., A→B and C→A, `get_linked(A, 1)` returns `[B, C]` with no duplication)
  - Depth=2 reaches second-degree neighbours; results dedup across paths
  - Depth=3 reaches third-degree; visiting order remains BFS
  - Starting note excluded from results even when reachable via a cycle
  - Cycles do not loop forever; visited-set prevents re-expansion
  - `ValueError` on `depth=0` and `depth=4`
  - `NoteNotFoundError` on unknown `note_id`
  - Isolated note returns `[]`

**Step 5 — `get_personality_context`** — Complete. See DEVLOG "Step 5: `get_personality_context`" entry.

- Implement `MemoryStore.get_personality_context() -> PersonalityContext`:
  - Considers Tier 3 notes via the index. A Tier 3 note is **superseded** when some other note's `supersedes` field equals its `note_id`; superseded notes are excluded.
  - Builds the superseded set by scanning index entries (`supersedes` is currently parsed from frontmatter into the `MemoryNote`, but the `IndexEntry` does not carry it). Step 5 extends the `Index` private record to track each entry's `supersedes` value (still not added to the public `IndexEntry` dataclass — internal only).
  - Loads each surviving note via the existing index-backed read path (fresh on every call — never cached). Returned notes carry inbound-augmented `link_count` and loaded `embedding`.
  - `version_id`: deterministic SHA-1 of a stable representation of the selected set — `||\0`-joined `note_id|updated_at_iso` pairs, sorted by `note_id`. Empty set has its own deterministic id (e.g., hash of empty string). Same state → same id; any add/update/supersede on a Tier 3 note changes the id.
  - Tier 1 and Tier 2 notes are excluded from `personality_files`.
- Tests (`tests/memory_store/test_personality_context.py`):
  - Empty store → `personality_files == []`, `version_id` is the deterministic empty-state id
  - All Tier 3 notes returned when none are superseded
  - A Tier 3 note that is the `supersedes` target of *another* Tier 3 note is excluded (test setup: write the markdown directly so frontmatter has `supersedes:` set, then re-init `MemoryStore` — Phase 4 will provide the `supersede()` method that produces this state)
  - Tier 1 and Tier 2 notes are not included
  - Two consecutive calls on identical state return identical `version_id`
  - `version_id` changes after `store_note` or `update_note` on a Tier 3 note
  - Returned notes have `embedding` populated when present and inbound-augmented `link_count`
  - Method is loaded fresh per call (mutate vault on disk between calls; second call sees the new state — same as `query_notes` does)

### Phase 3 Acceptance

- All Phase 1 and Phase 2 tests still pass.
- Public surface added: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`.
- Embedding persistence is wired: `embedding_path` actually stores and loads embeddings on every read path.
- Internal: `Index` exposes inbound source ids and tracks `supersedes` per entry.
- No frontmatter format changes; Phase 1/2 stored notes load unchanged.

<!-- HISTORY — Worker: stop reading here. Everything below is completed phase history. -->
