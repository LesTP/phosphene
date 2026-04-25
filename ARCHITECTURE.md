# Phosphene — Architecture

## Component Map

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| Memory Store | Three-tier hierarchical memory (daily log → pattern layer → personality files). Index layer, density metrics, forgetting, versioned personality files. | none (leaf) |
| Seeding | One-time corpus-to-graph-to-personality pipeline. Produces initial Tier 2/3 files. | toolkit/embedding, Memory Store |
| Attention Filter | Personality-driven content selection and annotation. Prompt-to-structure transition. | toolkit/llm_client, toolkit/embedding, Memory Store (read: density metrics, existing notes) |
| Source Ingestion | Adapters for Telegram channels, RSS, Reddit → normalized content items. | none (leaf per adapter) |
| Distillation | Tier promotion: T1→T2 (RAPTOR-style clustering), T2→T3 (two-step reflect-evolve). | toolkit/clustering, toolkit/embedding, toolkit/llm_client, Memory Store |
| Generator | Prompted and lateral-freedom generation from personality context. Intent-tagged output. | toolkit/llm_client, Memory Store (read: personality files, unresolved threads) |
| Explorer | Link-following via Playwright, pre-fetch scoring, source evaluation protocol. | toolkit/embedding, toolkit/llm_client |
| Gateway | Multi-platform message bus (inbound + outbound). Telegram + Discord. | toolkit/telegram_client, discord library |
| Output Router | Maps generator output (intent_tag, mode) → platform + format + feedback affordance. | Gateway |
| Feedback Collector | Normalizes signals from all platforms into common format. Intent-aware interpretation. | Memory Store (write: feedback events) |
| Scheduler | Activation management: cron triggers, tension-responsive frequency, lateral-freedom budget allocation, ambient stream assembly. | Memory Store (read: tension metrics) |
| Orchestrator | Wires all modules. Manages activation lifecycle: trigger → load context → execute task → lateral opportunity → output → log. | All modules |

## Data Flow

### Core Objects
- **ContentItem** — {content, source, timestamp, url, linked_content} from Source Ingestion
- **AmbientContext** — {timestamp, budget_remaining, budget_trend, activation_count, time_since_interaction, memory_metrics} injected by Scheduler at activation time
- **AnnotatedFragment** — {content, annotation, friction_target, importance_score, connections} from Attention Filter
- **MemoryNote** — Obsidian-compatible markdown with frontmatter (tier, timestamp, links, importance, unresolvedness)
- **PersonalityContext** — Tier 3 files loaded fresh at each generation call
- **GeneratorOutput** — {content, intent_tag, output_mode, importance_score, is_lateral}
- **FeedbackEvent** — {source_platform, output_id, feedback_type, content, intent_tag}

### Flow
```
Source Ingestion → [ContentItem] → Attention Filter → [AnnotatedFragment] → Memory Store (Tier 1)
                                        ↑ reads density metrics, existing notes

Scheduler → assembles AmbientContext → injects into activation

Memory Store (Tier 1) → Distillation → Memory Store (Tier 2, Tier 3)
                         ↑ triggered by importance threshold

Memory Store (Tier 3 personality + Tier 2 patterns) → Generator → [GeneratorOutput]
                                                                        ↓
                                                                  Output Router
                                                                        ↓
                                                              Gateway → platforms
                                                                        ↓
                                                              Feedback Collector
                                                                        ↓
                                                              Memory Store (feedback events)

Explorer ← triggered by links in filtered content
Explorer → [ContentItem] → Attention Filter (same path as source ingestion)
Explorer → [SourceProposal] → human approval → Source Ingestion config
```

## Implementation Sequence

| Order | Module | Rationale | Status |
|-------|--------|-----------|--------|
| 1 | Memory Store | Leaf. Everything depends on it. Three-tier CRUD, index layer, density metrics API. | Not started |
| 2 | Seeding | Populates Memory Store with initial content. Enables testing downstream modules against real data. | Not started |
| 3 | Attention Filter | First module that actively uses Memory Store. Tests the density metrics interface. Core novel mechanism. | Not started |
| 4 | Source Ingestion | Feeds the Attention Filter. Enables daily operation loop. Start with one adapter (Telegram or RSS). | Not started |
| 5 | Gateway | Message bus for both input and output. Needed before any user-visible output. | Not started |
| 6 | Generator + Output Router | First user-visible outputs. Prompted generation from personality context. | Not started |
| 7 | Distillation | Core developmental mechanism. T1→T2 first, then T2→T3 with reflect-evolve. Tests toolkit/clustering RAPTOR strategy. | Not started |
| 8 | Feedback Collector | Closes the loop. Connects platform signals back to Memory Store. | Not started |
| 9 | Explorer | Link-following, source evaluation. Adds depth to ingestion but not required for core loop. | Not started |
| 10 | Scheduler + Orchestrator | Full activation lifecycle: tension-responsive scheduling, lateral-freedom budget, ambient stream injection. Last because it requires all other modules. | Not started |

