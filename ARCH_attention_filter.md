# ARCH: Attention Filter

## Purpose
Personality-driven content selection and annotation. Receives raw content items from Source Ingestion (or Explorer), scores them against configurable criteria, and produces annotated fragments for storage in Memory Store as Tier 1 notes. Implements automatic prompt-to-structure transition: early filtering relies on explicit personality-derived criteria evaluated by LLM; as memory network density grows, structural signals (link density, cluster novelty, unresolvedness affinity) progressively take over. The transition is internal — the filter's input and output formats do not change.

## Public API

### Types

```python
@dataclass
class ContentItem:
    content: str                            # raw text content
    source: str                             # source adapter name (e.g., "telegram", "rss", "reddit")
    timestamp: datetime
    url: str | None = None                  # source URL
    linked_urls: list[str] = field(default_factory=list)  # URLs found in content (for Explorer)

@dataclass
class FilterCriterion:
    name: str                               # identifier, e.g. "friction", "precision_surplus"
    description: str                        # natural language instruction for LLM evaluation
    weight: float = 1.0                     # relative weight in prompt-based composite score

@dataclass
class AttentionFilterConfig:
    prompt_criteria: list[FilterCriterion]   # personality-derived criteria (from Seeding, updated by Distillation)
    acceptance_threshold: float = 0.3        # minimum composite score for retention [0.0, 1.0]
    auto_accept_sources: list[str] = field(default_factory=list)
                                             # sources that bypass acceptance_threshold but still get full annotation
                                             # e.g., ["human_share"] — human-curated content always enters Tier 1
    density_crossover: float = 3.0           # mean_link_degree at which prompt/structure blend reaches 50/50
    similarity_candidates: int = 20          # how many existing notes to retrieve for friction/connection detection
    llm_config: LLMConfig                    # toolkit/llm_client — for criteria evaluation and annotation
    llm_tier: ModelTier = ModelTier.DEFAULT   # model tier for filter LLM calls
    embedding_config: EmbeddingConfig         # toolkit/embedding — for content embedding

@dataclass
class AnnotatedFragment:
    content: str                            # original content (unmodified)
    annotation: str                         # LLM-generated explanation of why this was retained
    importance_score: float                 # [0.0, 1.0] — composite of all criteria scores
    unresolvedness: float                   # [0.0, 1.0] — tension with existing memory (0 = fully resolved)
    retention_criteria: list[str]           # criteria that contributed to retention (e.g., ["friction", "link_density"])
    prompt_score: float                     # [0.0, 1.0] — prompt-based criteria component
    structure_score: float                  # [0.0, 1.0] — structure-based criteria component
    friction_target: str | None             # note_id of existing note this creates friction with (if any)
    connections: list[str]                  # note_ids of existing notes this connects to
    source: str                             # from ContentItem
    timestamp: datetime                     # from ContentItem
    url: str | None                         # from ContentItem
    linked_urls: list[str]                  # URLs extracted from content (passed to Explorer)
    embedding: ndarray                      # computed embedding of this content (passed to Memory Store)

@dataclass
class FilterResult:
    accepted: list[AnnotatedFragment]       # fragments above acceptance_threshold
    rejected_count: int                     # items below threshold
    total_count: int                        # items evaluated
    prompt_weight: float                    # current blend: 1.0 = pure prompt, 0.0 = pure structure
    structure_weight: float                 # 1.0 - prompt_weight
    density_snapshot: DensityMetrics        # Memory Store metrics used for this run (from memory_store.get_density_metrics)
```

### Constructor

- **Signature:** `AttentionFilter(memory_store: MemoryStore)`
- **Parameters:**
  - memory_store: MemoryStore — for density metrics, existing note queries, and embedding search. Read-only access.
- **Errors:**
  - None at construction. Errors surface at `filter_content` call time.

### filter_content

- **Signature:** `filter_content(items: list[ContentItem], config: AttentionFilterConfig) -> FilterResult`
- **Parameters:**
  - items: list[ContentItem] — raw content to evaluate. May be empty (returns empty result).
  - config: AttentionFilterConfig — criteria, thresholds, and model configuration for this run. Config is per-call to allow criteria to evolve between runs.
- **Returns:** FilterResult
- **Errors:**
  - `LLMAPIError` — LLM call for criteria evaluation or annotation generation failed (from toolkit/llm_client)
  - `EmbeddingModelError` — embedding computation failed (from toolkit/embedding)
  - `InvalidScoreError` — acceptance_threshold outside [0.0, 1.0]

**Behavior:**

For each content item, the filter:

1. **Embeds** the content via toolkit/embedding.
2. **Queries** Memory Store for similar existing notes (`search_by_embedding`) and density metrics (`get_density_metrics`).
3. **Computes blend weight** from density metrics. When `mean_link_degree` is near zero, `prompt_weight ≈ 1.0`. At `density_crossover`, blend is 50/50. Beyond, `structure_weight` dominates.
4. **Evaluates prompt criteria** — calls LLM with the criterion descriptions, the content item, and relevant existing notes. Each criterion produces a score in [0.0, 1.0].
5. **Evaluates structural criteria** (always computed, weight increases with density):
   - *Link density*: how many existing notes the content connects to (from embedding similarity above threshold)
   - *Cluster novelty*: whether the content falls within an existing Tier 2 cluster or opens new territory
   - *Unresolvedness affinity*: whether the content engages with notes that have high unresolvedness
6. **Computes composite score** — weighted combination of prompt and structure scores, blended by prompt_weight/structure_weight.
7. **Accepts or rejects** based on `acceptance_threshold`. Items from `auto_accept_sources` bypass the threshold but still receive the full annotation pass — importance, unresolvedness, friction, and connections are computed normally.
8. For accepted items: **generates annotation** via LLM — a short explanation of why this was retained, which criteria it scored on, and what friction or connections were identified. For auto-accepted items, the annotation captures what the system finds interesting *about* the content, even though it was pre-accepted.

