# ARCH: Explorer

## Purpose
Autonomous link-following and source evaluation. When the Attention Filter accepts content containing URLs, the Explorer fetches those linked pages, evaluates them for relevance, and feeds worthy content back through the Attention Filter as new `ContentItem` objects. Adds depth to ingestion — the system doesn't just process what's handed to it, it follows threads outward. Includes a pre-fetch scoring step (commodity LLM) to avoid wasting budget on low-relevance links. Optional module — the core loop runs without it.

## Public API

### Types

```python
@dataclass
class ExplorerConfig:
    llm_config: LLMConfig                           # toolkit/llm_client — for pre-fetch scoring
    llm_tier: ModelTier = ModelTier.COMMODITY         # commodity tier for scoring (cheap, many calls)
    embedding_config: EmbeddingConfig                 # toolkit/embedding — for relevance comparison
    fetch_timeout: timedelta = timedelta(seconds=30)  # per-URL HTTP timeout
    max_content_length: int = 50_000                  # max chars extracted per page (truncate beyond)
    max_depth: int = 1                                # link-following depth (1 = follow links from filtered content,
                                                      # 2 = also follow links found in those pages, etc.)
    max_urls_per_batch: int = 20                      # cap on URLs processed per explore activation
    min_relevance_score: float = 0.3                  # pre-fetch relevance threshold [0.0, 1.0]
    respect_robots: bool = True                       # obey robots.txt
    rate_limit_per_domain: timedelta = timedelta(seconds=5)  # minimum delay between requests to same domain

@dataclass
class ExploreRequest:
    urls: list[UrlCandidate]                          # URLs to evaluate and potentially fetch
    budget_tokens: int = 2000                         # token budget for pre-fetch scoring LLM calls

@dataclass
class UrlCandidate:
    url: str
    context: str                                      # text surrounding the URL in the source content
    source_note_id: str                               # note_id of the Tier 1 note containing this URL
    source_annotation: str | None = None              # Attention Filter annotation of the source content

@dataclass
class ExploreResult:
    fetched: list[ContentItem]                        # successfully fetched and scored above threshold
    skipped: list[SkippedUrl]                         # below relevance threshold (not fetched)
    failed: list[FailedUrl]                           # fetch attempted but failed
    total_scored: int                                 # URLs that went through pre-fetch scoring
    total_fetched: int                                # URLs actually fetched

@dataclass
class SkippedUrl:
    url: str
    relevance_score: float                            # pre-fetch score (below threshold)
    reason: str                                       # why it was skipped

@dataclass
class FailedUrl:
    url: str
    error: str                                        # fetch error (timeout, 404, parse failure, etc.)
```

### Constructor

- **Signature:** `Explorer(memory_store: MemoryStore, config: ExplorerConfig)`
- **Parameters:**
  - memory_store: MemoryStore — for querying existing notes (deduplication, relevance context)
  - config: ExplorerConfig — fetch settings, scoring thresholds, rate limits
- **Errors:** none

### explore

- **Signature:** `explore(request: ExploreRequest) -> ExploreResult`
- **Parameters:**
  - request: ExploreRequest — URLs to evaluate, token budget for scoring
- **Returns:** ExploreResult — fetched content items (ready for Attention Filter), plus skipped and failed URLs
- **Errors:**
  - `LLMAPIError` — pre-fetch scoring LLM call failed (from toolkit/llm_client)

**Behavior:**

1. **Deduplicate:** check URLs against Memory Store — skip any URL already present as a `url` field on an existing note (already ingested).
2. **Pre-fetch score:** for each new URL, call LLM (commodity tier) with the URL, its surrounding context, the source annotation, and a sample of current personality context. Ask: "How relevant is this link likely to be, given what this system cares about?" Returns a relevance score in [0.0, 1.0].
3. **Filter:** discard URLs below `min_relevance_score`.
4. **Fetch:** for URLs above threshold, fetch the page content via HTTP. Extract text (strip HTML/JS/CSS). Respect `robots.txt` (if `respect_robots`) and `rate_limit_per_domain`.
5. **Normalize:** produce `ContentItem` objects with `source="explorer"`, the fetched text as `content`, and any links found in the page as `linked_urls` (for potential depth > 1 following).
6. **Depth control:** if `max_depth > 1`, newly found `linked_urls` are added to the queue for the next depth level. Each depth level applies the same pre-fetch scoring. Most runs should use `max_depth=1`.

### queue

- **Signature:** `queue(url: str, context: str, source_note_id: str, annotation: str | None = None) -> None`
- **Parameters:**
  - url: str — URL to add to the exploration queue
  - context: str — surrounding text from the source content
  - source_note_id: str — note_id of the note containing this URL
  - annotation: str | None — Attention Filter annotation (if available)
