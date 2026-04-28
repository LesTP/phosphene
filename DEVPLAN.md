---
module: MEMORY_STORE
phase: 4
phase_title: Decay, supersession, and density metrics
step: 2 of 4
mode: Code
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

- **Phase** — 4 — Decay, supersession, and density metrics
- **Focus** — Step 2: `supersede` — add `change_summary` to `MemoryNote`, implement Tier 3 supersession, and audit the contract evolution as D-14.
- **Blocked/Broken** — None

## Module 1: Memory Store

Four-phase plan (matching ARCH_memory_store.md public API surface).

- **Phase 1 (complete)** — Core data model and CRUD: types, errors, vault I/O, store/get/update for individual notes. See DEVLOG "Phase 1 Completion" entry.
- **Phase 2 (complete)** — Index layer and queries: `get_index`, `query_notes`, inbound link counting, and index-backed `get_note` / `update_note`. See DEVLOG "Phase 2 Completion" entry.
- **Phase 3 (complete)** — Embedding search and graph operations: `search_by_embedding`, `add_links`, `get_linked`, `get_personality_context`, plus sidecar embedding persistence on read paths. See DEVLOG "Phase 3 Completion" entry.
- **Phase 4 (in progress)** — Decay, supersession, and density metrics: `supersede`, `run_decay`, `get_density_metrics`.

### Phase 4 Step Plan

Regime: Build. Four steps. Each step ends with passing `tests/memory_store` and a commit.

**Step 1 — `get_density_metrics`**

- Extend `phosphene.memory_store.index.IndexedNote` with `cluster_group: str | None`. Populate it in `Index.register` from `MemoryNote.cluster_group`. No public `IndexEntry` change.
- Implement `MemoryStore.get_density_metrics() -> DensityMetrics` purely from the in-memory index — no markdown reads:
  - `note_count` = `len(self._index.entries)`
  - `tier_counts` = `{1: n1, 2: n2, 3: n3}` — every tier key present even when zero (keys 1/2/3 always populated)
  - `mean_link_degree` = mean over all notes of `inbound_count(id) + len(entry.links)`. `0.0` when `note_count == 0`.
  - `cluster_count` = number of distinct non-`None` `cluster_group` values across **Tier 2** entries only
  - `unresolved_count` = entries with `unresolvedness > 0.5` (strict greater-than, ARCH-stated threshold)
  - `max_unresolvedness` = max across all entries (`0.0` when empty)
- Tests (`tests/memory_store/test_density.py` — new file):
  - empty vault returns zeros, all tier keys present, `max_unresolvedness == 0.0`
  - tier_counts reflects mixed-tier vault accurately
  - `mean_link_degree` averages inbound + outbound across all notes (verify with a hand-computed example: a 4-note graph with two A→B and one C→A links)
  - `cluster_count` counts distinct Tier 2 `cluster_group` values; ignores `None`; ignores cluster_group set on Tier 1/3
  - `unresolved_count` strict `> 0.5` (a note at exactly 0.5 is *not* counted)
  - `max_unresolvedness` returns the highest score across all tiers
  - density metrics reflect freshly stored notes immediately (no rebuild needed); confirm after `add_links` updates inbound counts

**Step 2 — `supersede`**

