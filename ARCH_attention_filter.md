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
class ScoringConfig:
    """Processing-level tuning parameters for Phase 1/Phase 2 scoring.
    Separates tunable weights and thresholds from the architectural contract.
    Deployment-specific overrides go in deployment.yaml."""

    # Phase 1 (LLM) criterion weight
    precision_surplus_weight: float = 1.0            # weight for LLM-scored precision surplus

    # Phase 2 geometric criterion weights (active after triple-gate transition)
    liminality_weight: float = 1.0
    friction_weight: float = 1.0
    unexpected_connection_weight: float = 1.0
    structural_insight_weight: float = 1.0
    link_density_weight: float = 1.0
    cluster_novelty_weight: float = 1.0
    unresolvedness_affinity_weight: float = 1.0

    # Phase 2 scoring thresholds
    link_density_sim_threshold: float = 0.4          # embedding similarity above which a note counts as "connected"
    gap_factor_exponent: float = 2.0                 # controls liminality gap_factor curve steepness
    assertion_alignment_threshold: float = 0.5       # friction: below this alignment = frictionful

    # Transition: triple gate (S-3) — Phase 2 activates when ALL three are met
    note_count_threshold: int = 50                   # minimum Tier 1 notes before Phase 2 activates
    cluster_count_threshold: int = 3                 # minimum Tier 2 clusters before Phase 2 activates
    # mean_link_degree threshold is density_crossover on AttentionFilterConfig

    # Blend curve
    phase2_max_weight: float = 0.7                   # cap on Phase 2 weight (S-2) — prompt retains at least 1 - this

@dataclass
class AttentionFilterConfig:
    prompt_criteria: list[FilterCriterion]   # Phase 1 personality-derived criteria (LLM-evaluated)
                                             # Default: precision_surplus only. See Default Prompt Criteria.
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
                                             # Phase 2 weights, thresholds, and transition parameters
    acceptance_threshold: float = 0.3        # minimum composite score for retention [0.0, 1.0]
    auto_accept_sources: list[str] = field(default_factory=list)
                                             # sources that bypass acceptance_threshold but still get full annotation
                                             # e.g., ["human_share"] — human-curated content always enters Tier 1
    density_crossover: float = 3.0           # mean_link_degree at which prompt/structure blend reaches 50/50
    similarity_candidates: int = 20          # how many existing notes to retrieve for friction/connection detection
    llm_config: LLMConfig                    # toolkit/llm_client — for Phase 1 criteria evaluation and annotation
    llm_tier: ModelTier = ModelTier.DEFAULT   # model tier for Phase 1 LLM calls
    assertion_extraction_tier: ModelTier = ModelTier.COMMODITY  # model tier for friction assertion extraction
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
3. **Checks triple gate** for Phase 2 activation: Phase 2 is active only when `note_count >= scoring.note_count_threshold` AND `cluster_count >= scoring.cluster_count_threshold` AND `mean_link_degree >= density_crossover × 0.5` (half the crossover point). If any gate fails, `structure_weight = 0.0` and `prompt_weight = 1.0`.
4. **Computes blend weight** (when triple gate passes): `structure_weight` increases linearly from 0.0 to `scoring.phase2_max_weight` as `mean_link_degree` rises from `density_crossover × 0.5` to `density_crossover × 2.0`. Above `density_crossover × 2.0`, `structure_weight` is fixed at `scoring.phase2_max_weight`. `prompt_weight = 1.0 - structure_weight` (always ≥ `1 - phase2_max_weight`, default 0.3).
5. **Evaluates Phase 1 (prompt criteria)** — calls LLM with the criterion descriptions, the content item, and relevant existing notes. Each criterion produces a score in [0.0, 1.0]. Default: precision_surplus only.
6. **Evaluates Phase 2 (geometric criteria)** — always computed when triple gate passes, weight increases with density:
   - *Liminality*: `1 - max_sim(text, centroids) × gap_factor(rank1, rank2)` — between clusters
   - *Friction*: `topical_sim(text, nearest_cluster) × (1 - assertion_alignment(text, cluster))` — contradicts a cluster's claims. Uses one LLM call (at `assertion_extraction_tier`) to extract claims from the incoming text; cluster claims are read from the assertion cache produced by the Distillation engine (see S-6, ARCH_distillation.md).
   - *Unexpected connection*: `max over cluster pairs: min(sim(text, ci), sim(text, cj)) × (1 - sim(ci, cj))` — bridges distant clusters
   - *Structural insight*: `sim(text, meta_cluster_of_tier2_summaries)` — operates at pattern-layer abstraction level
   - *Link density*: `count(notes where sim(text, note) > scoring.link_density_sim_threshold)` — centrality / familiarity
   - *Cluster novelty*: `1 - max(sim(text, all_centroids))` — genuinely new territory (beyond all clusters, distinct from liminality which is *between*)
   - *Unresolvedness affinity*: `sum(sim(text, note_i) × note_i.unresolvedness)` over similar notes — engages with live tensions (hybrid: vector similarity × note metadata)
