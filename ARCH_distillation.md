# ARCH: Distillation

## Purpose
Tier promotion engine. Promotes Memory Store content upward: Tier 1 daily log → Tier 2 pattern clusters (RAPTOR-style recursive clustering), and Tier 2 patterns → Tier 3 personality files (two-step reflect-evolve). Threshold-triggered, not just scheduled. Runs as a read-then-write process: reads current Memory Store state, performs all synthesis, then writes results back. Incorporates feedback events to calibrate Attention Filter criteria weights. Handles semantic merging — resolves contradictions in personality files rather than accumulating divergent observations.

## Public API

### Types

```python
@dataclass
class DistillationConfig:
    llm_config: LLMConfig                              # toolkit/llm_client — for synthesis, reflection, evolution
    llm_configs_rotation: list[LLMConfig] | None = None # optional: multiple providers for rotation
    reflection_tier: ModelTier = ModelTier.QUALITY       # model tier for reflection step
    evolution_tier: ModelTier = ModelTier.QUALITY        # model tier for evolution step (can differ from reflection)
    embedding_config: EmbeddingConfig                    # toolkit/embedding — for RAPTOR re-embedding
    clustering_config: ClusterConfig | None = None       # toolkit/clustering — None uses RAPTOR defaults
    min_time_between_runs: timedelta = timedelta(hours=24)
    min_tier1_volume: int = 20                          # minimum new Tier 1 notes before T1→T2 triggers
    t2_to_t3_cycle_days: int = 30                       # T2→T3 runs on this cadence
    inertia_per_cycle: float = 0.25                     # additional inertia weight per survived T2→T3 cycle
    max_inertia: float = 3.0                              # cap on version-count inertia (effective = min(max_inertia, 1.0 + (version_count-1) * inertia_per_cycle))
    max_compression_ratio: float = 0.5                  # safety cap: max 50% content reduction per T2→T3 pass
    incorporate_feedback: bool = True                    # process feedback events during distillation
    min_cluster_coherence: float = 0.4                   # minimum mean pairwise similarity for Tier 2 promotion
                                                         # clusters below this threshold are held in Tier 1
    cross_link_threshold: float = 0.45                   # minimum centroid similarity for T2→T2 links
    max_cross_links: int = 15                            # cap on same-run T2→T2 links per cluster
    t2_reflection_batch_size: int = 30                   # Tier 2 notes per reflection LLM call

@dataclass
class GateStatus:
    ready: bool                             # all gates pass for at least one tier promotion
    time_gate: bool                         # enough time since last run
    volume_gate: bool                       # enough Tier 1 content accumulated
    lock_gate: bool                         # no concurrent distillation running
    t1_to_t2_ready: bool                    # T1→T2 specifically ready
    t2_to_t3_ready: bool                    # T2→T3 specifically ready (monthly cycle)
    time_since_last_run: timedelta | None   # None if never run
    tier1_pending: int                      # new Tier 1 notes since last T1→T2
    days_since_last_t3: int | None          # None if T2→T3 never run

@dataclass
class TierPromotionResult:
    new_cluster_ids: list[str]              # note_ids of newly created Tier 2 notes
    updated_cluster_ids: list[str]          # note_ids of Tier 2 notes that were updated (merged new material)
    promoted_count: int                     # Tier 1 notes that contributed to clusters
    noise_count: int                        # Tier 1 notes that didn't cluster (retained in Tier 1)
    incoherent_cluster_count: int           # clusters below min_cluster_coherence (members retained in Tier 1)
    cluster_tree_depth: int                 # RAPTOR recursion depth reached
    feedback_processed: int                 # feedback events incorporated
    assertion_cache_updated: list[str]      # cluster_group ids whose assertion cache was refreshed

@dataclass
class ReflectionInsight:
    content: str                            # synthesized insight text
    source_pattern_ids: list[str]           # Tier 2 note_ids that contributed
    insight_type: str                       # "recurring_tension", "new_pattern", "evolution", "contradiction"
    confidence: float                       # [0.0, 1.0]

@dataclass
class SupersessionRecord:
    old_note_id: str                        # personality file that was superseded
    new_note_id: str                        # replacement version
    change_summary: str                     # what changed and why (stored in new note's frontmatter)

@dataclass
class CriteriaAdjustment:
    criterion_name: str                     # e.g., "friction", "precision_surplus"
    old_weight: float
    new_weight: float
    evidence: str                           # e.g., "friction items received 82% engagement vs 34% baseline"

@dataclass
class EvolutionResult:
    insights: list[ReflectionInsight]                   # from reflection step
    superseded: list[SupersessionRecord]                # personality files updated
    unchanged_ids: list[str]                            # personality file note_ids not modified
    criteria_adjustments: list[CriteriaAdjustment]      # proposed Attention Filter weight changes
    compression_ratio: float                            # actual content reduction (0.0 = no reduction)
```

