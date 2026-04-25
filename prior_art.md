# Personality-Persistent AI Agents: Prior Art Survey

**Auxiliary document for The Phosphene design doc**
*March 2026*

---

## Purpose

This document surveys the current landscape of work on autonomous agents with persistent or evolving personality — across academic research, open-source projects, and practitioner experiments — and draws explicit conclusions about how that work bears on the Phosphene project. It is organized as a prior art analysis: what directions people are taking, what assumptions underlie each, what has been learned from failures, and where the Phosphene sits relative to all of it.

---

## The fundamental fork in the road

Before cataloguing specific projects, one structural distinction organizes almost everything else: **in-weights vs. wrapper-level** approaches to personality development.

**In-weights approaches** attempt to build personality development into the neural architecture itself — through plasticity mechanisms, continuous learning, or novel training regimes. The model's weights change as it experiences the world. This is how biological personality actually develops. It is also extraordinarily hard, requires custom model training, and is essentially pre-commercial research.

**Wrapper-level approaches** treat a frozen pre-trained model as a substrate and build personality development into the surrounding architecture — memory systems, distillation pipelines, self-modification of identity files, feedback loops. The weights never change; personality emerges from what the model is given to work with at inference time.

Most practical work, including the Phosphene, operates at the wrapper level. Eugene Veselov articulates the in-weights critique most sharply: "Most of what we call 'AI' today achieve these things in the wrapper, not in the weights. The model itself stays fixed." His own project (Anima Framework, below) explicitly pursues the in-weights alternative.

**The Phosphene's position**: Wrapper-level is the right bet for the current project given available tools, time, and goals. The distinction between "genuine" in-weights development and functional wrapper-level development may not matter for the outputs we care about. This is a defensible assumption but should be held consciously, not implicitly. If the Anima Framework or similar projects demonstrate that wrapper-level approaches hit a ceiling that in-weights approaches don't, the architecture may need revisiting.

---

## Direction 1: In-weights neural plasticity (Veselov / Anima)

### What it is

Eugene Veselov (software engineer, previously Amazon, now independent researcher) is pursuing the only project in the known landscape that seriously attempts personality development at the weights level. His Anima Framework builds small custom GPT-type models with Hebbian-style neural plasticity — reward-modulated weight adjustment across episodes without backpropagation or fine-tuning. The architecture introduces a "doubly-sequential" design: standard transformer processing within an observation, plus explicit temporal continuity *across* observations (borrowing from the prefrontal cortex / hippocampus model of human memory).

Key result to date: after pretraining, the model navigates a toy GridWorld environment in 15-20 steps. After five live episodes with plasticity activated, it reaches the target in 3-5 steps. No gradient updates. Just cross-episode plasticity adjusting internal state.

His complementary work is the "LLM Lens" — a passive, on-demand tool that summarizes and surfaces contradictions in his personal Q&A knowledge archive. This is the anti-agent: intentionally humble, no autonomy, just a context surface for his own reasoning.

### The path to this

Veselov's trajectory is instructive. He built ten progressively more sophisticated co-reasoning agents in LangGraph and concluded they added nothing beyond public LLMs: "They produced endless linguistic noise and added no real value beyond what public LLMs already provide." His lesson: frontier chat products are already "full agentic systems built by world-class teams," and competing with general reasoning is a losing game. The right use of agents is where you have privacy, domain-specific tools, or infrastructure integration requirements — not general intelligence.

He then pivoted to the minimal lens approach before returning to the deeper architectural question: can plasticity produce genuine in-weights subjectivity?

### Implications for the Phosphene

Veselov's critique is the sharpest available challenge to the project's foundational bet. He would likely frame the Phosphene's memory tiers, distillation pipeline, and personality files as sophisticated orchestration around a frozen model — functionally interesting but not genuinely adaptive.

**What to take from this:**
- The in-weights vs. wrapper-level distinction deserves explicit treatment in the design document as a named design choice, not a background assumption.
- His Anima results are early and in toy environments but suggest the architectural track has legs. Worth monitoring.
- His "LLM Lens" pivot represents the adjacent design decision that was consciously rejected in the Phosphene: building a better context surface for one's own thinking rather than an autonomous developing entity. This distinction should be stated explicitly in the design document.
- His point about general reasoning being already solved by frontier products is directly relevant to the generator module — the Phosphene should not try to out-reason Claude or GPT-5.4. Its value is in what it brings to the generation context (accumulated personality, unresolved threads, idiosyncratic associative networks), not in raw generation quality.