### Default Prompt Criteria

Initial criteria operationalized from the seed personality. The Seeding pipeline may customize these; the Distillation engine may revise weights over time based on feedback signals.

| Name | Description | Default Weight |
|------|-------------|----------------|
| `friction` | Does this contradict, complicate, or sit in tension with existing content? | 1.0 |
| `unexpected_connection` | Does this link to existing notes across topical boundaries in an unpredicted way? | 1.0 |
| `precision_surplus` | Does this say something more specific than the domain usually allows? | 0.8 |
| `structural_insight` | Does this identify a mechanism or pattern rather than an analogy or illustration? | 0.8 |
| `liminal_position` | Does this occupy a space between established categories? | 0.7 |

### Structural Criteria (built-in)

These are always computed. Their contribution to the composite score is governed by `structure_weight`.

| Name | Signal | Source |
|------|--------|--------|
| `link_density` | Number of existing notes the content connects to (embedding similarity above threshold) | `memory_store.search_by_embedding` |
| `cluster_novelty` | Content falls outside existing Tier 2 clusters, or bridges two clusters | `memory_store.get_index(tier=2)` cluster_group tags |
| `unresolvedness_affinity` | Content engages with notes that have high unresolvedness scores | `memory_store.search_by_embedding` + note unresolvedness |

## Inputs

- **ContentItem** — from Source Ingestion adapters or Explorer. Raw content with source metadata and extracted URLs.
- **AttentionFilterConfig** — per-call configuration including personality-derived criteria, thresholds, and model settings. Criteria evolve over time: Seeding produces initial criteria from the corpus; Distillation may adjust weights based on accumulated feedback evidence.

## Outputs

- **AnnotatedFragment** — accepted content with:
  - Annotation explaining *why* it was retained (which criteria, what friction/connections were found)
  - Importance score and unresolvedness score for Memory Store storage
  - Friction target and connections linking to existing notes (these become links in Memory Store)
  - Pre-computed embedding vector (consumer passes to `memory_store.store_note`)
  - Extracted URLs (consumer passes to Explorer for link-following)

- **FilterResult** — batch result with blend weight metadata. The `prompt_weight` / `structure_weight` values allow monitoring the prompt-to-structure transition over time.

**Consumer integration:** The consumer (typically the Orchestrator) maps each `AnnotatedFragment` to a `NoteInput` for `memory_store.store_note`:

```python
for fragment in result.accepted:
    memory_store.store_note(NoteInput(
        tier=1,
        content=fragment.content,
        title=fragment.annotation[:150],
        importance=fragment.importance_score,
        unresolvedness=fragment.unresolvedness,
        links=fragment.connections,
        tags=fragment.retention_criteria,
        source=fragment.source,
        friction_target=fragment.friction_target,
        embedding=fragment.embedding,
    ))
```

## State

None. The Attention Filter is stateless — it reads from Memory Store on each call and produces output. All criteria configuration is passed per-call via `AttentionFilterConfig`. The prompt-to-structure transition is computed dynamically from Memory Store density metrics, not tracked internally.

Criteria weight adjustments (from feedback calibration) are stored externally — either in configuration files or as part of the personality context managed by the Distillation engine. The filter receives the current weights in each `config.prompt_criteria` and applies them.

## Usage Example

```python
from attention_filter import AttentionFilter, AttentionFilterConfig, FilterCriterion, ContentItem
from memory_store import MemoryStore, MemoryStoreConfig, NoteInput
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
af = AttentionFilter(memory_store=store)

# Initial criteria from seed personality
config = AttentionFilterConfig(
    prompt_criteria=[
        FilterCriterion("friction", "Does this contradict or complicate existing content?"),
        FilterCriterion("unexpected_connection", "Does this link across topical boundaries?"),
        FilterCriterion("precision_surplus", "Does this say something unusually specific?", weight=0.8),
        FilterCriterion("structural_insight", "Does this identify a mechanism, not just an analogy?", weight=0.8),
        FilterCriterion("liminal_position", "Does this sit between established categories?", weight=0.7),
    ],
    acceptance_threshold=0.3,
    density_crossover=3.0,
    llm_config=LLMConfig(provider="anthropic", api_key="sk-...", models={"default": "claude-sonnet-..."}),
    embedding_config=EmbeddingConfig(model="all-MiniLM-L6-v2"),
)

# Filter a batch of ingested content
items = [
    ContentItem(
        content="Luhmann credited surprise as the primary value of his Zettelkasten...",
        source="rss",
        timestamp=datetime.now(),
        url="https://example.com/article",
        linked_urls=["https://example.com/related"],
    ),
]

result = af.filter_content(items, config)

print(f"Accepted {len(result.accepted)}/{result.total_count}")
print(f"Blend: {result.prompt_weight:.0%} prompt / {result.structure_weight:.0%} structure")
print(f"Network density: {result.density_snapshot.mean_link_degree:.1f} mean links")

# Store accepted fragments in Memory Store
for fragment in result.accepted:
    store.store_note(NoteInput(
        tier=1,
        content=fragment.content,
        title=fragment.annotation[:150],
        importance=fragment.importance_score,
        unresolvedness=fragment.unresolvedness,
        links=fragment.connections,
        tags=fragment.retention_criteria,
        source=fragment.source,
        friction_target=fragment.friction_target,
        embedding=fragment.embedding,
    ))

# Pass linked URLs to Explorer for potential link-following
for fragment in result.accepted:
    for url in fragment.linked_urls:
        explorer.queue(url)
```