7. **Computes composite score** — weighted combination of Phase 1 and Phase 2 scores, blended by `prompt_weight` / `structure_weight`. Phase 1 sub-score is the weighted average of prompt criteria scores. Phase 2 sub-score is the weighted average of geometric criteria scores (using `scoring.*_weight` values).
8. **Accepts or rejects** based on `acceptance_threshold`. Items from `auto_accept_sources` bypass the threshold but still receive the full annotation pass — importance, unresolvedness, friction, and connections are computed normally.
9. For accepted items: **generates annotation** via LLM — a short explanation of why this was retained, which criteria it scored on, and what friction or connections were identified. For auto-accepted items, the annotation captures what the system finds interesting *about* the content, even though it was pre-accepted.

### Default Prompt Criteria (Phase 1)

Phase 1 criteria are evaluated by the LLM. They handle scoring dimensions that resist geometric formalization — intrinsic text quality rather than relational position in the memory network.

Default `prompt_criteria` (one criterion — precision surplus is the only Phase 1 signal):

```python
default_prompt_criteria = [
    FilterCriterion(
        name="precision_surplus",
        description="Score the ratio of precise claim to vague gesture in this text. "
                    "High score: claims are specific, evidence is tight, the text could not "
                    "have been written without knowing something. Low score: claims are general, "
                    "evidence is gestures toward evidence.",
        weight=1.0,
    ),
]
```

**Why only one Phase 1 criterion:** Friction, unexpected connection, structural insight, and liminal position are all *relational* — they measure how the incoming text relates to the existing memory network. These are formalized as geometric computations in Phase 2, where they are cheaper, more reproducible, and scale with cluster count rather than LLM budget. Precision surplus is *intrinsic* — it measures the text's internal argumentative quality (claim-evidence tightness), which doesn't reduce to vector arithmetic. It remains the sole Phase 1 signal.

**Precision surplus formalization options (recorded for future reference, not pursued now):**
- *Embedding specificity proxy*: distance from nearest cluster centroid within a topical band. Measures unusualness, not precision — insufficient.
- *Information density*: ratio of named entities / quantities / technical terms to total length. NLP-computable but different from argumentative precision.
- *Claim-evidence structure detection*: lightweight NLP to detect assertion vs. evidence sentences. Essentially a simplified LLM call — not a real savings.
- *Compression resistance*: `1 - sim(text_embedding, summary_embedding)`. Requires an LLM call to summarize — doesn't avoid the LLM.

### Phase 2 Geometric Criteria

Phase 2 criteria are computed geometrically against the Tier 2 cluster structure and existing Memory Store notes. Phase 2 activates after the triple gate: note count, cluster count, and mean link degree must all cross their respective `ScoringConfig` thresholds.

Seven scoring dimensions, each with a configurable weight in `ScoringConfig`:

| Criterion | Formula | What it captures |
|-----------|---------|-----------------|
| **Liminality** | `1 - max_sim(text, centroids) × gap_factor(rank1, rank2)` | Between clusters — equidistant to two clusters is more liminal than narrowly missing one |
| **Friction** | `topical_sim(text, nearest) × (1 - assertion_alignment(text, cluster))` | Topically related but contradicts cluster claims. One LLM call for assertion extraction from incoming text; cluster claims from Distillation assertion cache |
| **Unexpected connection** | `max over pairs: min(sim(text, ci), sim(text, cj)) × (1 - sim(ci, cj))` | Bridges two clusters that have low mutual similarity |
| **Structural insight** | `sim(text, meta_cluster_of_tier2_summaries)` | Operates at pattern-layer abstraction level — resembles synthesis outputs in register |
| **Link density** | `count(notes where sim(text, note) > threshold)` | Centrality / familiarity — how many things this relates to |
| **Cluster novelty** | `1 - max(sim(text, all_centroids))` | Genuinely new territory — beyond all clusters (distinct from liminality which is *between*) |
| **Unresolvedness affinity** | `sum(sim(text, note_i) × note_i.unresolvedness)` | Engages with live tensions (hybrid: vector similarity × note metadata) |

