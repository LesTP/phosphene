# ARCH: Seeding

## Purpose
One-time corpus-to-personality pipeline. Ingests the human's writing corpus (multiple source types), extracts a knowledge graph, and produces initial Memory Store content: Tier 2 pattern clusters (characteristic tensions, associative networks) and Tier 3 personality files (attractor state). Also produces initial Attention Filter criteria operationalized from the corpus. Runs once at system initialization; output is the starting point the personality develops away from.

## Public API

### Types

```python
@dataclass
class CorpusSource:
    path: str                               # file or directory path
    source_type: str                        # "livejournal", "twitter", "blog", "conversations", "custom"
    format: str                             # "html", "json", "markdown", "text"
    label: str | None = None                # human-readable name (e.g., "LJ archive 2008-2018")

@dataclass
class SeedingConfig:
    sources: list[CorpusSource]             # corpus sources, processed in order
    llm_config: LLMConfig                   # toolkit/llm_client — for ontology extraction, persona generation
    llm_tier: ModelTier = ModelTier.QUALITY  # seeding is quality-critical
    embedding_config: EmbeddingConfig        # toolkit/embedding — for graph construction and clustering
    clustering_config: ClusterConfig | None = None  # toolkit/clustering — for pattern detection. None = defaults.
    max_personality_files: int = 10          # cap on initial Tier 3 files
    max_pattern_clusters: int = 50          # cap on initial Tier 2 clusters
    human_review: bool = True               # pause for human review before writing to Memory Store

@dataclass
class SeedingResult:
    personality_files: list[PersonalityDraft]    # proposed Tier 3 files
    pattern_clusters: list[PatternDraft]         # proposed Tier 2 clusters
    filter_criteria: list[FilterCriterion]       # proposed Attention Filter criteria
    graph_stats: GraphStats                      # knowledge graph summary
    source_stats: dict[str, SourceStats]         # per-source processing summary

@dataclass
class PersonalityDraft:
    title: str                              # max 150 chars
    content: str                            # markdown — personality file content
    derived_from: list[str]                 # source labels that contributed
    confidence: float                       # [0.0, 1.0] — extraction confidence

@dataclass
class PatternDraft:
    title: str                              # max 150 chars
    content: str                            # markdown — pattern description
    cluster_group: str                      # cluster identifier
    member_count: int                       # how many corpus fragments belong to this cluster
    derived_from: list[str]                 # source labels that contributed
    embedding: ndarray                      # cluster centroid embedding

@dataclass
class GraphStats:
    entity_count: int                       # nodes in knowledge graph
    relationship_count: int                 # edges in knowledge graph
    cluster_count: int                      # semantic clusters found
    corpus_fragments: int                   # total text fragments processed

@dataclass
class SourceStats:
    source_label: str
    fragments_extracted: int                # text fragments from this source
    entities_extracted: int                 # graph entities from this source
    processing_errors: int                  # fragments that failed extraction
```

### seed

- **Signature:** `seed(config: SeedingConfig, memory_store: MemoryStore) -> SeedingResult`
- **Parameters:**
  - config: SeedingConfig — corpus sources, model settings, caps
  - memory_store: MemoryStore — target store. Should be empty or near-empty (seeding is initialization).
- **Returns:** SeedingResult — proposed personality files, pattern clusters, and filter criteria. If `config.human_review` is True, these are proposals only — the caller must review and confirm before writing to Memory Store via `commit_seeding`.
- **Errors:**
  - `CorpusError` — source path not found, unreadable, or empty
  - `CorpusFormatError` — source format not recognized or parse failed
  - `LLMAPIError` — LLM call failed during extraction (from toolkit/llm_client)
  - `EmbeddingModelError` — embedding computation failed (from toolkit/embedding)
  - `ClusterInputError` — insufficient fragments for clustering (from toolkit/clustering)

### commit_seeding

- **Signature:** `commit_seeding(result: SeedingResult, memory_store: MemoryStore, approved_personalities: list[int] | None = None, approved_patterns: list[int] | None = None) -> CommitReport`
- **Parameters:**
  - result: SeedingResult — from a prior `seed()` call
  - memory_store: MemoryStore — target store
  - approved_personalities: list[int] | None — indices into `result.personality_files` to accept. None = accept all.
  - approved_patterns: list[int] | None — indices into `result.pattern_clusters` to accept. None = accept all.
- **Returns:** CommitReport
  ```python
  @dataclass
  class CommitReport:
      personality_note_ids: list[str]      # note_ids of stored Tier 3 files
      pattern_note_ids: list[str]          # note_ids of stored Tier 2 clusters
      filter_criteria: list[FilterCriterion]  # criteria for Attention Filter config
      total_links_created: int             # cross-references wired between notes
  ```
- **Errors:**
  - `NoteNotFoundError` — Memory Store write failed (from memory_store.store_note)

**Behavior:**

1. Stores approved personality drafts as Tier 3 notes via `memory_store.store_note`.
2. Stores approved pattern drafts as Tier 2 notes with `cluster_group` set.
3. Wires cross-references between related Tier 2 and Tier 3 notes via `memory_store.add_links`.
4. Returns the committed note_ids and the filter criteria for the caller to use when configuring the Attention Filter.

## Pipeline

The `seed()` call executes a multi-stage pipeline internally. The stages are:

