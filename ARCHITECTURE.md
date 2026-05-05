# Phosphene — Architecture

## Component Map

| Component | Responsibility | Dependencies |
|-----------|---------------|--------------|
| Memory Store | Three-tier hierarchical memory (daily log → pattern layer → personality files). Index layer, density metrics, forgetting, versioned personality files. | none (leaf) |
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
| Reviewer Panel *(deferred — flexible scope, see below)* | Multi-model evaluation of Generator outputs against personality criteria. Produces signals for the Feedback Collector. | toolkit/llm_client (multiple model handles), Generator (consumes outputs), Memory Store (read: personality context for evaluation criteria) |
| Model Router *(deferred — flexible scope, see below)* | Routes LLM calls across providers/subscriptions to realize the union-of-subscriptions cost model. Sits as a thin layer in front of toolkit/llm_client. | toolkit/llm_client |

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
| 1 | Memory Store | Leaf. Everything depends on it. Three-tier CRUD, index layer, density metrics API. | Complete |
| 2 | Attention Filter | First module that actively uses Memory Store. Tests density metrics. Core novel mechanism. | Complete |
| 3 | Source Ingestion | Feeds the Attention Filter. Enables daily operation loop. Corpus adapters for initial import. | Complete |
| 4 | Gateway | Message bus for input and output. Needed before user-visible output. | Complete |
| 5 | Generator + Output Router | First user-visible outputs. Prompted generation from personality context. | In progress |
| 6 | Distillation | Core developmental mechanism. T1→T2 with RAPTOR, T2→T3 with reflect-evolve. | Not started |
| 7 | Feedback Collector | Closes the loop. Connects platform signals back to Memory Store. | Not started |
| 8 | Explorer | Link-following, source evaluation. Adds depth to ingestion but not required for core loop. | Not started |
| 9 | Orchestrator | Full activation lifecycle: tension-responsive scheduling, lateral-freedom budget, ambient stream injection. Last because it requires all other modules. | Not started |

### Flexible / Deferred Components

The following are in PROJECT.md's flexible-scope `[in]` set but have no numbered slot in the Implementation Sequence above. They will be promoted (assigned a build order, given an `ARCH_*.md` file, and added to the active sequence) when the operational pressure that motivates them becomes real.

| Module | Promote when | Status |
|--------|--------------|--------|
| Reviewer Panel | Generator outputs are landing on real channels and a single-model evaluation signal is no longer enough (e.g., systematic bias suspected, or feedback-loop calibration needs cross-model corroboration). | Deferred — flexible scope. ARCH file not yet written. |
| Model Router | Subscription rotation moves from a configuration-time choice to a runtime concern (e.g., a single subscription's daily cap is hit during a normal day, or multi-provider routing is needed inside a single activation). | Deferred — flexible scope. ARCH file not yet written. |

Both are flagged as load-bearing for downstream concerns (Reviewer Panel for `Reviewer Panel Calibration` in PROJECT.md Risks; Model Router for the `Subscription rotation strategy` cost model in Constraints), so the deferral is about timing, not importance. See D-10.

### Deferred Test Investments

Test-debt items recognised but not scheduled. Each has an explicit promote-when trigger so it stops being invisible when the trigger fires. Same shape as the components table above.

| Investment | Promote when | Status |
|------------|--------------|--------|
| Real-adapter integration tests for Source Ingestion (Telegram / RSS / Reddit / corpus) | Concrete adapters land in Module 3 Phase 2+. Each adapter's PR includes at least one test that hits the real API surface (recorded fixture or live, depending on adapter), not just the FakeAdapter path. | Partially complete — Phase 2 added fixture and fake-boundary coverage for all concrete adapters; live external-service tests remain deferred until credentials and a live integration harness exist. |
| LLM prompt/parse round-trip tests for Attention Filter | A model upgrade is planned, OR a production parsing failure is observed, OR before Generator (Module 5) ships (since Generator inherits the same prompt/parse risk surface). | Deferred — current FakeLLM tests verify control flow but not the actual prompt strings or JSON-parse-on-real-output. |
| Property-based tests (decay, scoring blends, normalization helpers) | A bug is found in one of these areas that example-based tests missed, OR before any of these algorithms is changed in a non-trivial way (the property tests then act as regression armour for the change). | Deferred — example-based coverage is currently sufficient and property tests have a non-trivial setup cost (hypothesis dependency, strategy design). |
| Coverage tooling (pytest-cov + baseline report) | Completed at the Module 3 Phase 1 → Phase 2 boundary. Re-run before phase completions or when coverage drops are suspected. | Complete — baseline captured 2026-05-04: 310 tests pass, 98% total coverage; memory_store 98%, attention_filter 97%, source_ingestion 99%. |

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

See DECISIONS.md for the full decision log (D-1 through D-38).

## Provisional Contracts

- **Memory Store ↔ Attention Filter density metrics** — resolved in ARCH_memory_store.md. The `get_density_metrics()` method returns note count, mean link degree, cluster count, unresolved count, and max unresolvedness. The Attention Filter uses these to compute its prompt-to-structure blend weight.
- **Distillation ↔ toolkit/clustering RAPTOR strategy** — resolved in ARCH_distillation.md. The Distillation engine constructs `raptor_summarizer` and `raptor_embedder` callbacks internally, wiring toolkit/llm_client and toolkit/embedding respectively, and passes them to `toolkit/clustering.cluster()` via `ClusterConfig`. Consumers of the Distillation engine don't interact with RAPTOR directly.
- **Scheduler ↔ Orchestrator activation lifecycle** — resolved in ARCH_orchestrator.md. The Orchestrator subsumes the Scheduler role. Activation lifecycle: trigger → assemble AmbientContext → budget check → execute task → lateral check → route outputs → collect feedback → log. Tension-responsive scheduling adjusts frequency and budget based on `memory_store.get_density_metrics()`. Lateral-freedom budget is a configurable ratio (default 15%) of per-activation token budget, allocated when unresolved tension exceeds threshold.
- **Generator ↔ Memory Store personality context loading** — resolved in ARCH_generator.md. The Generator uses `memory_store.get_personality_context()` for Tier 3 (loaded fresh per call) and enriches with relevant Tier 2 patterns via `memory_store.search_by_embedding()`. Tier 2 inclusion is configurable (`include_tier2_patterns`, default True). Skeptical memory verification checks Tier 3 claims against recent Tier 1 before generating.
