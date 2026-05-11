# Clustering A/B Plan

**Status:** Planned (pre-implementation)
**Date:** 2026-05-09
**Origin:** Discussion during MVP audit window — choosing the post-agglomerative clustering algorithm
**See also:** `NETWORK_OPTIMUMS.md` (terrain analysis methodology), `DEVPLAN.md` immediate-todo #2

---

## Goal

Replace the current agglomerative clustering used in simulation (and earmarked for distillation) with a better algorithm. Use the swap as the first principled A/B in phosphene's experimentation track — establish the methodology so future tuning passes (embedding models, retention parameters, attention weights) can reuse it.

## Phosphene's Clustering Requirements

The algorithm choice should be driven by what phosphene actually needs from clustering, not by familiarity with one method. In rough priority order:

1. **Connected, coherent clusters.** Fragmented clusters break distillation — reflect-evolve summaries over a fragmented set produce incoherent T2 outputs.
2. **Hierarchy.** Phosphene's tier structure (T1 raw notes → T2 thematic clusters → T3 personality nodes) is intrinsically hierarchical. An algorithm that produces a hierarchy natively is better-fit than one that requires post-hoc stacking.
3. **No fixed k.** Themes emerge from the corpus; phosphene cannot predeclare how many clusters exist at any time.
4. **Weighted edges.** Similarity is continuous (cosine of normalized embeddings). The algorithm must respect edge weights, not binarize them.
5. **Computationally cheap.** Distillation runs on a Pi (orchestration only, but graph algorithms run locally — only embeddings/distillation summaries hit the API). Want sub-second to single-digit-seconds for graphs of hundreds-to-low-thousands of nodes, with periodic reclustering as the graph grows.
6. **Stable / persistent labels.** Cluster identity should not churn wildly between consecutive ticks at similar parameters — distillation needs to recognize "this is still the same theme as last cycle."
7. **Possibly: overlap tolerance.** A note about "AI ethics" can legitimately belong to both an *ethics* theme and an *AI* theme. Strict partitioning forces a choice that may distort the personality. Worth considering, adds complexity.

## Algorithm Landscape

A scorecard against the requirements above:

| Algorithm                              | Connected | Hierarchy           | No-k        | Weighted | Fast        | Overlap | Verdict for phosphene                |
|----------------------------------------|-----------|---------------------|-------------|----------|-------------|---------|--------------------------------------|
| Hierarchical agglomerative (current)   | Y         | Y                   | Y           | Y        | O(n²)       | N       | what we're replacing                 |
| Min-cut / Karger                       | Y         | recursive only      | unbalanced  | Y        | slow        | N       | bisection-only — wrong shape         |
| Girvan–Newman                          | Y         | Y                   | Y           | Y        | **O(n³)**   | N       | beautiful, doesn't scale             |
| Modularity max — Louvain               | **N**     | Y                   | Y           | Y        | fast        | N       | superseded by Leiden                 |
| Modularity max — **Leiden**            | Y         | Y (multi-level)     | Y           | Y        | fast        | N       | **strong default**                   |
| Statistical inference — **nested SBM** | Y         | **Y, native**       | Y           | Y        | slow        | Y (mixed-membership variant) | **principled, native T1→T2→T3 fit**  |
| Clique percolation (CPM)               | Y         | implicit            | **needs k** | Y        | slow        | **Y**   | only viable overlap-tolerant choice  |
| Label propagation                      | Y         | N                   | Y           | Y        | very fast   | N       | unstable across runs — skip          |
| Spectral clustering                    | Y         | recursive only      | **needs k** | Y        | medium      | N       | needs k — disqualified               |
| Markov clustering (MCL)                | Y         | implicit            | Y           | Y        | medium      | N       | underrated in bio, niche elsewhere   |
| HDBSCAN-on-embeddings                  | N/A       | partial (condensed tree) | Y      | N/A      | fast        | N       | skips graph entirely — paradigm contrast |

After filtering by phosphene's hard requirements (no fixed k; weighted edges; reasonable cost), the realistic shortlist is **Leiden, nested SBM, HDBSCAN-on-embeddings**, with **CPM** as a conditional fourth if overlap-tolerance becomes a feature requirement.

## A/B Candidates (Revised)

### Arm A — Leiden (default)

