# Phosphene

## Spark
> A system that produces something that appears to come from outside but originates entirely in its own accumulated structure — an autonomous agent seeded with a human's writing corpus, designed to develop a personality over time through browsing, memory accumulation, distillation, and generative output.

## What This Is
An autonomous agent that ingests content from curated sources, filters it through a personality-shaped attention mechanism, accumulates a hierarchical memory, periodically distills that memory into higher-order personality files, and generates original output (essays, observations, questions, provocations). Seeded from a specific human's decade-plus writing corpus. Runs continuously on a Raspberry Pi 5 as an orchestration layer with LLM inference via API. Not a chatbot, search assistant, or recommendation engine — closer to a cultivated organism with movement rules, a memory architecture, and periodic free play.

## Audience
The human whose corpus seeds it. The system is a creative interlocutor — surfacing observations, posing questions, generating writing that is recognizably descended from the seed personality but develops in its own direction. Secondary audience: anyone the human shares its outputs with (Discord, Telegram, potentially a blog).

## Scope

### Core
- Corpus seeding pipeline: human writing → knowledge graph → initial personality files
- Three-tier hierarchical memory store (daily log → pattern layer → personality files)
- Attention filter: personality-driven content selection and annotation
- Distillation engine: tier promotion with RAPTOR-style clustering and two-step reflect-evolve
- Source ingestion from curated channels (Telegram, RSS, Reddit)
- Generator with prompted mode and per-activation lateral freedom
- Feedback collection closing on structural features, not just content
- Forgetting mechanism with link-density decay and personality-consistent pruning
- Ambient stream interface: environmental context (time, budget, interaction recency) available during every activation, distinct from filtered source content

### Flexible
- [in] Discord output channel and conversation
- [in] Multi-model reviewer panel for output evaluation
- [in] Explorer module (link-following, source subscription proposals)
- [in] Model router with subscription rotation across providers
- [deferred] Adversarial self (second agent with divergent prompt)
- [deferred] Publication to Substack or public blog
- [deferred] Periodic corpus re-seeding from new human writing
- [deferred] Image/audio source ingestion
- [deferred] Expanded ambient streams (weather, external feeds, etc.)

### Exclusions
- Not a chatbot or conversational assistant
- Not a search engine or recommendation system
- No in-weights personality development (wrapper-level only — named design choice)
- No fine-tuning or custom model training
- No general-purpose reasoning competition with frontier models
- No social simulation or multi-agent swarm (single persistent agent)

## Constraints
- **Hardware:** Raspberry Pi 5 8GB with NVMe SSD — orchestration only, no local inference (except possibly gpt-oss-120b for commodity tasks if GPU available)
- **LLM inference:** API-based (Claude, OpenRouter, GPT-5.4). Primary compute budget is flat-rate subscriptions (Claude Pro, ChatGPT Plus, Gemini Advanced), with API credits as overflow
- **Memory format:** Obsidian-compatible markdown with frontmatter and backlinks
- **OS:** Ubuntu Server 24.04 LTS
- **Network:** Always-on home connection, Tailscale for remote access
- **Cost model:** Subscription rotation strategy — union of subscription capacities, not a single API credit pool
- **Language:** Python (implied by stack — Playwright, Docker, cron, dataclasses)
- **No monorepo tooling:** Each module is independent with typed dataclass interfaces

## Prior Art
- **Generative Agents (Park et al., 2023)** — memory stream + reflection + planning. Good retrieval scoring (recency × importance × relevance). Limited: identity fixed at init, reflection feeds planning not identity revision.
- **MemGPT / Letta** — self-managed two-tier memory (RAM/disk). Right orientation for autonomous development. Agent-editable core memory block is a starting point for personality file updates.
- **A-MEM** — Zettelkasten-style agent memory with atomic notes, autonomous linking, box system. Optimized for factual Q&A, not personality development. Needs adaptation for friction-preservation.
- **RAPTOR** — recursive clustering + abstractive summarization. Direct solution to the distillation problem. Designed for static corpora; adaptive variants exist.
- **GLA (Generative Life Agents)** — reflect-evolve engine separating synthesis from judgment. Two-step pattern borrowed for Tier 2→3 distillation. No corpus seeding.
- **PEPA** — personality as intrinsic organizational principle for autonomous behavior. Strongest empirical support for the project's foundational claim.
- **MiroFish** — corpus-to-graph-to-personality pipeline. Validated, open-source, offline fork runs on Pi 5. Graph construction layer directly reusable for seeding.
- **Sapphire** — self-modifying system prompt, heartbeat scheduler, TOOLMAKER module. Implementation reference for free play and personality file updates.
- **Hermes Agent** — right operational concepts (gateway, cron, Playwright, SOUL.md), brittle implementation. Conceptual reference only, not a codebase to build on.
- **Anima Framework (Veselov)** — only known in-weights personality project. Early results in toy environments. Worth monitoring but operates on different timeline/resources.