### Constructor

- **Signature:** `DistillationEngine(memory_store: MemoryStore)`
- **Parameters:**
  - memory_store: MemoryStore — source and target for all reads and writes
- **Errors:** none

### check_gates

- **Signature:** `check_gates(config: DistillationConfig) -> GateStatus`
- **Parameters:**
  - config: DistillationConfig — thresholds for gate evaluation
- **Returns:** GateStatus — which gates pass, whether T1→T2 and/or T2→T3 are ready
- **Errors:** none

Three gates must pass before any distillation runs:

| Gate | Condition | Default |
|------|-----------|---------|
| Time | `time_since_last_run >= min_time_between_runs` | 24 hours |
| Volume | `tier1_pending >= min_tier1_volume` (T1→T2) or `days_since_last_t3 >= t2_to_t3_cycle_days` (T2→T3) | 20 notes / 30 days |
| Lock | No other distillation process is running | — |

### distill_t1_to_t2

- **Signature:** `distill_t1_to_t2(config: DistillationConfig) -> TierPromotionResult`
- **Parameters:**
  - config: DistillationConfig — model settings, clustering params, feedback preference
- **Returns:** TierPromotionResult — new and updated Tier 2 cluster notes, promotion counts
- **Errors:**
  - `DistillationLockError` — another distillation is running
  - `InsufficientDataError` — fewer Tier 1 notes than `min_tier1_volume`
  - `LLMAPIError` — LLM call failed during summarization (from toolkit/llm_client)
  - `EmbeddingModelError` — embedding failed (from toolkit/embedding)
  - `ClusterInputError` — clustering failed (from toolkit/clustering)

**Behavior:**

1. Acquires consolidation lock.
2. Reads Tier 1 notes accumulated since last T1→T2 run via `memory_store.query_notes(tier=1, since=...)`.
3. If `incorporate_feedback`: reads feedback events from Tier 1 (notes with `source="feedback"`), boosts importance scores of referenced notes.
4. Embeds all Tier 1 note content via toolkit/embedding.
5. Clusters embeddings via toolkit/clustering with RAPTOR strategy. Passes Tier 1 note contents as `texts` (required by RAPTOR for summarization) and provides callbacks:
   - `raptor_summarizer`: calls toolkit/llm_client to synthesize cluster members into a pattern description
   - `raptor_embedder`: calls toolkit/embedding to embed the summaries for re-clustering
6. **Checks cluster coherence**: for each cluster, computes `mean(pairwise_sim(member_embeddings))`. Clusters below `config.min_cluster_coherence` are not promoted — their member notes remain in Tier 1 with unmodified decay windows. This prevents diffuse, gap-filling material from forming weak clusters that become reference centroids for the Attention Filter's geometric scoring (see novelty-addiction risk in ARCH_attention_filter.md). Clusters must earn their status as attractors.
7. For each coherent cluster: creates or updates a Tier 2 note via `memory_store.store_note` or `memory_store.update_note`, setting `cluster_group` to the cluster identifier.
7. Wires cross-references between related clusters via `memory_store.add_links`.
   Relatedness is determined by cosine similarity between same-run cluster
   centroids: pairs below `config.cross_link_threshold` are ignored, and each
   note links to at most `config.max_cross_links` highest-similarity peers.