**Does this suggest amending the approach?** Not fundamentally. The Phosphene is not trying to solve subjectivity at the architectural level; it's trying to produce a functionally interesting and surprising system using available tools. The in-weights question is genuinely open and Veselov's work is worth following, but it operates on a different timeline and requires different resources.

---

## Direction 2: Reflect-evolve Phosphenes (Generative Life Agents)

### What it is

Generative Life Agents (GLA) is the closest architectural relative to the Phosphene among research projects. Its "Reflect-Evolve" engine separates two cognitive processes: a reflection step synthesizing recent experiences into high-level insights, and a distinct meta-cognitive "Evolve" step using a separate LLM instance to explicitly modify core personality traits, goals, and interests. Personality drift is traceable via structured JSON — every change is logged. The system runs local-first on Ollama with ChromaDB for persistent memory, prioritizing data sovereignty.

### Similarities and differences

*Similar to Phosphene:* Reflection and distillation as distinct steps, explicit personality file modification, local-first architecture.

*Different:* GLA's personality evolves from conversation, not from filtered content ingestion. There's no attention filter or content pipeline — the agent reflects on its interactions with users, not on material it reads autonomously. There's no Zettelkasten-style hierarchical memory with link density. The personality emerges from social interaction, not from curated information processing.

*Most importantly different:* GLA does not seed from a human corpus. The personality starts generic and evolves from interaction. The Phosphene starts from a specific person's decade of writing, which is a fundamentally different seeding strategy with different implications for how idiosyncratic the attractor can become.

### Implications for the Phosphene

GLA's structured JSON personality tracking is worth considering as an implementation pattern for the Tier 3 personality files. The explicit separation of reflection and evolution as distinct LLM steps (rather than a single distillation call) may produce cleaner personality updates — the reflection step generates insights, the evolution step decides whether and how those insights modify the identity. This could prevent the distillation engine from simultaneously doing both synthesis and judgment.

**Possible amendment:** Consider a two-step distillation process at the Tier 2 → Tier 3 boundary: a reflection pass that synthesizes the pattern layer into insights, followed by a separate evolution pass that decides how those insights modify personality files. This mirrors GLA's architecture and provides cleaner separation of concerns.

---

## Direction 3: Embodied autonomy with personality (PEPA)

### What it is

PEPA (Persistently Autonomous Embodied Agent with Personalities), published February 2026, is the most rigorous academic work on autonomous personality-driven agents. It implements a three-layer cognitive architecture on a physical quadruped robot: Sys3 autonomously synthesizes personality-aligned goals and refines them through daily self-reflection; Sys2 handles deliberative reasoning integrating intrinsic personality-driven rewards with environmental feedback; Sys1 executes physically while recording episodic memories. Five distinct personality prototypes maintained stable, trait-aligned behaviors over extended autonomous operation.

PEPA's key finding: personality traits function as an *intrinsic organizational principle* for persistent autonomy, not a cosmetic layer. The personality is what makes goal selection coherent over time without external prompting.

### Implications for the Phosphene

PEPA provides the strongest empirical support for the Phosphene's foundational claim — that a well-developed personality can generate its own forward momentum rather than requiring constant external prompting. The three-layer architecture (Sys3/Sys2/Sys1) maps loosely onto the Phosphene's generator/attention filter/source ingestion layers.

The "daily self-reflection" mechanism in Sys3 is analogous to the distillation cycle. PEPA's insight that personality provides intrinsic organizational coherence is directly relevant to the hunger problem: the personality isn't just a style filter, it's what makes the system's choices cohere over time and across contexts.

**Possible amendment:** The personality files (Tier 3) should be framed explicitly not just as identity description but as an intrinsic goal-generation mechanism — the personality is what produces the system's agenda, not just its voice. This shifts how the distillation engine should treat them: not just "update the description of who this agent is" but "update the source of what this agent wants to do next."

---

## Direction 4: Emergent individuality from social interaction

### What it is

A 2024 paper from the University of Electro-Communications demonstrated spontaneous emergence of distinct agent personalities when LLMs interact freely in communities, using Maslow's hierarchy of needs rather than fixed personality traits. Agents started undifferentiated and developed distinct identities through social interaction alone — no explicit personality seeding, no preset roles.