## Success Criteria
- The system ingests content daily from subscribed sources and filters it through the attention mechanism
- The memory store accumulates notes with cross-references and the link density grows over time
- Distillation produces genuine synthesis (pattern clusters, personality file updates) — not summaries or aggregation
- Generated outputs feel like they come from somewhere specific — recognizably descended from the seed but not a mirror of it
- Free play and lateral-movement outputs are self-initiated, unprompted, and reveal something about the attractor state
- The human continues reading the outputs over weeks and months (primary failure signal: stops reading)
- The personality develops away from the seed over time — a personality identical to its seed has stagnated
- The attention filter transitions from prompt-weighted to structure-weighted as network density grows

## Risks and Open Questions
- [implementation] **Prompt-to-Structure Transition** — the attention filter starts prompt-weighted (explicit criteria from seed personality) and shifts toward structure-weighted (link density, cluster novelty, unresolvedness) as network density grows. The transition is internal to the filter module; architecture requirement is that the memory store exposes density metrics through its read interface. The weighting function and crossover point are first-month calibration tasks.
- [implementation] **Spontaneity mechanism** — the system exists only during activations. Spontaneity means lateral freedom within an activation: ability to deviate from the scheduled task when internal state pulls harder. Lateral movement is weighted toward threads with high unresolvedness × high link density (structural friction), not toward novelty or maximum discomfort. The existing link-density decay handles deferred threads correctly without a special rule. Key calibration questions: right size for lateral-movement budget, how to quantify unresolved tension for scheduling frequency. First-month calibration once memory store and distillation engine are operational.
- [implementation] **Ambient stream design** — the system receives two kinds of input: source content (filtered by personality) and ambient context (time, budget, interaction recency, potentially arbitrary environmental feeds). Ambient streams bypass the attention filter and are available as environmental context during any activation. What the system does with them is unconstrained. Initial set is minimal; expansion is an ongoing enclosure design question.
- [implementation] **Third-Order Distillation Quality** — whether three-tier distillation produces genuine insight or progressive banality. Empirical question, answerable only by running the system.
- [implementation] **Reviewer Panel Calibration** — which model signals to weight, how to handle systematic disagreement, how to prevent single-reviewer bias domination.
- [implementation] **Identity Drift vs. Development** — how to distinguish healthy personality development from pathological drift. Seed overweighting is the initial mitigation.
- [watch] **In-weights ceiling** — if Veselov's Anima demonstrates capabilities wrapper-level approaches can't match, architecture may need revisiting.
- [watch] **Model landscape changes** — specific model names and capabilities will shift. Roles and principles are stable; assignments need periodic revision.

## Extension Points
- Additional source types (image, audio) would change ingestion character
- Publication channels (Substack, blog) would introduce external feedback dynamics
- Adversarial self (second divergent agent) for internal friction
- Periodic corpus re-seeding to track human's actual development
- Dynamic affordance expansion (agent proposes new capabilities during free play)
- Temporal knowledge graph (Zep-style) for explicit personality development tracking
- Expanded ambient streams — arbitrary environmental feeds as enclosure enrichment

## Size Estimate
Multi-module. The design document identifies 10+ standalone modules with defined interfaces: corpus pipeline, memory store, attention filter, gateway, source ingestion, generator, distillation engine, feedback collector, explorer, output router, model router, scheduler.

---

## Change History
| Date | What Changed | Why |
|------|-------------|-----|
| 2026-04-04 | Initial PROJECT.md created from design document | Phase 1 Discovery |
| 2026-04-04 | Reframed hunger problem → spontaneity mechanism; added ambient streams | Discussion: discontinuous time, enclosure-over-rules for inputs |