- Contract evolution: add `change_summary: str | None = None` to `MemoryNote` (defaulted everywhere) and round-trip it through `serialize_note` / `parse_note`. No `NoteInput` change — `change_summary` is set only via `supersede`. Log as **D-14** in DECISIONS.md when this step lands. ARCH already says "stored in new version's frontmatter for audit"; this is the smallest faithful implementation.
- Implement `MemoryStore.supersede(note_id: str, new_content: str, new_title: str, change_summary: str) -> MemoryNote`:
  - `NoteNotFoundError` if `note_id` is not in the index.
  - `TierMismatchError` if the note's tier is not 3.
  - `AlreadySupersededError` if any other Tier 3 entry's `supersedes` already points at `note_id`.
  - Validate new title length (`TitleTooLongError`) before any disk write.
  - Generate a new note id from `new_title` + the current timestamp (same `generate_note_id` pattern as `store_note`).
  - Carry forward from the old note: `links`, `tags`, `importance`, `unresolvedness`, `attractor_relevance`, `cluster_group`, `friction_target`, `embedding`, `source` (the new version inherits the old's metadata; only content/title/`change_summary`/`supersedes` are new).
  - New note: `tier=3`, `supersedes=<old_note_id>`, `change_summary=<summary>`, `created_at=now`, `updated_at=now`, `decay_deadline=None`. Persist via `serialize_note`; if `embedding` carried forward and `embedding_path` is set, save the sidecar copy.
  - Old note: set `decay_deadline = now + timedelta(days=config.tier3_superseded_retention_days)`. Persist via `serialize_note` (re-write to disk), then re-register with the index. `change_summary` on the old note remains `None`.
  - Return the new note via `_load_note` (so it carries inbound-augmented `link_count`).
- Tests (`tests/memory_store/test_supersede.py` — new file):
  - basic supersede: old note's `supersedes` stays `None`, new note's `supersedes` matches old id; both readable via `get_note`
  - new note's `change_summary` matches input; old note's `change_summary` is `None`
  - new note carries forward links, tags, importance, unresolvedness, attractor_relevance, cluster_group, friction_target, source from the old note
  - new note carries forward embedding when one is stored (round-trip verified via `get_note(new_id).embedding`)
  - old note gets `decay_deadline ≈ now + tier3_superseded_retention_days` (assertion within ±2s)
  - `TierMismatchError` for Tier 1 and Tier 2 source notes
  - `AlreadySupersededError` when calling supersede twice on the same source id
  - `NoteNotFoundError` for unknown source id
  - `TitleTooLongError` for >150 char `new_title` — old note unchanged, no new file written
  - `get_personality_context()` excludes the old (now superseded) note and includes the new one
  - `change_summary` survives `parse_note` round-trip on freshly loaded vault

**Step 3 — `run_decay` — Tier 1 rules + DecayReport infrastructure**

- Add a private `delete_embedding(embedding_path: Path, note_id: str) -> None` helper to `phosphene.memory_store.embeddings` that removes the sidecar file when present (and is a no-op when it's missing or `embedding_path` is `None`).
- Add private `MemoryStore._expire_note(note_id: str) -> None` that: looks up the index path, deletes the markdown file, deletes the embedding sidecar (via the helper), and removes the entry from `self._index.entries` (then `rebuild_inbound`).
- Implement `MemoryStore.run_decay() -> DecayReport`. Phase 4 Step 3 covers Tier 1 only; Tier 2 and Tier 3 are filled in by Step 4. Behavior for Tier 1:
  - For each Tier 1 entry, compute `effective_days`:
    - base = `config.tier1_base_retention_days`
    - extended = `config.tier1_extended_retention_days` if `inbound_count(id) >= config.link_density_threshold` else `base`
    - apply attractor multiplier: `effective = extended * (1 + (attractor_relevance or 0.0))`
  - A note expires when `now - created_at > effective_days`.
  - The `DecayReport.extended_count` counts Tier 1 notes whose retention was extended *but did not yet expire* (i.e., where extended/attractor moved them past the base deadline they would have hit). Notes already expired even with extension are counted as expired, not extended.
  - Skeleton DecayReport returned: `expired_count`, `expired_ids`, `extended_count`, `tier_breakdown={1: n1, 2: 0, 3: 0}` (Step 4 fills in tiers 2 and 3).
- Tests (`tests/memory_store/test_decay.py` — new file, Tier 1 only this step):
  - empty vault → empty report (`expired_count=0`, `expired_ids=[]`, `extended_count=0`, `tier_breakdown={1: 0, 2: 0, 3: 0}`)
  - Tier 1 note older than `base_retention_days` with no inbound links expires; markdown and embedding sidecar are removed; `get_note` raises `NoteNotFoundError`
  - Tier 1 note older than `base_retention_days` with `>= link_density_threshold` inbound links survives and is counted in `extended_count`
  - Tier 1 note older than `extended_retention_days` with the link threshold met still expires
  - Attractor extension: a note with `attractor_relevance=1.0` (extended × 2) survives a window where `attractor_relevance=None` would expire
  - Notes where `now - created_at == retention` are *not* expired (strict `>`)
  - DecayReport `expired_ids` matches the actual deleted set; index no longer contains those ids
  - Re-running `run_decay` immediately after a sweep is a no-op (everything already eligible was removed)
  - Embedding sidecar for an expired note is gone; sidecars for surviving notes are intact
  - Test fixtures simulate age by writing notes with backdated `created_at` directly, then reloading via a fresh `MemoryStore` — matches the existing `test_query.py` fixed-timestamp approach.

**Step 4 — `run_decay` — Tier 2 + Tier 3 rules and full DecayReport**

- Contract evolution: add `tier2_cycle_window_days: int = 30` to `MemoryStoreConfig`. Update `ARCH_memory_store.md` MemoryStoreConfig field list and the Tier 2 row in the decay-rules table to read "Two cycle windows from `created_at`. Distillation may extend retention via `update_note` (importance/attractor_relevance) ahead of the second window." Log as **D-15** in DECISIONS.md when this step lands.
- Extend `run_decay` for Tier 2 and Tier 3:
  - **Tier 2:** a note expires when `now - created_at > 2 * config.tier2_cycle_window_days`. No link-threshold or attractor extension at this layer (Distillation owns promotion semantics; Memory Store's job is to evict by age unless metadata moves the note out of Tier 2). Notes expire by Tier 2 rule even if they have inbound links.
  - **Tier 3:** only superseded versions decay. A Tier 3 note expires when `decay_deadline is not None` and `now > decay_deadline`. Current (non-superseded) Tier 3 notes never expire.
  - `tier_breakdown` is filled in for tiers 2 and 3; `expired_count` and `expired_ids` aggregate across all three tiers.
- Tests (`tests/memory_store/test_decay.py` — extend):
  - Tier 2 note older than `2 * cycle_window` expires; Tier 2 note inside the window survives even with no links
  - Tier 2 expiry ignores inbound links and `attractor_relevance` (regression: a Tier 2 note that *would* have been extended under Tier 1 rules still expires on schedule)
  - Tier 3 superseded note past `decay_deadline` expires; the supersession chain is severed — `get_note(new_id).supersedes` still references the (now deleted) old id literal but the index no longer contains the old id (acceptable; chain history lives in the new note's frontmatter)
  - Tier 3 superseded note before `decay_deadline` survives
  - Tier 3 current (non-superseded) note never expires regardless of age
  - Mixed run: a vault with expirations across all three tiers reports the union in `expired_ids` and matching counts in `tier_breakdown`
  - `extended_count` only counts Tier 1 extensions; Tier 2/3 do not contribute to it
  - After a sweep, `get_density_metrics()` reflects the reduced `note_count` and `tier_counts`

**End of Phase 4:** `/phase-review` then `/phase-complete`. Review must verify: no public-API drift beyond `change_summary` (D-14) and `tier2_cycle_window_days` (D-15); `get_density_metrics` is index-only and cheap; `run_decay` cleans both markdown and embedding sidecars; supersession chain semantics align with `get_personality_context`.

<!-- HISTORY --> <!-- Worker: stop reading here. Everything below is completed phase history. -->