- **Returns:** None. Adds to the internal queue for the next `explore` call.
- **Errors:** none (silently deduplicates against queue and existing notes)

Convenience method for the Orchestrator to queue URLs extracted from accepted `AnnotatedFragment.linked_urls` without immediately triggering an explore activation.

### get_queue

- **Signature:** `get_queue() -> list[UrlCandidate]`
- **Parameters:** none
- **Returns:** list[UrlCandidate] — current exploration queue
- **Errors:** none

## Pre-Fetch Scoring

The pre-fetch score prevents the Explorer from wasting fetch budget and Attention Filter cycles on low-relevance links. The scoring prompt is lightweight (commodity tier) and includes:

- The URL itself (domain and path often signal relevance)
- The surrounding context (what was the link embedded in?)
- The source note's Attention Filter annotation (why was the source content retained?)
- A brief personality summary (what does this system care about?)

The score reflects **predicted relevance to the personality**, not general quality. A high-quality article on an irrelevant topic scores low. A rough blog post on a core interest scores high.

**Scoring is the budget gate.** Most URLs will be skipped. This is by design — the Explorer is selective, not comprehensive.

## Integration

The Explorer sits between the Attention Filter (upstream — provides URLs to follow) and the Attention Filter again (downstream — Explorer output goes back through filtering):

```
Attention Filter → accepted fragments with linked_urls
    → Orchestrator queues URLs via explorer.queue()
    → Orchestrator triggers "explore" activation
    → Explorer.explore() → pre-fetch score → fetch → ContentItem
    → Attention Filter.filter_content() → Memory Store (Tier 1)
```

Explorer output is treated identically to Source Ingestion output — it goes through the Attention Filter with the same criteria. The `auto_accept_sources` config does **not** include `"explorer"` by default — autonomously followed links are filtered normally, unlike human-shared content.

## Inputs

- **UrlCandidate** — URLs from accepted content's `linked_urls`, with context and source note metadata. Queued by the Orchestrator.
- **ExplorerConfig** — fetch settings, scoring thresholds, depth limits.
- **ExploreRequest** — batch of URLs to process with token budget.

## Outputs

- **ContentItem** — fetched page content with `source="explorer"`. Passed to Attention Filter.
- **ExploreResult** — batch result with fetched, skipped, and failed URLs for monitoring.

## State

- **URL queue:** in-memory list of `UrlCandidate` objects waiting to be explored. Not persisted — lost on restart, which is acceptable (URLs will be re-encountered if they're in accepted content).
- **Domain rate limiter:** in-memory map of `domain → last_request_timestamp`. Enforces `rate_limit_per_domain`. Reset on restart.
- **Seen URLs:** in-memory set of URLs already processed or queued in this session. Deduplication against Memory Store is the durable layer.
- No persistent state beyond what's in Memory Store.

## Usage Example

```python
from explorer import Explorer, ExplorerConfig, ExploreRequest, UrlCandidate
from attention_filter import AttentionFilter, AttentionFilterConfig
from memory_store import MemoryStore, NoteInput
from llm_client import LLMConfig, ModelTier
from embedding import EmbeddingConfig

store = MemoryStore(MemoryStoreConfig(vault_path="./memory"))
af = AttentionFilter(memory_store=store)

explorer = Explorer(
    memory_store=store,
    config=ExplorerConfig(
        llm_config=LLMConfig(provider="anthropic", api_key="sk-...",
                             models={"commodity": "claude-haiku-..."}),
        llm_tier=ModelTier.COMMODITY,
        embedding_config=EmbeddingConfig(model="all-MiniLM-L6-v2"),
        max_depth=1,
        min_relevance_score=0.3,
    ),
)

# Orchestrator queues URLs from accepted fragments
for fragment in filter_result.accepted:
    for url in fragment.linked_urls:
        explorer.queue(
            url=url,
            context=fragment.content[:500],
            source_note_id=fragment_note_id,
            annotation=fragment.annotation,
        )

# Orchestrator triggers explore activation
candidates = explorer.get_queue()
if candidates:
    result = explorer.explore(ExploreRequest(
        urls=candidates[:20],
        budget_tokens=2000,
    ))

    print(f"Explored: {result.total_fetched} fetched, "
          f"{len(result.skipped)} skipped, {len(result.failed)} failed")

    # Feed fetched content back through Attention Filter (normal filtering, not auto-accepted)
    if result.fetched:
        filter_result = af.filter_content(result.fetched, filter_config)
        for fragment in filter_result.accepted:
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
```