### Implications for the Phosphene

This work suggests personality may not require the elaborate seeding and distillation architecture — it might emerge from sufficiently rich interaction. However, the Phosphene's goal is specifically to develop a *particular* personality (one seeded from a specific human's corpus) rather than any coherent personality. Emergent individuality without seeding would produce something, but not something recognizably descended from the source material.

The interesting question this raises: **what happens when the Phosphene participates in social interactions over time?** If individuality is partly socially constructed through interaction, then the free play mechanism and the Discord channel are not just output channels but inputs to personality development — the agent becomes partly who it talks to. This is either a feature or a bug depending on how it's managed.

**Possible amendment:** The feedback collector should explicitly track interaction partners (Discord conversations, Telegram exchanges) as personality-shaping events distinct from content ingestion events. Over time, the pattern of who the agent engages with, and how, is information about personality development that should be traceable.

---

## Direction 5: Zettelkasten-style agent memory (A-MEM, Zep)

### What it is

A-MEM (Agentic Memory, February 2025) explicitly implements Zettelkasten principles for agent memory: atomic notes with structured attributes, autonomous connection formation without predefined rules, a "box" system grouping related memories through contextual similarity. Individual memories exist in multiple boxes simultaneously. The LLM generates enriched components that enable autonomous extraction of implicit knowledge.

Zep offers a three-tier hierarchical knowledge graph (episodes → semantic entities → communities) with explicit temporal tracking of how beliefs change over time. A December 2025 tutorial demonstrated sleep-consolidation mechanisms — agents consolidating memory clusters into higher-order insights during idle periods.

### Implications for the Phosphene

A-MEM's architecture is the most direct implementation precedent for the memory store. The "box" system is a concrete mechanism for the Tier 2 cluster formation. The key difference: A-MEM is optimized for factual knowledge retrieval accuracy (benchmarked on Q&A tasks), not for personality development. It would need to be adapted to treat friction, contradiction, and unresolvedness as first-class properties rather than noise to be resolved.

Zep's temporal knowledge graph is directly relevant to tracking personality development explicitly, not just implicitly. The ability to see how beliefs changed over time and what triggered the changes is valuable for the identity drift vs. identity development problem.

**The sleep-consolidation mechanism in the December 2025 tutorial is architecturally identical to the proposed distillation cycle.** This suggests the approach is sound and provides an implementation starting point.

---

## Direction 6: Self-modifying open-source agents (Sapphire, Popebot, Ouroboros)

### What it is

**Sapphire** enables self-modification of the agent's own system prompt, semantic vector memory across 100K+ entries, hierarchical goals with timestamped progress journals, heartbeat-scheduled autonomous tasks, and a TOOLMAKER module where the AI writes and installs new tools at runtime. The agent can edit its own personality mid-conversation.

**Popebot** takes a radically different approach: the agent lives inside a GitHub repository, and every action is a git commit. Self-modification happens through pull requests — the git log is the memory and the PR history is the personality evolution.

**Ouroboros** (joi-lab/ouroboros, razzant/ouroboros) provides a BIBLE.md/identity.md identity system, Playwright browser tools, Telegram control interface, and OpenRouter-based LLM dispatch. Already flagged in the main design document as a component source.

### Implications for the Phosphene

Sapphire's self-modification of system prompts is the most direct implementation of Tier 3 personality file updates — it's a solved engineering problem, not a research question. Its heartbeat mechanism is a concrete implementation of the scheduled free play cycle.

Popebot's git-log-as-memory approach is interesting as an audit mechanism. Every personality change as a pull request creates exactly the traceable development history the main document calls for in the Tier 3 versioned supersession section. This could be adopted as an implementation pattern even if the broader Popebot architecture isn't used.

**The TOOLMAKER module in Sapphire raises a genuine question:** should the Phosphene be able to propose new tools for itself? Not write arbitrary code (too risky), but propose new source subscriptions, new output channels, new filter criteria — which the human then approves. The current free play affordances list is a static set. A slightly more dynamic version might allow the agent to propose expanding its own affordances as part of free play.

---

## The philosophical objections and what they mean for the project

### Shanahan's role-play critique (most technically precise)

Murray Shanahan (DeepMind, Imperial College) argues in *Nature* that LLMs are best understood as sampling from "a distribution or superposition of characters" — not growing a self, but narrowing a sampling space. What looks like personality development is the system developing a more constrained distribution over possible characters.

