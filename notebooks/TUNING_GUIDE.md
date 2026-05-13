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

### Coherence threshold must match the embedding model

The `min_cluster_coherence` threshold (default 0.4) gates which clusters produce T2 notes. With the multilingual model (tighter similarity distribution), 0.4 is too strict — only 5 of 11 clusters pass, losing the largest and most thematically interesting groups.

Measured on 200-note sample (11 clusters):
- At 0.4: 5/11 pass (28% of notes promoted)
- At 0.3: 8/11 pass (75% of notes promoted)
- At 0.25: 11/11 pass (81% of notes promoted)

**What to test:** Run `tools/check_coherence.py` after seeding to see how your corpus's clusters score against the threshold. If >50% of clusters fail, lower the threshold.

**Set to 0.25 for multilingual corpora.** The clusters at 0.27 coherence produce valid summaries — they're diverse within a topic (e.g., bilingual music discussions) but still thematically coherent.

### LLM model fallback for cluster summaries

The summarizer now tries: primary model → same model retry → fallback model → placeholder. Fallback models are `claude-sonnet-4-20250514` and `claude-haiku-4-5-20251001`. This catches model-specific refusals without wasting the entire cluster.

### RAPTOR summary propagation (integration bug)

The toolkit's RAPTOR clustering stores summaries in `ClusterResult.tree[].summaries`, but Phosphene's normalizer was reading from `ClusterResult.labels` (Path B), which doesn't carry summaries. This caused T2 notes to contain raw T1 text instead of LLM-generated syntheses. Fixed by extracting summaries from the tree layers during normalization.

**What to watch for:** If T2 notes contain raw journal text instead of synthesis paragraphs, the summary propagation is broken. Check `ClusterResult.tree` structure against the normalizer.

### LLM model selection: newer isn't always better

`claude-sonnet-4-5-20250929` (Sonnet 4.5) consistently returns `stop_reason: refusal` on bilingual casual conversations — the exact content that makes up most of the corpus. Same prompts work perfectly on `claude-sonnet-4-20250514` (Sonnet 4) with `stop_reason: end_turn`.

Verified empirically: same cluster (30 notes, 25K chars of bilingual LJ conversations), same prompt, same system message. Sonnet 4.5 refuses. Sonnet 4 produces "multilingual social interaction centered around drug-related humor" — which is an accurate summary, not objectionable content.

The refusal happens on content that includes: transliterated Russian (`nu eto ty uzhe kuda-to zagnul`), casual drug references, informal language mixing. None of this is harmful — it's how bilingual people actually write in online journals.

**What to test:** Before committing to an LLM model for distillation, send your actual cluster content (not synthetic test data) through the API and check `stop_reason`. Use the raw `anthropic` client, not a wrapper that swallows the refusal as "empty response."

**What to watch for:** Model version upgrades may change safety classifier behavior. Sonnet 4 is deprecated (EOL June 15, 2026). When migrating to a newer model, re-test against real clusters before running a full seed.

**Cost note:** Sonnet 4 and 4.5 are priced the same ($3/MTok input). Haiku ($0.25/MTok) is an option for cluster summaries if budget is tight, but needs its own refusal testing.

### LLM API rate limits dominate batch processing time

Anthropic's API limit is 30K input tokens per minute. RAPTOR clustering produces ~50-200 clusters per batch, each needing an LLM summary call. Without throttling, the first 3 calls succeed and the rest get 429'd.

**Fix:** 20-second delay between cluster summary calls. 60-second backoff on 429. Per-cluster error tolerance (placeholder summaries for failed clusters, not abort). This makes the overnight seed take hours instead of minutes, but it completes.

**What to consider:** If your corpus is smaller (<500 notes), you might not hit the rate limit. If larger (>5000), consider using a cheaper model (Haiku) for cluster summaries to stay under budget. Estimated cost: ~$0.01 per cluster summary × number of clusters.

### Cluster summaries overflow the context window

Naive approach: send all cluster members as one prompt. With 300+ notes per cluster, that's 227K tokens — over the 200K limit.

**Fix:** Cap at 50 observations × 2000 chars each per summary call (~30K tokens). The LLM summarizes a representative sample, not every member. This loses some coverage but the RAPTOR hierarchy compensates — higher-level summaries aggregate lower-level ones.

### Note ID collisions on multi-item posts

When corpus adapters extract multiple items from a single source entry (e.g., LJ post + its comment replies), all items may share the same title and timestamp. The note ID hash must include the content, not just title + timestamp, to prevent silent file overwrites.

Symptom: `run.py` reports "3859 stored" but `ls vault/tier1/ | wc -l` shows far fewer files (e.g., 1,469). No errors thrown — files are silently overwritten.

Fix: `generate_note_id()` includes content in the SHA1 hash input.

**What to test:** After seeding, verify `ls vault/tier1/ | wc -l` matches the reported count. If they differ, check for title+timestamp collisions with `tools/debug_seed200.py`.

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

## TODO: Illustrations

After the first successful seed run, add visual illustrations:
- **UMAP 2D cluster maps** — show actual cluster structure (from `tools/visualize_network.py`)
- **Regime comparison** — same seed with different attention filter weight profiles, showing which regions of the embedding space each profile selects/rejects. Side-by-side UMAP projections with accepted notes highlighted.
- **Chronological development** — snapshots of the network after each batch (batch 1 = 2002-2003, batch 5 = 2005, batch 15 = 2015+). Show how clusters form, merge, split over time.
- **Pruning effects** — network before/after a decay cycle, showing what survived and what died

These require a completed seed run with distillation.

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