| Stage | Input | Output | Toolkit |
|-------|-------|--------|---------|
| 1. Parse | CorpusSource files | Text fragments with metadata | — |
| 2. Extract | Text fragments | Entities + relationships (knowledge graph) | toolkit/llm_client |
| 3. Embed | Text fragments + entities | Embedding vectors | toolkit/embedding |
| 4. Cluster | Embedding vectors | Semantic clusters | toolkit/clustering |
| 5. Synthesize | Clusters + graph | PatternDrafts (Tier 2) | toolkit/llm_client |
| 6. Distill | PatternDrafts + graph | PersonalityDrafts (Tier 3) | toolkit/llm_client |
| 7. Derive criteria | PersonalityDrafts + corpus patterns | FilterCriterion list | toolkit/llm_client |

### Source-Specific Processing

Each `source_type` has different extraction characteristics:

- **livejournal** — long-form reflective prose. Highest personality signal. Extract: recurring intellectual moves, characteristic tensions, associative patterns, negative space (what is avoided or treated with unusual care).
- **twitter** — mostly links with brief reactions. Treat primarily as an exploratory library: process linked articles where accessible, use reactions as annotations. The pattern of *what was linked across time* is the associative network.
- **blog** — published writing. Similar to livejournal but more curated — may underrepresent characteristic frustrations visible in private writing.
- **conversations** — model conversation history (e.g., Claude projects). Recent, high-signal, unusually explicit about intellectual moves and preferences. The meta-analytical tendency (stepping back to examine conversation structure) is itself a characteristic move.
- **custom** — plain text files. No source-specific processing; fragments are extracted by paragraph or section boundary.

### What the Pipeline Derives

From the corpus, the pipeline extracts:

- **Characteristic intellectual moves** — recurring observation patterns, framing habits, register shifts
- **Associative networks** — cross-domain connections that form initial Tier 2 clusters
- **Negative space** — what is systematically absent, avoided, or treated with unusual caution
- **Characteristic frustrations** — where the writer's instincts and their material are in genuine tension (these become unresolved threads)
- **Initial filter criteria** — the five default criteria (friction, unexpected connection, precision surplus, structural insight, liminal position) operationalized with descriptions specific to this personality

## Inputs

- **CorpusSource** files — the human's writing corpus. Multiple source types processed in signal-density order: conversations and livejournal first, then blogs, then twitter.
- **SeedingConfig** — model settings, caps, review preference.

## Outputs

- **SeedingResult** — proposed Tier 2 pattern clusters, Tier 3 personality files, and Attention Filter criteria. All are proposals pending human review (if `human_review=True`).
- **CommitReport** — after `commit_seeding`, the note_ids of stored content and the filter criteria ready for Attention Filter configuration.

**Downstream integration:**
- Tier 3 `personality_note_ids` → used by Generator via `memory_store.get_personality_context()`
- Tier 2 `pattern_note_ids` → used by Distillation as the initial pattern layer
- `filter_criteria` → passed to `AttentionFilterConfig.prompt_criteria` for the first filter runs

## State

None. The seeding pipeline is stateless — it reads corpus files, calls toolkit modules, and produces drafts. Persistence happens only via `commit_seeding` writing to Memory Store.

The knowledge graph built during Stage 2 is transient (in-memory during the pipeline run). Its structure is captured in the PatternDrafts and PersonalityDrafts; the graph itself is not persisted. If graph persistence is needed for debugging or re-seeding, the caller can serialize `SeedingResult` before committing.

## Usage Example

```python
from seeding import seed, commit_seeding, SeedingConfig, CorpusSource
from memory_store import MemoryStore, MemoryStoreConfig
from attention_filter import AttentionFilterConfig
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))

config = SeedingConfig(
    sources=[
        CorpusSource("./corpus/claude_conversations/", "conversations", "json", "Claude projects 2025-2026"),
        CorpusSource("./corpus/livejournal_export/", "livejournal", "html", "LJ archive 2008-2018"),
        CorpusSource("./corpus/blog_posts/", "blog", "markdown", "Published essays 2015-2024"),
        CorpusSource("./corpus/twitter_archive/", "twitter", "json", "Twitter export 2012-2023"),
    ],
    llm_config=LLMConfig(provider="anthropic", api_key="sk-...", models={"quality": "claude-opus-..."}),
    llm_tier=ModelTier.QUALITY,
    embedding_config=EmbeddingConfig(model="all-MiniLM-L6-v2"),
    human_review=True,
)

# Run pipeline — produces proposals
result = seed(config, store)
print(f"Graph: {result.graph_stats.entity_count} entities, {result.graph_stats.relationship_count} relationships")
print(f"Proposed: {len(result.personality_files)} personality files, {len(result.pattern_clusters)} patterns")

# Human reviews proposals
for i, pf in enumerate(result.personality_files):
    print(f"\n--- Personality File {i}: {pf.title} (confidence: {pf.confidence:.0%}) ---")
    print(pf.content[:500])

# Commit approved subset
report = commit_seeding(
    result, store,
    approved_personalities=[0, 1, 2, 3, 5],  # drop #4
    approved_patterns=None,                    # accept all patterns
)

print(f"Stored {len(report.personality_note_ids)} personality files, "
      f"{len(report.pattern_note_ids)} patterns, "
      f"{report.total_links_created} links")

# Use derived criteria for Attention Filter
filter_config = AttentionFilterConfig(
    prompt_criteria=report.filter_criteria,
    llm_config=config.llm_config,
    embedding_config=config.embedding_config,
)
```
