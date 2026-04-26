# ARCH: Memory Store

## Purpose
Three-tier hierarchical memory for Phosphene. Stores notes as Obsidian-compatible markdown with YAML frontmatter and `[[wikilink]]` backlinks. Provides CRUD, graph-based linking, tier-scoped queries, density metrics, embedding-based search, and scheduled decay. From Phase 2 onward, reads go through a lightweight index layer; in Phase 1 (CRUD-only), single-note reads scan the tier subdirectories. All writes go through typed APIs. No other module reads or writes note files directly.

## Public API

### Types

```python
@dataclass
class MemoryStoreConfig:
    vault_path: str                         # root directory for note files
    embedding_path: str | None = None       # directory for embedding vectors. None = no embedding storage.
    tier1_base_retention_days: int = 30     # Tier 1 decay window (no links)
    tier1_extended_retention_days: int = 90  # Tier 1 decay window (2+ links)
    tier3_superseded_retention_days: int = 90  # retention of superseded Tier 3 versions
    link_density_threshold: int = 2         # inbound link count required for extended retention

@dataclass
class NoteInput:
    tier: int                               # 1, 2, or 3
    content: str                            # markdown body
    title: str                              # max 150 chars — used in index
    importance: float = 0.0                 # [0.0, 1.0]
    unresolvedness: float = 0.0             # [0.0, 1.0] — 0 = resolved
    links: list[str] = field(default_factory=list)   # note_ids of related notes
    tags: list[str] = field(default_factory=list)
    source: str | None = None               # provenance: "ingestion", "distillation", "seeding", "feedback"
    friction_target: str | None = None      # note_id this creates friction with
    embedding: ndarray | None = None        # pre-computed embedding vector (consumer provides)
    attractor_relevance: float | None = None  # [0.0, 1.0] — modifies decay rate. None = default.
    cluster_group: str | None = None        # Tier 2 only: cluster identifier set by Distillation

@dataclass
class MemoryNote:
    note_id: str
    tier: int
    content: str
    title: str
    importance: float
    unresolvedness: float
    links: list[str]                        # outbound link note_ids
    tags: list[str]
    source: str | None
    friction_target: str | None
    embedding: ndarray | None
    attractor_relevance: float | None
    cluster_group: str | None
    supersedes: str | None                  # note_id of the version this replaced (Tier 3)
    created_at: datetime
    updated_at: datetime
    link_count: int                         # computed: inbound + outbound links
    decay_deadline: datetime | None         # None = no expiry (current Tier 3, or manually pinned)

@dataclass
class IndexEntry:
    note_id: str
    tier: int
    title: str                              # max 150 chars
    importance: float
    unresolvedness: float
    link_count: int
    tags: list[str]
    created_at: datetime

@dataclass
class DensityMetrics:
    note_count: int                         # total across all tiers
    tier_counts: dict[int, int]             # {1: n, 2: n, 3: n}
    mean_link_degree: float                 # average (inbound + outbound) links per note
    cluster_count: int                      # distinct cluster_group values in Tier 2
    unresolved_count: int                   # notes with unresolvedness > 0.5
    max_unresolvedness: float               # highest unresolvedness score across all notes

@dataclass
class PersonalityContext:
    personality_files: list[MemoryNote]     # current (non-superseded) Tier 3 notes
    version_id: str                         # snapshot identifier for audit trail

@dataclass
class NoteQuery:
    tier: int | None = None
    min_importance: float | None = None
    min_unresolvedness: float | None = None
    tags: list[str] | None = None           # match notes containing any of these tags
    source: str | None = None
    since: datetime | None = None           # created_at >= since
    until: datetime | None = None           # created_at <= until
    limit: int = 50
    order_by: str = "created_at"            # "created_at", "importance", "unresolvedness", "link_count"
    descending: bool = True

@dataclass
class NotePatch:
    content: str | None = None
    title: str | None = None
    importance: float | None = None
    unresolvedness: float | None = None
    links: list[str] | None = None          # replaces full link list
    tags: list[str] | None = None           # replaces full tag list
    embedding: ndarray | None = None
    attractor_relevance: float | None = None

@dataclass
class DecayReport:
    expired_count: int
    expired_ids: list[str]
    extended_count: int                     # notes with retention extended due to link density
    tier_breakdown: dict[int, int]          # expired notes per tier
```

### Constructor

- **Signature:** `MemoryStore(config: MemoryStoreConfig)`
- **Parameters:**
  - config: MemoryStoreConfig — vault path, embedding path, decay windows
- **Behavior:** Opens (or creates) the vault directory. From Phase 2 onward, rebuilds the index from existing note frontmatter on first initialization and updates it incrementally on subsequent writes; in Phase 1 the constructor only ensures the vault and tier subdirectories exist.
- **Errors:**
  - `VaultError` — vault_path is not writable or not a directory

### store_note