8. **Extracts and caches assertions** from each cluster summary via a lightweight LLM call. For each new or updated cluster, the call extracts the dominant claims (assertions the cluster's material supports or contests). These are stored alongside cluster centroids as the **assertion cache** — consumed by the Attention Filter's friction scoring, which compares incoming text assertions against cached cluster assertions rather than re-extracting per filter call. Storage: JSON file per cluster in the Tier 2 directory, keyed by cluster_group identifier.
9. Tier 1 notes that clustered are candidates for decay (their content is now captured in Tier 2). Noise items (unclustered) remain in Tier 1 with unmodified decay windows.
10. Releases lock.

### distill_t2_to_t3

- **Signature:** `distill_t2_to_t3(config: DistillationConfig) -> EvolutionResult`
- **Parameters:**
  - config: DistillationConfig — model settings, inertia settings, compression cap, feedback preference
- **Returns:** EvolutionResult — reflection insights, personality file changes, criteria adjustments
- **Errors:**
  - `DistillationLockError` — another distillation is running
  - `NoPatternDataError` — no Tier 2 notes exist
  - `LLMAPIError` — LLM call failed (from toolkit/llm_client)

**Behavior — two-step process:**

**Step 1 — Reflection:**
1. Acquires consolidation lock.
2. Reads current Tier 2 pattern notes via `memory_store.query_notes(tier=2)`.
3. If `incorporate_feedback`: reads feedback events, computes per-criterion engagement rates across accepted content.
4. Sorts Tier 2 notes by importance descending, breaking ties by unresolvedness descending.
5. Splits the sorted pattern layer into batches of `config.t2_reflection_batch_size`. When the pattern count is less than or equal to the batch size, this is a single batch and behavior matches the unbatched path.
6. Calls LLM (at `reflection_tier`) once per batch with the existing reflection prompt. Prompt: synthesize what recurring tensions are emerging, what threads are unresolved, what new associative connections have appeared.
7. Merges all batch outputs into one list of `ReflectionInsight` — candidate observations, not yet personality file updates.

**Step 2 — Evolution:**
1. Reads current personality files via `memory_store.get_personality_context()`.
2. If no personality files exist, calls LLM (at `evolution_tier`) with the merged reflection insights and asks for 3-7 initial personality files. Each file must capture a distinct corpus-specific dimension. Writes each file via `memory_store.store_note(tier=3, ...)` with `version_count = 1`.
3. If personality files exist, calls LLM (at `evolution_tier`, potentially a different model) with the reflection insights and current personality files. Each personality file's `version_count` (number of T2→T3 cycles survived) is conveyed in the prompt. Files with higher version counts have earned more inertia — effective weight = `min(max_inertia, 1.0 + (version_count - 1) * inertia_per_cycle)` — and require proportionally stronger evidence to override.
4. For each proposed modification:
   - Checks for contradictions with existing personality claims. Contradictions are resolved via supersession, not accumulation.
   - Enforces `max_compression_ratio` — a single pass cannot reduce personality file content by more than this ratio.
   - Writes the update via `memory_store.supersede(note_id, new_content, new_title, change_summary)`. The new note starts with `version_count = 1`.
5. For personality files that survived this cycle unchanged (in `unchanged_ids`): increments their `version_count` via `memory_store.update_note` metadata update.
6. Computes `criteria_adjustments` from feedback data: criteria that consistently produce well-received content get weight increases; criteria that produce ignored content get decreases.
7. Releases lock.

**The reflection output is an audit artifact.** It can be reviewed independently of the evolution output to diagnose whether a personality file change was triggered by genuine insight or by a synthesis artifact.

### RAPTOR Callback Wiring

Resolves the provisional contract from ARCHITECTURE.md: *"How distillation wires the RAPTOR summarizer callback to toolkit/llm_client."*

The Distillation engine constructs callbacks at runtime and passes them to `toolkit/clustering.cluster()` via `ClusterConfig`:

```python
# Constructed internally by distill_t1_to_t2
def make_raptor_summarizer(llm_config, tier):
    def summarizer(texts: list[str]) -> str:
        prompt = f"Synthesize these observations into a coherent pattern:\n\n" + "\n---\n".join(texts)
        response = complete(
            messages=[Message(role="user", content=prompt)],
            config=llm_config,
            tier=tier,
        )
        return response.content
    return summarizer

def make_raptor_embedder(embedding_config):
    def embedder(texts: list[str]) -> ndarray:
        return embed(texts, embedding_config).vectors
    return embedder

# Passed to toolkit/clustering
cluster_config = ClusterConfig(
    strategy=ClusterStrategy.RAPTOR,
    raptor_summarizer=make_raptor_summarizer(config.llm_config, config.reflection_tier),
    raptor_embedder=make_raptor_embedder(config.embedding_config),
    raptor_max_depth=3,
)
tier1_texts = [note.content for note in tier1_notes]
result = cluster(tier1_embeddings, cluster_config, texts=tier1_texts)
```

The summarizer prompt is Phosphene-specific (synthesize observations into patterns with attention to tensions and friction). The embedding is pass-through to toolkit/embedding. This wiring is internal to the Distillation engine — consumers call `distill_t1_to_t2` and don't interact with RAPTOR directly.

## Inputs

- **Tier 1 notes** — from Memory Store. Daily log entries stored by the Attention Filter.
- **Tier 2 notes** — from Memory Store. Pattern clusters from prior T1→T2 runs.
- **Tier 3 notes** — from Memory Store. Current personality files.
- **Feedback events** — from Memory Store. Notes with `source="feedback"` linking back to content and carrying retention criteria metadata.
- **DistillationConfig** — model settings, thresholds, version-count inertia settings, compression cap.

## Outputs

- **TierPromotionResult** — new/updated Tier 2 cluster notes (written to Memory Store during the call). Counts of promoted and noise items. List of cluster_group ids whose assertion cache was refreshed.
- **EvolutionResult** — reflection insights (audit artifact), supersession records (personality files updated in Memory Store during the call), proposed criteria adjustments (returned to caller for Attention Filter config update — not written to Memory Store).
- **GateStatus** — whether distillation should run.

**Downstream integration:**
- New Tier 2 clusters are available to the Attention Filter for geometric scoring (Phase 2 criteria use cluster centroids and assertion cache)
- **Assertion cache**: cluster assertions extracted during T1→T2 are consumed by the Attention Filter's friction scoring. The filter reads cached assertions rather than re-extracting per incoming item. Cache is stored as JSON per cluster in the Tier 2 directory.
- Updated Tier 3 files are available to the Generator via `memory_store.get_personality_context()`
- `criteria_adjustments` should be applied to `AttentionFilterConfig.prompt_criteria` weights before the next filter run
- Supersession records provide the audit trail for personality development tracking

## State

- **Consolidation lock:** in-memory flag preventing concurrent distillation runs. If the process crashes, the lock is released on restart. The lock is not persistent — a clean restart always clears it.
- **Last-run timestamps:** persisted to a metadata file in the Memory Store vault. Tracks when T1→T2 and T2→T3 last ran, used by `check_gates`. Updated after each successful distillation.
- **Assertion cache:** JSON files in the Tier 2 directory, one per cluster, containing dominant assertions extracted from cluster summaries. Updated during each T1→T2 run for new and modified clusters. Consumed by the Attention Filter for friction scoring.
- No other state. All content state lives in Memory Store.

## Usage Example

```python
from distillation import DistillationEngine, DistillationConfig
from memory_store import MemoryStore, MemoryStoreConfig
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
engine = DistillationEngine(memory_store=store)

config = DistillationConfig(
    llm_config=LLMConfig(provider="anthropic", api_key="sk-...",
                         models={"quality": "claude-opus-...", "default": "claude-sonnet-..."}),
    embedding_config=EmbeddingConfig(model="all-MiniLM-L6-v2"),
    min_tier1_volume=20,
    t2_to_t3_cycle_days=30,
    inertia_per_cycle=0.25,
    max_inertia=3.0,
)

# Check whether distillation should run
gates = engine.check_gates(config)
print(f"T1→T2 ready: {gates.t1_to_t2_ready} ({gates.tier1_pending} pending)")
print(f"T2→T3 ready: {gates.t2_to_t3_ready} ({gates.days_since_last_t3} days)")

# T1→T2: cluster daily log into patterns
if gates.t1_to_t2_ready:
    result = engine.distill_t1_to_t2(config)
    print(f"Created {len(result.new_cluster_ids)} clusters, "
          f"updated {len(result.updated_cluster_ids)}, "
          f"{result.noise_count} noise items")

# T2→T3: reflect-evolve pattern layer into personality files
if gates.t2_to_t3_ready:
    result = engine.distill_t2_to_t3(config)

    # Review reflection insights (audit)
    for insight in result.insights:
        print(f"[{insight.insight_type}] {insight.content[:100]}...")

    # Review personality file changes
    for record in result.superseded:
        print(f"Updated {record.old_note_id} → {record.new_note_id}: {record.change_summary}")

    # Apply criteria adjustments to Attention Filter config
    for adj in result.criteria_adjustments:
        print(f"Criterion '{adj.criterion_name}': {adj.old_weight:.2f} → {adj.new_weight:.2f} ({adj.evidence})")
        # Update AttentionFilterConfig.prompt_criteria weights accordingly
```