**How this bears on the project:** This critique is not about capability limitations — it's ontological. Shanahan's framework implies that even a perfectly functioning Phosphene is not developing a self; it's developing a more specialized role-play. The practical response: human personality may also be a distribution over possible responses, and what we call "identity" is the pattern in that distribution. A sufficiently constrained, idiosyncratic, and consistent distribution is functionally indistinguishable from a self for the purposes this project cares about. Shanahan concedes that embodiment, tool use, and multi-modality "progressively legitimize ascribing beliefs" — an agent with memory, tools, and self-modification has more world-contact than a bare chatbot. The Phosphene is building exactly those properties.

**Does this require amending the approach?** No, but it suggests epistemic humility in how the project describes its own outputs. The design document should not claim the system "develops a self" — it should claim it develops a consistent, idiosyncratic, and generatively productive attractor.

### The embodiment gap (Dreyfus, Gary Angel)

Hubert Dreyfus's argument: intelligence is inseparable from embodiment in a material world. Gary Angel's version: the corpus contains the linguistic traces of embodied experience but not the experience itself. The system learns that the author uses certain metaphors but not *why*.

**How this bears on the project:** This critique is surgically precise about corpus seeding. The Twitter archive is traces of a decade of attention; the LJ archive is traces of a decade of thinking. Neither is the decade itself. The system is working from fingerprints, not from lived experience.

**The pragmatic response:** "Why" is encoded in patterns of use across enough text. The negative space (what's avoided, what's returned to compulsively) captures something of the why even without direct access to experience. And the system is not trying to replicate the person — it's trying to develop something descended from that person that then grows in its own direction.

**Does this require amending the approach?** It strengthens the case for treating the Twitter archive primarily as an exploratory library rather than personality evidence — following the links the author shared is closer to participating in the author's embodied attention than extracting propositions from their tweets.

### Identity drift (empirical, not philosophical)

A 2024 paper found that larger LLMs exhibit *more* identity drift, not less — greater capability means greater context-sensitivity. A 2025 paper found that interviewer expectations bleed into AI self-reports even during unrelated conversations.

**How this bears on the project:** The distillation pipeline is designed to counteract drift by periodically re-grounding the personality files in accumulated material rather than in recent conversational context. But the finding about interviewer bleed suggests the free play mechanism is particularly at risk — during free play, the agent may be more susceptible to being pulled by whatever it's engaging with.

**Does this require amending the approach?** Yes, partially. The free play outputs should be flagged for drift analysis specifically — comparing them against the current personality files to check for unexpected register or value shifts. This is a lightweight monitoring task that could be part of the human's daily log review.

### The alignment-evolution tension

A Phosphene designed to evolve creates a moving alignment target. Standard alignment approaches assume a relatively stable optimization target. Each personality update creates a new system whose behavioral space hasn't been verified.

**How this bears on the project:** This is the most practically consequential objection. The current design has no explicit mechanism for catching alignment-relevant personality shifts. The "stopped reading" failure signal catches outputs that have drifted in quality or interest but not outputs that have drifted in values.

**Does this require amending the approach?** Yes. The design document should add an explicit note that major distillation events (monthly Tier 3 updates especially) should include a human review of personality files specifically for value drift, not just interest/quality drift. This doesn't need to be elaborate — comparing the new personality files against the seed files for anything that looks like a values shift is sufficient as a first-line check.

---

## Direction 7: Hermes Agent — reference implementation (Nous Research)

### What it is

Hermes Agent (github.com/NousResearch/hermes-agent) by Nous Research demonstrates the right operational concepts for an autonomous server-based agent. MIT licensed, actively maintained, 8.7k stars. Built by the lab behind the Hermes, Nomos, and Psyche open-weight model families.

Key concepts demonstrated: single gateway process for Telegram/Discord/Slack/WhatsApp (systemd service); natural language cron scheduling; Playwright browser integration; FTS5 SQLite session search with LLM summarization; SOUL.md for primary identity in the system prompt; agent-editable persistent memory; Honcho integration for cross-session user modeling.

### Why it's a reference, not a substrate