- **Signature:** `store_note(note: NoteInput) -> str`
- **Parameters:**
  - note: NoteInput — tier must be 1, 2, or 3. title max 150 chars.
- **Returns:** str — generated note_id (stable, unique)
- **Errors:**
  - `InvalidTierError` — tier not in {1, 2, 3}
  - `TitleTooLongError` — title exceeds 150 chars
  - `InvalidScoreError` — importance or unresolvedness outside [0.0, 1.0]

### get_note

- **Signature:** `get_note(note_id: str) -> MemoryNote`
- **Parameters:**
  - note_id: str
- **Returns:** MemoryNote with computed fields (link_count, decay_deadline)
- **Errors:**
  - `NoteNotFoundError` — no note with this id

### update_note

- **Signature:** `update_note(note_id: str, patch: NotePatch) -> MemoryNote`
- **Parameters:**
  - note_id: str — note to update
  - patch: NotePatch — only non-None fields are applied
- **Returns:** MemoryNote — updated. `updated_at` is refreshed.
- **Errors:**
  - `NoteNotFoundError` — no note with this id
  - `InvalidScoreError` — importance or unresolvedness outside [0.0, 1.0]

### get_index

- **Signature:** `get_index(tier: int | None = None) -> list[IndexEntry]`
- **Parameters:**
  - tier: int | None — filter to a single tier. None returns all tiers.
- **Returns:** list[IndexEntry] — lightweight entries (title ≤ 150 chars). Sorted by created_at descending.
- **Errors:**
  - `InvalidTierError` — tier not in {1, 2, 3}

### query_notes

- **Signature:** `query_notes(query: NoteQuery) -> list[MemoryNote]`
- **Parameters:**
  - query: NoteQuery — filter, sort, and limit parameters
- **Returns:** list[MemoryNote] — matching notes, sorted per `query.order_by`
- **Errors:**
  - `InvalidTierError` — query.tier not in {1, 2, 3}

### search_by_embedding

- **Signature:** `search_by_embedding(embedding: ndarray, tier: int | None = None, limit: int = 10) -> list[tuple[MemoryNote, float]]`
- **Parameters:**
  - embedding: ndarray — 1-D query vector, same dimensionality as stored embeddings
  - tier: int | None — restrict search to a single tier. None searches all.
  - limit: int — max results (default 10)
- **Returns:** list of (MemoryNote, similarity_score) tuples, sorted by cosine similarity descending. Only notes with stored embeddings are searched.
- **Errors:**
  - `DimensionMismatchError` — query vector dimensionality differs from stored vectors
  - Returns empty list if no notes have stored embeddings (not an error)

### get_personality_context

- **Signature:** `get_personality_context() -> PersonalityContext`
- **Parameters:** none
- **Returns:** PersonalityContext containing current (non-superseded) Tier 3 notes, loaded fresh on each call (never cached from a previous call). Empty `personality_files` list if no Tier 3 notes exist.
- **Errors:** none

**Provisional:** Whether the Generator should also receive relevant Tier 2 patterns alongside Tier 3 is unresolved. Currently this method returns Tier 3 only. If Tier 2 patterns are needed, the Generator can query them separately via `query_notes(NoteQuery(tier=2, ...))` or `search_by_embedding(...)`. Resolve during ARCH_generator.md.

### get_density_metrics

- **Signature:** `get_density_metrics() -> DensityMetrics`
- **Parameters:** none
- **Returns:** DensityMetrics — current snapshot. Cheap to compute (derived from index).
- **Errors:** none

### add_links

- **Signature:** `add_links(source_id: str, target_ids: list[str]) -> None`
- **Parameters:**
  - source_id: str — note gaining the outbound links
  - target_ids: list[str] — notes being linked to. Duplicates ignored.
- **Returns:** None. Updates `link_count` on all affected notes. Backlinks are symmetric — linking A→B also makes B discoverable from A via `get_linked`.
- **Errors:**
  - `NoteNotFoundError` — source_id or any target_id not found

### get_linked

- **Signature:** `get_linked(note_id: str, depth: int = 1) -> list[MemoryNote]`
- **Parameters:**
  - note_id: str — starting note
  - depth: int — traversal depth. 1 = direct links only. Max 3.
- **Returns:** list[MemoryNote] — all notes reachable within depth, deduplicated, excluding the starting note
- **Errors:**
  - `NoteNotFoundError` — note_id not found
  - `ValueError` — depth < 1 or depth > 3

### supersede