**Cost:** For a content chunk against N clusters, Phase 2 requires N cosine similarity computations (microseconds each) plus one LLM call at `assertion_extraction_tier` for the friction component's claim extraction from the incoming text. Cluster claims are pre-cached by the Distillation engine (see Assertion Cache in ARCH_distillation.md). Total Phase 2 cost per chunk is dominated by the single assertion-extraction call, not by the vector arithmetic.

**Novelty-addiction risk:** Overweighting liminality and cluster_novelty creates a self-reinforcing feedback loop. Liminal material enters Tier 1 → Distillation clusters it → new clusters form in the liminal zones → those clusters become reference centroids → the liminality formula now measures distance from the new, interpolated centroids → what was liminal is now central, and the new liminal zone is further out. The system develops an ever-expanding low-resolution map of everything rather than a deep, specific map of what matters — associatively rich but shallow outputs.

Two mitigations:
1. **Weight ordering:** Deployment weights should prioritize depth/challenge (friction, structural_insight, unresolvedness_affinity) over novelty (liminality, cluster_novelty). Liminality should be a tiebreaker, not a dominant signal. See Section 5.9 in phosphene.md for Phosphene's calibrated weights.
2. **Cluster coherence gate:** The Distillation engine enforces `min_cluster_coherence` — clusters below a mean pairwise similarity threshold are not promoted to Tier 2. This prevents diffuse, gap-filling material from forming weak clusters that then become the reference centroids for the next round of geometric scoring. See `distill_t1_to_t2` step 6 in ARCH_distillation.md.

## Inputs

- **ContentItem** — from Source Ingestion adapters or Explorer. Raw content with source metadata and extracted URLs.
- **AttentionFilterConfig** — per-call configuration including Phase 1 criteria, `ScoringConfig` (Phase 2 weights and thresholds), and model settings. Phase 1 criteria evolve over time: initial defaults are hardcoded; Distillation adjusts weights based on accumulated feedback evidence. Phase 2 criterion weights are set via `ScoringConfig` and can be overridden per deployment in `deployment.yaml`.

**Bootstrap behavior:** When Memory Store is empty (no notes, density metrics at zero), the triple gate fails and the filter operates on Phase 1 criteria alone — `prompt_weight = 1.0`, Phase 2 contributes zero. Corpus sources listed in `auto_accept_sources` bypass the acceptance threshold during initial import while still receiving full annotation. This allows the system to bootstrap from an empty state without requiring a separate seeding pipeline.

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

Criteria weight adjustments (from feedback calibration) are stored externally — either in configuration files or as part of the personality context managed by the Distillation engine. The filter receives the current Phase 1 weights in each `config.prompt_criteria` and Phase 2 weights via `config.scoring`.

## Usage Example

```python
from attention_filter import (
    AttentionFilter, AttentionFilterConfig, ScoringConfig,
    FilterCriterion, ContentItem,
)
from memory_store import MemoryStore, MemoryStoreConfig, NoteInput
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
af = AttentionFilter(memory_store=store)

# Phase 1: precision surplus only (default)
# Phase 2: geometric criteria with deployment-specific weights
config = AttentionFilterConfig(
    prompt_criteria=[
        FilterCriterion(
            "precision_surplus",
            "Score the ratio of precise claim to vague gesture in this text. "
            "High score: claims are specific, evidence is tight. "
            "Low score: claims are general, evidence is gestures toward evidence.",
            weight=1.0,
        ),
    ],
    scoring=ScoringConfig(
        # Phosphene deployment weights (from deployment.yaml)
        # Starting points for empirical calibration — depth/challenge over novelty
        friction_weight=1.5,
        structural_insight_weight=1.3,
        unexpected_connection_weight=1.3,
        unresolvedness_affinity_weight=1.2,
        liminality_weight=1.0,
        link_density_weight=1.0,
        cluster_novelty_weight=0.8,
        # Triple gate thresholds (TBD — first-month calibration)
        note_count_threshold=50,
        cluster_count_threshold=3,
        phase2_max_weight=0.7,
    ),
    acceptance_threshold=0.3,
    density_crossover=3.0,
    llm_config=LLMConfig(provider="anthropic", api_key="sk-...",
                         models={"default": "claude-sonnet-..."}),
    assertion_extraction_tier=ModelTier.COMMODITY,
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