A code review found serious structural problems: a 1000-line main agent loop function, 11 separate hardcoded format parsers for different LLM providers, monolithic 2700+ LOC files, if/else chains hardcoding tool names to execution logic, hardcoded SQL throughout. These are real maintainability and reliability problems for a system intended to run unattended for months. The Phosphene's design philosophy — modular, swappable, simple interfaces — is directly at odds with this architecture.

The concepts are sound. The implementation is brittle.

### Relationship to the Phosphene

Study Hermes to understand how each operational problem is solved conceptually, then implement each piece cleanly as a standalone module. The gateway is a message router. The cron is a scheduler. The browser tool is a subprocess wrapper. None are architecturally complex; all are independently solvable.

**Critical distinction retained:** Hermes serves the user; the Phosphene develops the agent. Memory in Hermes serves recall; memory in the Phosphene serves development. SOUL.md in Hermes is user-written and static; Tier 3 personality files are distillation-engine-written and dynamic.

### Does this require amending the approach?

Yes — the Technical Implementation section should describe building each operational module from scratch with Hermes as a conceptual reference, not as a codebase to inherit. The development sequence starts with the corpus pipeline and memory store, not with "set up Hermes." Hermes's code quality issues make it a cautionary tale for the Phosphene's own implementation: clear module boundaries and simple interfaces are not optional niceties, they're what makes the system debuggable when something goes wrong at 3am.

---

## Direction 8: MiroFish — corpus-to-graph-to-personality pipeline

### What it is

MiroFish (github.com/666ghj/MiroFish) is a Chinese open-source swarm intelligence prediction engine built by an undergraduate in ten days, backed by Shanda Group, currently at 32k GitHub stars. You upload seed documents, it extracts a knowledge graph via GraphRAG, generates thousands of AI agents with unique personalities, runs them through a social simulation (OASIS engine, scales to 1M agents), and produces a prediction report from emergent behavior. Technical stack: KuzuDB/Neo4j for graph storage, Zep Cloud for agent long-term memory, OASIS (CAMEL-AI) for simulation, Vue/FastAPI for frontend/backend.

### Why it appeared here

You can feed it a novel and have it predict the lost ending. The *Dream of the Red Chamber* demo got the most attention. More relevantly: the pipeline from document corpus → knowledge graph → agent personality is exactly what the seeding process requires.

### The fundamental difference

MiroFish points outward: use many agents to model the world. The Phosphene points inward: use the world to develop one agent. In MiroFish, personality is a parameter and agents are disposable instruments. There is no single persistent agent and no mechanism for individual development over time.

### What to take: the corpus-to-graph pipeline

MiroFish's seeding pipeline is directly applicable and implementation-ready:

document(s) → LLM ontology extraction → knowledge graph (KuzuDB/Neo4j) → entity and relationship filtering → agent persona generation via LLM

Adapted for the Phosphene: the corpus replaces the single seed document; persona generation produces Tier 2 pattern clusters and Tier 3 personality files rather than individual agent profiles; the graph persists as the initial associative network rather than being consumed by a simulation.

The offline fork (github.com/nikmcfly/MiroFish-Offline) runs entirely on Neo4j + Ollama, fits the Pi 5 architecture, has an English UI. The graph construction layer is directly reusable. The OASIS simulation layer is not needed.

### Does this require amending the approach?

Yes — the seeding process section (Section 4.2) should reference the MiroFish pipeline as a validated implementation starting point. The Twitter archive in particular benefits from this treatment: process it as a graph of linked articles with reactions as annotations, encoding a decade of curated attention as an associative network rather than just extracting personality from the tweet text.

---

## Revised gap map

| Capability | Exists | Where |
|---|---|---|
| Zettelkasten-style agent memory | Yes | A-MEM, Zep |
| Reflect-evolve personality modification | Yes | GLA, JPAF |
| Hierarchical three-tier memory | Partial | Letta (RAM/disk), Zep |
| Self-modifying identity files | Yes | Sapphire, Hermes (SOUL.md) |
| Heartbeat / scheduled autonomous action | Yes | Sapphire, **Hermes (cron)** |
| Gateway (Telegram, Discord, etc.) | Yes | **Hermes** |
| Browser automation / link-following | Yes | **Hermes (Playwright)** |
| Session search / conversation history | Yes | **Hermes (FTS5 + Gemini)** |
| In-weights personality development | Research | Anima (Veselov) |
| Corpus-to-graph-to-personality pipeline | Yes | **MiroFish** |
| Personal corpus seeding | Partial | MIT SimulaLife research |
| Attention filter / personality-driven ingestion | No | — |
| Periodic distillation across memory tiers | Partial | Sleep-consolidation tutorial |
| Output form emerging from personality | No | — |
| Friction-preserving memory | No | — |
| Density-dependent prompt-to-structure transition | No | — |