- **Signature:** `supersede(note_id: str, new_content: str, new_title: str, change_summary: str) -> MemoryNote`
- **Parameters:**
  - note_id: str — the Tier 3 note being replaced
  - new_content: str — replacement markdown content
  - new_title: str — replacement title, max 150 chars
  - change_summary: str — what changed and why (stored in new version's frontmatter for audit)
- **Returns:** MemoryNote — the new version. `supersedes` points to the old note_id. The old version receives a `decay_deadline` per `config.tier3_superseded_retention_days`. Links, tags, and importance carry forward from the old note unless the new content changes them.
- **Errors:**
  - `NoteNotFoundError` — note_id not found
  - `TierMismatchError` — note is not Tier 3
  - `AlreadySupersededError` — note has already been superseded by another version

### run_decay

- **Signature:** `run_decay() -> DecayReport`
- **Parameters:** none
- **Returns:** DecayReport — summary of expired notes

Decay rules (enforced internally, parameters from `MemoryStoreConfig`):

| Tier | Rule | Default |
|------|------|---------|
| 1 | Base retention from `created_at`. Notes with ≥ `link_density_threshold` inbound links get extended retention. `attractor_relevance` (if set) further extends proportionally. | 30 days base, 90 days extended |
| 2 | Unpromoted notes retained for one additional distillation cycle window. Expired after two consecutive non-promotions. | Cycle window = 30 days |
| 3 | Superseded versions retained per `tier3_superseded_retention_days`. Current (non-superseded) versions never decay. | 90 days |

- **Errors:** none

## Inputs

- **NoteInput** — from Attention Filter (Tier 1 annotated fragments), Distillation (Tier 2 clusters and Tier 3 personality files), Seeding (initial Tier 2/3 content), Feedback Collector (feedback events stored as Tier 1 notes with `source="feedback"`)
- **NotePatch** — from any module updating note metadata (importance, unresolvedness, links, tags)
- **ndarray** — pre-computed embedding vectors, provided by consumer alongside note content or as search queries. The Memory Store does not compute embeddings — consumers use toolkit/embedding and pass the results.

## Outputs

- **MemoryNote** — full note with computed fields (`link_count`, `decay_deadline`)
- **IndexEntry** — lightweight pointer (title ≤ 150 chars). Designed to fit in LLM context as a navigation map without loading note content.
- **DensityMetrics** — consumed by Attention Filter (prompt-to-structure transition weighting) and Scheduler (tension-responsive scheduling)
- **PersonalityContext** — consumed by Generator. Loaded fresh per generation call, never cached.
- **DecayReport** — consumed by logging/monitoring

## State

- **Note files:** Obsidian-compatible markdown with YAML frontmatter and `[[wikilink]]` backlinks. One `.md` file per note, organized by tier subdirectory.
- **Index:** In-memory, derived from frontmatter. Rebuilt on startup; updated incrementally on writes. All read queries go through the index first.
- **Embedding vectors:** Stored separately from markdown files (binary format), keyed on note_id. Only present for notes where the consumer provided an embedding.
- **Supersession chain:** Tier 3 version history maintained via `supersedes` pointers. Old versions remain readable until their `decay_deadline`.
- **Concurrency:** Supports concurrent reads. Writes are serialized (single writer). Distillation runs as a read-only subprocess — it reads via the public API and writes back results through `store_note` / `supersede` at completion.

Only the Memory Store writes to the vault. Other modules interact exclusively through this API.

## Usage Example

```python
from memory_store import MemoryStore, MemoryStoreConfig, NoteInput, NoteQuery
from datetime import datetime, timedelta

store = MemoryStore(MemoryStoreConfig(vault_path="./memory", embedding_path="./memory/embeddings"))

# Attention Filter stores a Tier 1 annotated fragment
note_id = store.store_note(NoteInput(
    tier=1,
    content="Luhmann's Zettelkasten produced surprise through network density, not through "
            "any individual note's quality. The critical mass threshold is the key variable.",
    title="Zettelkasten: network density → surprise",
    importance=0.7,
    unresolvedness=0.4,
    links=["note-042"],
    tags=["memory-architecture", "emergence"],
    source="ingestion",
    friction_target="note-038",
    embedding=query_embedding,  # pre-computed via toolkit/embedding
))

# Attention Filter checks density metrics for prompt-to-structure blend
metrics = store.get_density_metrics()
structure_weight = min(1.0, metrics.mean_link_degree / 5.0)

# Generator loads fresh personality context
ctx = store.get_personality_context()
for pf in ctx.personality_files:
    pass  # inject into LLM context

# Distillation queries recent Tier 1 notes for synthesis
recent = store.query_notes(NoteQuery(
    tier=1,
    since=datetime.now() - timedelta(days=7),
    min_importance=0.3,
    order_by="importance",
))

# Distillation supersedes a Tier 3 personality file
new_version = store.supersede(
    note_id="personality-voice",
    new_content="Updated voice description reflecting register fluency...",
    new_title="Voice: precision with register fluency",
    change_summary="Shifted from 'precision as primary' to 'precision with register fluency' "
                   "based on 3 weeks of pattern layer evidence.",
)

# Scheduled maintenance
report = store.run_decay()
print(f"Expired {report.expired_count} notes ({report.tier_breakdown})")
```
