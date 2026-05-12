# Phosphene Tuning Guide — Corpus to Personality

What we learned bringing a bilingual personal archive (LJ, Blogspot, Facebook, text notes) through Phosphene's memory pipeline. Written for anyone running this on a different corpus, and for anyone curious about the non-obvious engineering of personality-from-archives.

## The Source Material Problem

Your corpus is not clean training data. It's 20 years of a human being inconsistent across platforms, languages, registers, and moods. The interesting engineering is in making the system see *through* the noise to the personality signal.

### Language is the dominant clustering signal

With a monolingual embedding model (`all-MiniLM-L6-v2`), all Russian text clusters together regardless of topic. A post about rock climbing and a post about Soviet animation land in the same cluster because they share Cyrillic characters. The model embeds language, not meaning.

**Fix:** Multilingual model (`paraphrase-multilingual-MiniLM-L12-v2`). Same 384-dim output, drop-in replacement. Cross-lingual similarity gap reduced 80% (from 0.375 to 0.076). Russian posts about music now cluster with English posts about music, not with Russian posts about politics.

**What to test:** Run terrain analysis on your corpus with both models. Compare within-language vs cross-language similarity means. If the gap is >0.2, you need a multilingual model.

### High-dimensional embeddings defeat density clustering

HDBSCAN on raw 384-dim embeddings produces one mega-cluster (733/3919 notes) and 76% noise. The curse of dimensionality — everything is roughly equidistant in high dimensions, so HDBSCAN can't find density peaks.

**Fix:** UMAP dimensionality reduction to 15 dims before HDBSCAN. Result: 227 clusters, largest 50 notes, 38% noise. Tested dims 5/10/15/20; 15 was optimal for this corpus.

**What to test:** Run `tools/test_reduce_dims.py` on your seeded vault. Compare cluster count, largest cluster, noise percentage across dims. The sweet spot depends on corpus diversity — more diverse content needs fewer dims.

### LLM API rate limits dominate batch processing time

Anthropic's API limit is 30K input tokens per minute. RAPTOR clustering produces ~50-200 clusters per batch, each needing an LLM summary call. Without throttling, the first 3 calls succeed and the rest get 429'd.

**Fix:** 20-second delay between cluster summary calls. 60-second backoff on 429. Per-cluster error tolerance (placeholder summaries for failed clusters, not abort). This makes the overnight seed take hours instead of minutes, but it completes.

**What to consider:** If your corpus is smaller (<500 notes), you might not hit the rate limit. If larger (>5000), consider using a cheaper model (Haiku) for cluster summaries to stay under budget. Estimated cost: ~$0.01 per cluster summary × number of clusters.

### Cluster summaries overflow the context window

Naive approach: send all cluster members as one prompt. With 300+ notes per cluster, that's 227K tokens — over the 200K limit.

**Fix:** Cap at 50 observations × 2000 chars each per summary call (~30K tokens). The LLM summarizes a representative sample, not every member. This loses some coverage but the RAPTOR hierarchy compensates — higher-level summaries aggregate lower-level ones.

### "Your" content vs other people's

In LJ exports, comments from other people are embedded alongside your posts. Their voice dilutes your personality signal. In Facebook exports, "shared a post" and "added a photo" boilerplate creates junk clusters.

**Fixes applied:**
- LJ: Strip comments section, but extract *your* replies with parent context (`[context: username] their text\n[reply] your text`)
- Facebook: Strip boilerplate patterns ("shared a post/photo", "added a new photo")
- Blogspot: Include your follow-up comments (they're personality signal), skip others' comments when threading data isn't available
- Music blog: Strip track listings (numbered song lists), share links (depositfiles, megaupload), bitrate lines

**What to test:** After seeding, run `tools/inspect_clusters.py`. Look for clusters that are entirely junk (boilerplate, metadata, link-only posts). These indicate missing cleanup patterns in the adapter.

## The Parameter Landscape

### Data-constrained vs free parameters

The corpus determines: similarity distributions, natural cluster boundaries, link density at each threshold. These are measured, not chosen.

The free parameters are: `sim_threshold` (what similarity counts as a "link"), `base_retention_days` (how long notes survive without links), `density_crossover` (when structural scoring takes over from personality scoring), pruning schedule.

**Grid search results** (from `notebooks/NETWORK_OPTIMUMS.md`):
- `sim_threshold=0.4` — optimal for both monolingual and multilingual models, but the selectivity is very different (37% of pairs link with English model, 11.5% with multilingual)
- `base_retention=20-30 days` — shorter kills the network, longer lets noise accumulate
- Periodic pruning (25d accumulation / 5d mild pruning) produces 3× link density and 2× unresolvedness vs pure slow accumulation at equal content consumption

### Chronological seeding matters

Bulk-loading all content at once produces a flat snapshot — distillation sees everything simultaneously and can't distinguish early interests from late ones. Chronological seeding (sorted by timestamp, fixed-size batches of 200 with distillation between each) lets early writing shape initial T2 patterns that later writing reinforces or challenges. The T3 personality files accumulate version history.

### Phase 2 attention filter activates organically

Direct seeding writes notes with zero structural metadata (no links, no clusters, no unresolvedness). Phase 2 structural scoring requires `mean_link_degree >= 1.5` and `cluster_count >= 3`. After direct seed, all metrics are zero — Phase 2 is naturally inactive. It activates only after distillation creates real structure. No manual `density_crossover` adjustment needed.

## Tools

| Tool | What it does |
|------|-------------|
| `tools/visualize_network.py` | UMAP 2D scatter plot of vault, colored by cluster |
| `tools/inspect_clusters.py` | Show cluster sizes, sources, sample texts |
| `tools/test_reduce_dims.py` | Compare UMAP dims for optimal HDBSCAN clustering |
| `tools/measure_density.py` | Check vault link density and Phase 2 activation |
| `tools/check_clustering_compat.py` | Dry-run toolkit interface validation |

## Cost Estimates

| Operation | Cost | Notes |
|-----------|------|-------|
| Corpus embedding | Free | Local CPU, ~3 min for 4K notes |
| `--seed-direct` | Free | Embedding only, no LLM |
| `--seed-chronological` (20 batches) | ~$5-10 | Distillation per batch |
| Single `--once` cycle | ~$1-3 | Distillation + generation |
| Daily cron operation | ~$0.50-1 | Ingestion + periodic distillation |
| `--seed-only` (LLM attention filter) | ~$35 for 3.5K notes | **Avoid** — use `--seed-direct` |