## Coupling Notes

- Memory Store ↔ most modules: **tight by necessity** — it is the shared state. All reads go through the index layer; writes go through typed APIs. No module reads raw files directly.
- Attention Filter ↔ Memory Store: **read-heavy** — queries density metrics, existing notes for friction detection. The prompt-to-structure transition makes this coupling grow over time as the filter relies more on structural signals.
- Distillation ↔ Memory Store: **read-write** — reads Tier 1 to produce Tier 2, reads Tier 2 to produce Tier 3. Runs as a forked read-only process with write-back at completion (no corruption of live state).
- Generator ↔ Memory Store: **read-only** — loads fresh personality context at each call. Never writes.
- Source Ingestion ↔ Gateway: **none** — Source Ingestion pulls from APIs directly. Gateway handles human-facing messaging. Different concerns despite both touching Telegram.
- Output Router ↔ Gateway: **tight** — Router decides platform+format, Gateway executes. These could be one module; kept separate because routing logic is Phosphene-specific while Gateway is potentially reusable.
- Toolkit dependencies are one-way: Phosphene imports from toolkit. Toolkit never imports from Phosphene.
- **Extension:** Additional source adapters → additive (new adapter module). Additional output channels → additive (new Gateway adapter + Output Router rule). Additional ambient streams → Scheduler config change.

## Key Decisions

D-1: Toolkit as external dependency
Date: 2026-04-04 | Status: Closed
Decision: Shared modules (embedding, clustering, llm_client, telegram_client) live in a separate toolkit project. Phosphene imports from toolkit.
Rationale: Confirmed overlap with Year-in-Search and TGBot. Building shared modules once, tested by multiple consumers, avoids reinvention.
Revisit if: Toolkit interfaces prove too generic for Phosphene's specific needs and the abstraction cost exceeds the reuse benefit.

D-2: Ambient streams bypass Attention Filter
Date: 2026-04-04 | Status: Closed
Decision: Environmental context (time, budget, interaction recency) is injected as ambient data available to all modules, not filtered through the Attention Filter as content.
Rationale: Ambient streams are enclosure conditions, not foraging material. Filtering them would subject them to personality-shaped selection, defeating their purpose as environmental context the personality develops within.
Revisit if: The system develops a genuine need to selectively attend to environmental data (currently no evidence this is needed).

D-3: Per-activation lateral freedom, not scheduled free play only
Date: 2026-04-04 | Status: Closed
Decision: Every activation carries a small free-play budget for lateral movement. Dedicated free-play activations also exist, triggered by tension thresholds.
Rationale: Spontaneity for a discontinuous system means unpredicted lateral movement within an activation. A separate free-play schedule would make all "spontaneous" outputs actually scheduled.
Revisit if: Lateral movement consistently prevents scheduled tasks from completing, indicating the budget is too large or the mechanism needs throttling.

D-4: No individual ARCH files yet
Date: 2026-04-04 | Status: Closed
Decision: Defer individual ARCH_[module].md files until after Year-in-Search builds the toolkit modules.
Rationale: Writing ARCH files against hypothetical toolkit interfaces risks spec drift. Better to write them once toolkit APIs are real, tested code.
Closed: 2026-04-25. All toolkit modules complete. ARCH_memory_store.md written as first Phosphene module spec.

## Provisional Contracts

- **Memory Store ↔ Attention Filter density metrics** — resolved in ARCH_memory_store.md. The `get_density_metrics()` method returns note count, mean link degree, cluster count, unresolved count, and max unresolvedness. The Attention Filter uses these to compute its prompt-to-structure blend weight.
- **Distillation ↔ toolkit/clustering RAPTOR strategy** — resolved in ARCH_distillation.md. The Distillation engine constructs `raptor_summarizer` and `raptor_embedder` callbacks internally, wiring toolkit/llm_client and toolkit/embedding respectively, and passes them to `toolkit/clustering.cluster()` via `ClusterConfig`. Consumers of the Distillation engine don't interact with RAPTOR directly.
- **Scheduler ↔ Orchestrator activation lifecycle** — how the scheduler triggers activations, injects ambient context, and manages the lateral-freedom budget is the most complex coordination point. Provisional. Resolve last.
- **Generator ↔ Memory Store personality context loading** — partially resolved in ARCH_memory_store.md. `get_personality_context()` returns current Tier 3 files, loaded fresh per call. Whether the Generator should also receive relevant Tier 2 patterns is deferred to ARCH_generator.md.