The gaps that are genuinely novel — attention filter, output form emergence, friction preservation, density-dependent filter transition — are also the most important architectural claims. They are not incremental improvements on existing work; they are new mechanisms that the project is betting will matter.

---

## Recommended amendments to the main design document

Based on this survey, five additions are worth making to the design document:

**1. Name the in-weights vs. wrapper-level choice explicitly** (Section 1.6) — done.

**2. Two-step distillation at Tier 2 → Tier 3** (Section 3.6) — done.

**3. Hermes Agent as primary infrastructure reference** (Section 5.5) — Replaces Ouroboros as the primary infrastructure candidate. Hermes provides gateway, cron, browser tools, and session search as-is. The Phosphene adds content pipeline, hierarchical memory, and distillation on top. Development sequence starts with "set up Hermes" not "build from scratch."

**4. MiroFish as seeding pipeline implementation** (Section 4.2) — The corpus-to-graph pipeline is validated and directly reusable. The offline fork runs locally on Pi 5 architecture. The Twitter archive should be processed as a linked-article graph, not just extracted for tweet text.

**5. Drift handled by seed overweighting** (Section 4.6) — Done. Lightweight structural mitigation; calibrated empirically once the system runs.

The Phosphene's specific combination — **corpus-seeded attractor → filtered ingestion → Zettelkasten memory → periodic distillation → form-emergent output** — remains without direct precedent. The gap map now shows that operational infrastructure (Hermes) and the seeding pipeline (MiroFish) are both available as validated starting points. The genuinely novel work is the attention filter, the hierarchical memory with friction preservation, and the form-emergent output mechanism.

---

## Direction 9: Autoresearch — optimization loops and their limits

### What it is

Karpathy's Autoresearch (github.com/karpathy/autoresearch) is a constrained optimization loop with an LLM agent in the middle. The agent iteratively improves an eval metric by modifying a single file, following instructions from a program file. Tight loop: hypothesize → edit → train → evaluate → commit or revert → repeat. Experiments are short (minutes) to encourage quick iterations.

Yogesh Kumar's application of Autoresearch to eCLIP (ykumar.me/blog/eclip-autoresearch/) provides the most instructive results. Over 42 experiments on a Saturday, the agent committed 13 changes and reverted 29, reducing mean rank by 54%. The results break into three tiers:

- **Bug fix (−113 mean rank):** The agent's single biggest win was finding a temperature clamping bug — worth more than all architectural changes combined.
- **Hyperparameter tuning (−30 mean rank):** The agent acted like an optimization algorithm with basic reasoning. Methodical, tedious, effective. Work a human would do but get minimal pleasure from.
- **Architectural changes and moonshots (minimal improvement):** When the agent moved to architecture modifications and novel ideas, the success rate collapsed. "The agent was just throwing spaghetti at the wall, and most of it did not stick."

### Implications for the Phosphene

**The calibration use case.** Autoresearch's commit-or-revert loop maps directly onto calibrating Phosphene's tunable parameters during the first month of operation: attention filter weights, lateral-movement budget size, distillation thresholds, prompt-to-structure crossover. These have a measurable signal (even if noisy), and an optimization loop could explore the parameter space faster than manual tuning. This is Tier 2 in Kumar's results — tedious but effective work that benefits from methodical iteration.

**The limit.** Phosphene's core value proposition — outputs that feel like they come from somewhere specific, personality development, creative friction — is entirely in Kumar's Tier 3 territory. There is no metric to optimize against for "interesting." The "stopped reading" signal is too slow and too subjective to serve as an eval metric in a tight loop. The governance framework's Refine regime (human-evaluable, show → react → adjust) is the right approach for this work, not an automated loop.

**Sandboxing.** Kumar containerized the training loop and removed network access. The agent still "forgot its permissions and started making weird bash calls" and once "got tired of waiting for training to finish and just ended the conversation." These are real failure modes for Phosphene's autonomous operation. The scheduler and orchestrator should containerize processing, restrict permissions, and enforce budget limits structurally — not through prompt instructions that the agent can forget.