**Library:** `leidenalg` (Traag's reference implementation, igraph-backed). Mature, well-maintained.

**Why:** Strict improvement over Louvain — same UX (resolution parameter, weighted edges, multi-level hierarchy, no k), with three concrete fixes:
1. Communities are guaranteed connected (Louvain's greedy local-move + aggregate loop can produce disconnected communities under some sequences).
2. Higher-modularity partitions in similar wall clock.
3. Stronger guarantees about local optimality.

**Known limitation:** Modularity maximization has a *resolution limit* — communities smaller than √m (sqrt of total edge weight) get silently merged. Real concern for phosphene at scale, but phosphene's vault is small enough during establishment that it likely doesn't bite for a while.

**Cost:** trivial. ~1 line replacement for current `linkage` calls.

### Arm B — Nested Stochastic Block Model

**Library:** `graph-tool` (Tiago Peixoto's library — note: native C++ build, not pip-installable; needs apt/brew). Reference for nested SBM.

**Why:** This is the algorithm that's structurally closest to what phosphene actually wants:

- **Native hierarchy.** Nested SBM produces a *hierarchy of partitions* by design — you don't post-hoc stack flat partitions. This maps directly onto T1 → T2 → T3 without an integration step.
- **No resolution limit.** Unlike modularity-based methods (Leiden included), SBM doesn't suffer from the √m resolution issue. It can find arbitrarily small communities if the data supports them.
- **Mixed-membership variant** for overlap tolerance (a node in multiple communities with weights) — the cleanest path to representing "this note belongs to ethics AND AI" if we want it.
- **Bayesian principled.** Doesn't optimize a quality function; instead asks "what generative process most likely produced this graph?" — a different epistemology that gives uncertainty estimates for free.

**Costs:**
- More compute than Leiden (Bayesian inference is expensive). Tolerable for periodic distillation runs, probably not for per-message updates.
- More complex to interpret — the partition is a posterior, not a hard labeling.
- `graph-tool` is heavyweight to install relative to `leidenalg`.

**Why this matters more than I first flagged:** the native-hierarchy fit is genuinely unique among the candidates — every other option produces a flat partition that has to be hierarchically stacked by some external process. SBM's tree structure could simplify the T2/T3 generation logic considerably.

### Arm C — HDBSCAN on embeddings directly

**Library:** `hdbscan` (Python, well-maintained).

**Why:** A different *paradigm* — skip the graph entirely, cluster the embedding space.

- Captures *density* structure rather than *modularity* structure. Dense regions in embedding space become clusters regardless of the threshold-based edge construction.
- May surface different communities than Leiden — especially in regions where pairwise similarity is uniformly moderate (Leiden may merge into one big community; HDBSCAN may identify dense pockets within that region).
- Cheap to test. Two parameters (`min_cluster_size`, `min_samples`).

**Caveats:**
- Produces "noise" labels for points outside dense regions. Decision needed: do those become singleton T1 stragglers, or get force-assigned to nearest cluster?
- Hierarchy is partial (HDBSCAN's condensed tree gives some hierarchical info, but not as clean as Leiden's multi-level or SBM's native nested partition).

**Role in the A/B:** the paradigm contrast — if HDBSCAN finds clusters that the graph-based methods miss (or vice versa), that tells us something about whether phosphene's similarity terrain is better described as a graph or as a vector space.

### Arm D — Clique Percolation (CPM) — conditional

Only run this arm if you decide **overlap tolerance is a feature you want.** Adds complexity:
- Requires choosing k (the clique size)
- Computationally expensive (clique-finding is hard)
- Output is a set of overlapping communities, which changes downstream distillation logic (a T1 note belonging to multiple T2 clusters means distillation summaries see it multiple times)

If phosphene's personality is being distorted by strict partitioning during the establishment phase, CPM is the principled fix. If not, skip.

### Skipped (with rationale)

- **Louvain** — superseded by Leiden, no reason to use it directly.
- **Min-cut, Karger** — bisection only; produces an unbalanced binary cut, not many communities.
- **Girvan–Newman** — O(n³); the dendrogram is beautiful but it doesn't scale past toy graphs.
- **Label propagation** — too unstable, varies between runs at the same input. Bad fit for "stable labels" requirement.
- **Spectral clustering** — requires k.
- **Markov Clustering (MCL)** — used in bioinformatics for protein-protein interaction networks; no clear advantage over Leiden for semantic similarity graphs.
- **Modular / split decomposition** — unrelated to community detection despite the name overlap (these are graph-theoretic structural decompositions; on similarity graphs they find essentially nothing).

## Methodology

Reuse the simulation harness in `notebooks/regime_dynamics_v2.py` and friends. For each candidate algorithm:

### What to measure

Per-tick metrics already collected in NETWORK_OPTIMUMS work:
- Cluster count
- Mean cluster size (and distribution — flag heavy tails)
- Cluster persistence across ticks (tracking ID stability)
- Silhouette score (still useful as a relative comparison even if Leiden doesn't optimize it)
- Wall clock per tick

New metrics specific to this A/B:
- **Connectedness check** — for Leiden and SBM: trivially passes; for HDBSCAN-via-graph (if reconstructed): verify. Validates the Louvain pathology is actually being avoided.
- **Cluster cohesion** — mean intra-cluster similarity, mean inter-cluster similarity, ratio. Higher ratio = cleaner clusters.
- **Distillation quality proxy** — for each Tier 2 cluster, take the centroid embedding and the centroid + N-nearest items, and compute their mutual similarity. Sharper clusters distill better.
- **Hierarchy quality** — for Leiden (multi-level) and nested SBM (native): does the level-1 partition correspond to recognizable broad themes, and the level-2 partition to coherent sub-themes? Manual inspection on the real corpus is the strongest signal here.
- **Parameter sensitivity sweep** — for Leiden, plot cluster count vs resolution; for SBM, vs minimum description length / prior choices; for HDBSCAN, vs `min_cluster_size`. Look for **plateaus** (stable regimes) vs **cliff edges** (sensitive optima).
- **Resolution-limit probe** — construct a synthetic test where you know small communities exist (e.g., 5-node clique embedded in a larger graph). Does the algorithm find it? Leiden/Louvain will fail this past a threshold; SBM should succeed.

### How to compare

Two regimes to evaluate over:
1. **Real corpus** — the 117-chunk seed used in NETWORK_OPTIMUMS. Strongest signal because the data is genuine.
2. **Simulated steady-state** — long-run sim with perturbation-based ingestion (post pool exhaustion). Weaker signal because perturbation introduces artifacts; useful for stability comparisons over many ticks.

### Decision criteria

Prefer the algorithm that, on the real corpus:
1. Produces more **persistent clusters** (less label churn between adjacent ticks at similar parameter settings)
2. Has higher **cohesion ratio** (intra/inter similarity)
3. Has **better hierarchy quality** under manual inspection (the real test of whether T1→T2→T3 maps work)
4. Is **less sensitive** to its primary parameter (a stable plateau is better than a knife-edge optimum)
5. Doesn't fail the **resolution-limit probe** (this is a near-disqualifier for Leiden in scenarios where small communities are expected to matter)

If two arms tie or trade wins across these axes, prefer in this order:
- **Nested SBM** if hierarchy quality is critical and compute budget allows
- **Leiden** for ops simplicity (lighter library, faster, easier to interpret)
- **HDBSCAN** as a complementary signal, not a primary winner — its outputs have a different shape and may be worth combining rather than choosing

## Beyond Clustering — A/B Track Setup

This work is the first entry in a broader experimentation track. Future A/Bs likely to follow the same pattern:

- **Embedding model:** `all-MiniLM-L6-v2` vs `paraphrase-multilingual-MiniLM-L12-v2` (DEVPLAN immediate-todo #3). Critical for the bilingual corpus.
- **Retention parameters:** sweep `sim_threshold`, retention days, decay weights. NETWORK_OPTIMUMS already explored some of this; can be revisited with a real production signal.
- **Attention weights:** prompt vs structure blend, unresolvedness weighting.

To make these reusable, the A/B harness should:
1. Take a `(name, fn)` pair for each algorithm/config under test
2. Run identical scenarios, collect identical metrics
3. Output a side-by-side report (CSV + a notebook plot template)

If this clustering A/B ends up needing custom plumbing, factor it into a small `notebooks/ab_harness.py` so the next experiment doesn't pay the same cost.

## Open Questions

1. **Does the production distillation pipeline currently do any clustering?** Need to check `src/phosphene/distillation/` — the simulation does its own clustering, but if production already uses something different, that's another swap point.
2. **Hierarchical output integration.** Leiden returns a multi-level partition, nested SBM returns a native tree. Does phosphene's distillation use this hierarchy, or does it flatten? If it uses, we get T2 + T3 candidates from one algorithm run.
3. **Resolution parameter governance.** Should `resolution` (Leiden) / prior choices (SBM) / `min_cluster_size` (HDBSCAN) be user-tunable (via the future "cobwebbed panel" in todo #4), learned/adaptive, or fixed at deployment?
4. **Overlap tolerance — feature or noise?** Decision needed before considering CPM (or SBM mixed-membership variant). The personality-formation phase is probably the time to commit one way or the other.
5. **`graph-tool` install footprint.** Heavier than `leidenalg`. Worth checking Pi compatibility before committing to nested SBM as a serious contender.

## Effort Estimate

- **Leiden swap in simulation:** 1-2 hours (replace `linkage` calls, validate connectedness, plot cluster count vs resolution).
- **Nested SBM parallel run:** 3-4 hours (heavier setup — `graph-tool` install, learning curve, longer compute per run, interpreting posterior partitions).
- **HDBSCAN parallel run:** 1 hour (operates on embeddings directly, no graph step).
- **Side-by-side report on the real 117-chunk corpus:** 2-3 hours (three arms now, more axes to plot).
- **Resolution-limit synthetic probe:** 1 hour (small fixture, run all three).
- **Decision write-up to DECISIONS.md:** 30 minutes.

**Total: ~1-1.5 days end-to-end** for the three-arm A/B. Scope cleanly into a phase plan when ready to dispatch.

If you want to reduce risk on day one: run Leiden + HDBSCAN first (the two cheap arms), produce a draft comparison, then decide whether nested SBM is worth the extra compute. Skipping SBM means losing the native-hierarchy benefit but ships faster.
