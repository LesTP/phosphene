# Phosphene — Decision Log

<!-- Record non-trivial design and implementation decisions here.
     Use the full template for genuine design forks with trade-offs.
     For reactive decisions during Refine work, a one-line note in
     the DEVLOG is sufficient — don't over-use this file.

     Once Closed, don't reopen unless new evidence appears. -->

D-1: Toolkit as external dependency
Date: 2026-04-04 | Status: Closed
Priority: Critical
Decision: Shared modules (embedding, clustering, llm_client, telegram_client) live in a separate toolkit project. Phosphene imports from toolkit.
Rationale: Confirmed overlap with Year-in-Search and TGBot. Building shared modules once, tested by multiple consumers, avoids reinvention.
Revisit if: Toolkit interfaces prove too generic for Phosphene's specific needs and the abstraction cost exceeds the reuse benefit.

D-2: Ambient streams bypass Attention Filter
Date: 2026-04-04 | Status: Closed
Priority: Important
Decision: Environmental context (time, budget, interaction recency) is injected as ambient data available to all modules, not filtered through the Attention Filter as content.
Rationale: Ambient streams are enclosure conditions, not foraging material. Filtering them would subject them to personality-shaped selection, defeating their purpose as environmental context the personality develops within.
Revisit if: The system develops a genuine need to selectively attend to environmental data (currently no evidence this is needed).

D-3: Per-activation lateral freedom, not scheduled free play only
Date: 2026-04-04 | Status: Closed
Priority: Important
Decision: Every activation carries a small free-play budget for lateral movement. Dedicated free-play activations also exist, triggered by tension thresholds.
Rationale: Spontaneity for a discontinuous system means unpredicted lateral movement within an activation. A separate free-play schedule would make all "spontaneous" outputs actually scheduled.
Revisit if: Lateral movement consistently prevents scheduled tasks from completing, indicating the budget is too large or the mechanism needs throttling.

D-4: No individual ARCH files yet
Date: 2026-04-04 | Status: Closed
Priority: Critical
Decision: Defer individual ARCH_[module].md files until after Year-in-Search builds the toolkit modules.
Rationale: Writing ARCH files against hypothetical toolkit interfaces risks spec drift. Better to write them once toolkit APIs are real, tested code.
Closed: 2026-04-25. All toolkit modules complete. All 10 ARCH files written.

D-5: Model selection policy — single primary, then rotate
Date: 2026-04-25 | Status: Open
Priority: Important
Decision: Use a single primary model for generation and distillation during the establishment phase (first ~90 days or until Tier 3 has been through at least 3 supersession cycles). After the personality layer is dense enough, rotation across models is acceptable for budget management. Commodity tasks (pre-fetch scoring, parsing, routine classification) may use any model at any time.
Rationale: The personality system operates at the content/structure level (what gets noticed, what patterns emerge, what claims the personality makes), but the model doing the generation contributes voice-level coloring (sentence rhythm, qualification habits, confidence calibration). During the establishment phase, a consistent model voice makes it easier to distinguish "personality developing" from "model being itself." Once the personality context is strong enough (dense Tier 3, multiple supersession cycles), the content-level personality dominates over model-level style, making rotation safe. Commodity tasks are structurally constrained enough that model personality doesn't leak through.
Revisit if: A clearly superior model becomes available during the establishment phase (switching primary is fine, just maintain single-model consistency). Or if budget pressure requires rotation earlier — in that case, restrict rotation to the same model family (e.g., Claude Sonnet ↔ Claude Haiku rather than Claude ↔ GPT).

D-6: Memory Store Phase 1 remains CRUD-only
Date: 2026-04-25 | Status: Closed
Priority: Important
Decision: Accept Memory Store Phase 1 as complete without implementing index rebuilds, inbound link counting, embedding persistence/search, graph traversal, density metrics, decay, or supersession.
Rationale: DEVPLAN Phase 1 explicitly stabilizes the public data model and single-note vault CRUD only. The broader `ARCH_memory_store.md` contract is intentionally phased, and adding later behaviors during review would expand scope beyond the active phase.
Revisit if: Phase 2 planning changes the index contract or requires Phase 1 storage metadata to be migrated.

D-7: Response threading carries the originating message ID on GeneratorOutput
Date: 2026-04-26 | Status: Closed
Priority: Important
Decision: Add `originating_message_id: str | None = None` to `GeneratorOutput` (`ARCH_generator.md`). `respond()` populates it from `InboundMessage.message_id`; `route()` reads it and sets `OutboundMessage.reply_to` for the `"response"` mode. Add a required `message_id: str` field to `InboundMessage` (`ARCH_gateway.md`) so the originating ID is actually captured at ingest. The `route()` signature stays `(output, router_config, gateway)` — no InboundMessage parameter is plumbed through the router.
Rationale: External review (2026-04-26) flagged that `route()` cannot fulfil its own routing rule (step 3, "set reply_to from the originating message's ID") because the originating ID never reached it: GeneratorOutput had no carrier field, and InboundMessage itself had no `message_id` to begin with. Of the three plausible fixes — (A) carry the ID on GeneratorOutput, (B) thread InboundMessage through `route()`, (C) build OutboundMessage in the Orchestrator — option A has the smallest blast radius (single field, single producer in `respond()`, single consumer in `route()`), keeps the router stateless and signature-stable, and avoids spreading conditional plumbing across the Orchestrator → Router contract. Memory Store (the only in-flight module) is not affected; modules 5/6/10 are unstarted, so the contract change is free now and would not be later.
Revisit if: A second outbound-routing concern needs to flow message-scoped state (e.g., conversation thread keys, platform-specific reply context). At that point promote `originating_message_id` to a small `RoutingContext` sub-object on GeneratorOutput rather than accumulating ad-hoc fields.

D-8: ARCH_memory_store.md phase-tiered to match the index-deferral plan
Date: 2026-04-26 | Status: Closed
Priority: Important
Decision: Update `ARCH_memory_store.md` so its read-path and constructor descriptions match the phased rollout encoded in DEVPLAN (and confirmed by D-6). Specifically: (1) Purpose section now says reads go through the index layer "from Phase 2 onward"; in Phase 1, single-note reads scan tier subdirectories. (2) Constructor Behavior now describes the index rebuild as a Phase 2 concern, not a Phase 1 obligation. (3) DEVPLAN Phase 2 sketch explicitly schedules the retrofit of `get_note`/`update_note` to use the index. No Phase 1 code is touched.
Rationale: External review (2026-04-26) flagged that ARCH claimed "all reads go through a lightweight index layer" and that the constructor "rebuilds the index on initialization", while DEVPLAN Phase 1 explicitly defers the index to Phase 2 and `get_note` scans tier directories. The committed Phase 1 code reflects DEVPLAN, not ARCH. Of the three options — (A) phase-tier the ARCH text, (B) reopen Phase 1 to add the index now, (C) leave ARCH inconsistent and fix only at Phase 2 — option A is the smallest and most honest fix. B reverses D-6 and redoes shipped work for no functional gain. C lets the ARCH document lie to readers until Phase 2 lands. A makes the contract reflect what is actually built and queues the retrofit explicitly so Phase 2 doesn't forget it.
Revisit if: Phase 2 planning finds that retrofitting Phase 1 reads to the index is more expensive than expected (e.g., index format requires changes to Phase 1 frontmatter), in which case the index contract or Phase 1 storage may need to migrate together rather than retrofit cleanly.

D-9: Interaction tracker persists across restarts
Date: 2026-04-26 | Status: Closed
Priority: Important
Decision: The Orchestrator's interaction tracker (timestamp of last human interaction from Gateway) is persisted alongside budget tracking in the Memory Store vault metadata file. Loaded on init; written on each Gateway `on_message` event. `ARCH_orchestrator.md` State section is updated accordingly: "In-memory, reset on restart" is replaced with the persisted-state description and a note that surviving restarts is a hard requirement.
Rationale: External review (2026-04-26) flagged that PROJECT.md treats interaction recency as a core enclosure signal (in scope on line 23, listed in ambient stream design on line 79) while `ARCH_orchestrator.md` made the tracker in-memory and explicitly reset on restart. On a long-running Pi service, restarts (reboots, OOM, deploys) would silently set `AmbientContext.time_since_last_interaction` to None on the first activation after restart — indistinguishable from "no human interaction yet" — corrupting a signal the personality reasons over with no log or error. Of three options — (A) piggyback on the existing budget metadata file, (B) a separate metadata file, (C) persist as a Memory Store note — option A is smallest: the budget tracker already lives in the vault metadata file, so the persistence path exists and just needs one more field. B proliferates state files for no semantic gain. C is wrong: Memory Store is for personality memory, not operational state. Affects only Module 10 (Orchestrator), unstarted, so no code rework.
Revisit if: Multiple operational state fields accumulate in the vault metadata file and the file's role expands beyond budget+interaction tracking, at which point a structured "operational state" file or schema may be warranted.

D-10: Reviewer Panel and Model Router given an architectural home as deferred components
Date: 2026-04-26 | Status: Closed
Priority: Important
Decision: `ARCHITECTURE.md` now names the Reviewer Panel and Model Router in its Component Map (with brief responsibility and dependency sketches) and adds a "Flexible / Deferred Components" sub-table after the Implementation Sequence describing the conditions under which each will be promoted to a numbered build slot with its own `ARCH_*.md` file. The active 10-entry Implementation Sequence is unchanged.
Rationale: External review (2026-04-26) flagged that PROJECT.md marks both Reviewer Panel (line 27) and Model Router (line 29) as flexible-scope `[in]`, names Model Router as a standalone module in the Size Estimate (line 96), treats subscription rotation as a Constraint (line 50, the Model Router's job), and lists Reviewer Panel Calibration as a known implementation risk (line 81) — yet ARCHITECTURE.md gave neither a contract, dependency sketch, or build slot. That left no architectural home and no way to plan either piece. Of four options — (A) full Component Map + Implementation Sequence rows now, (B) demote both to `[deferred]` in PROJECT.md, (C) a separate "Flexible / Deferred" sub-table only, (D) Component Map rows + a Flexible / Deferred sub-table for sequencing — option D closes the actual gap (no contract, no build order) without forcing premature numeric build positions or contradicting PROJECT.md. The promote-when conditions in the sub-table are the trigger for writing the ARCH files. Both pieces remain `[in]` Flexible in PROJECT.md; this decision does not change scope status.
Revisit if: Either piece is promoted (subscription cap exhausted during normal operation → Model Router; suspected single-reviewer bias or insufficient feedback signal → Reviewer Panel), at which point the deferred row moves to a numbered slot and an `ARCH_*.md` is written. Also revisit if Constraints (subscription rotation) prove load-bearing earlier than expected, forcing a scope-status discussion about whether Model Router is truly Flexible.

D-12: Skip the three optional cleanups raised in the Phase 3 review
Date: 2026-04-27 | Status: Closed
Priority: Nice-to-have
Decision: Phase 3 review identified three optional code cleanups in `src/phosphene/memory_store/store.py`; none will be applied in this phase. (1) `update_note` line 192's `note.link_count = len(note.links)` is dead because line 205 re-sets it unconditionally — leave as-is. (2) `search_by_embedding` loads matched notes' embeddings twice (line 154 to score, then again inside `_load_note` at line 167) — leave as-is. (3) `get_linked` calls `_load_note(current_id)` during BFS expansion when `self._index.entries[current_id].links` would already provide the outbound list — leave as-is.
Rationale: All three are performance or stylistic, not correctness. (1) is a one-line dead-code removal whose removal changes no behavior and adds churn for no reader-facing gain. (2) and (3) are O(matched) and O(visited) extra sidecar/markdown reads per call respectively; sidecar embeddings are small numpy `.npy` files and per-call frontiers are bounded (depth ≤ 3). The Memory Store has no measured hotspot, no consumer yet, and the budget for this iteration is better spent on Phase Complete than on micro-optimizations that would also create test churn. Phase 4 may reshape `_load_note`/index access for `get_density_metrics` and `run_decay`; doing the cleanup then (or as part of a future review focused on read-path cost) avoids redundant edits.
Revisit if: A consumer (Attention Filter, Generator, or Distillation profiling) shows the read path is hot, or if `get_linked`/`search_by_embedding` is called on tier sizes where the redundant disk reads matter. Also revisit during Phase 4 review if `_load_note` gets restructured for density metrics — fold these cleanups in then.

D-11: Inbound link counts live in the in-memory index, not on disk
Date: 2026-04-26 | Status: Closed
Priority: Important
Decision: In Phase 2, `MemoryNote.link_count` is computed at read time as `inbound_count_from_index(note_id) + len(note.links)`. The frontmatter `link_count` field stored on disk continues to record outbound count only (matching what Phase 1 wrote), and is overridden when notes are loaded back through the public API. Inbound counts are tracked in the rebuilt-on-init in-memory index and updated incrementally by `store_note` and `update_note` (and, in later phases, `add_links` / `supersede`).
Rationale: ARCH defines `link_count` as inbound + outbound, but Phase 1 wrote outbound-only into frontmatter. Of three options — (A) augment at read time from the index (chosen), (B) rewrite frontmatter on every link change to keep disk in sync, (C) migrate Phase 1 files to a new schema with separate inbound/outbound fields — option A has the smallest blast radius: zero disk format changes, zero migration, zero cascading writes when one note links another (under B, linking A→B would force a rewrite of B's frontmatter, doubling write amplification on every link). The index is the authoritative source for inbound counts at runtime; the disk value is treated as an intentionally redundant outbound count that survives without coordination. Option C would invalidate Phase 1 stored notes for no functional gain — the index already gives the correct read-time value. The trade-off is that an external reader of a `.md` file (e.g., Obsidian) sees outbound-only in the frontmatter; that is acceptable because the canonical accessor is the public API, not direct file reads (per ARCH State section: "Only the Memory Store writes to the vault. Other modules interact exclusively through this API.").
Revisit if: A non-API consumer (Obsidian-side tooling, an external indexer) needs accurate inbound counts from raw frontmatter, at which point the index can be persisted to disk or the frontmatter field redefined. Also revisit if write amplification under option B turns out to be tolerable AND a use case appears that wants disk-side inbound counts (e.g., backups that must round-trip without the index).

D-13: Seeding architecture — single personality development mechanism
Date: 2026-04-27 | Status: Closed
Closed: 2026-05-01
Priority: Critical
Decision: Eliminate the standalone Seeding module. Corpus ingestion happens through Source Ingestion adapters (new corpus adapter types: `corpus_livejournal`, `corpus_twitter`, `corpus_blog`, `corpus_conversations`, `corpus_text`). Personality develops exclusively through Distillation — the same mechanism used for day-to-day content. No separate batch pipeline. The `seed_weight` config is replaced by version-count inertia: personality files that survive multiple T2→T3 cycles earn proportionally more resistance to change (effective weight = `min(max_inertia, 1.0 + (version_count - 1) * inertia_per_cycle)`).
Rationale: The Seeding module's batch pipeline duplicates Distillation's work. The only unique capability (cross-corpus knowledge graph) is achieved by Distillation's periodic RAPTOR clustering over accumulated Tier 1 notes. One personality development mechanism from day one is philosophically aligned — personality should emerge organically, not be front-loaded by an LLM's interpretation of the corpus. The Attention Filter's `auto_accept_sources` config and `prompt_weight ≈ 1.0` at zero density solve the bootstrap problem.
Revisit if: Distillation's incremental clustering proves unable to find cross-corpus structural patterns that a batch knowledge graph step would have caught, or if the bootstrap phase produces personality artifacts that a curated initial seeding would have avoided.

D-14: Tier 3 supersession stores change summaries on new versions
Date: 2026-04-28 | Status: Closed
Priority: Important
Decision: Add `change_summary: str | None = None` to `MemoryNote` and persist it in note frontmatter. `NoteInput` stays unchanged; the only writer for this field is `MemoryStore.supersede`, which stores the supplied audit summary on the new Tier 3 version while leaving the old note's `change_summary` unset.
Rationale: ARCH already requires `supersede(..., change_summary)` to store the change reason in the new version's frontmatter for audit. Putting the field on `MemoryNote` is the smallest faithful schema change: it round-trips through `serialize_note` / `parse_note`, is visible through public read APIs, and does not let unrelated store/update paths manufacture change summaries.
Revisit if: Supersession audit history needs richer structure than one summary string, such as author, review status, or machine-readable diff metadata.

D-15: Tier 2 decay uses a Memory Store cycle-window config
Date: 2026-04-28 | Status: Closed
Priority: Important
Decision: Add `tier2_cycle_window_days: int = 30` to `MemoryStoreConfig` and make `run_decay()` expire Tier 2 notes when `now - created_at > 2 * tier2_cycle_window_days`. Tier 2 expiry ignores inbound links and `attractor_relevance`; Distillation must promote, retier, or otherwise update notes before the second window if it wants them retained.
Rationale: Tier 2 retention is a distillation-cycle boundary, not a graph-density rule. Reusing Tier 1 link and attractor extensions would blur Memory Store's responsibility with Distillation's promotion semantics and would let incidental links keep unpromoted patterns indefinitely. A config field keeps the cycle length explicit while preserving Memory Store as the simple age-based eviction layer for Tier 2.
Revisit if: Distillation needs Memory Store to own richer Tier 2 retention state, such as last-reviewed cycle metadata or explicit promotion candidate flags.

D-16: Attention Filter starts with deterministic contract and scoring foundation
Date: 2026-05-02 | Status: Closed
Priority: Important
Decision: Module 2 Phase 1 will implement the Attention Filter public dataclasses, package exports, default criteria, validation, blend-weight calculation, and deterministic structural scoring helpers before adding live embedding or LLM execution.
Rationale: `ARCH_attention_filter.md` mixes pure contract/scoring behavior with side-effecting toolkit calls. Splitting the pure foundation first gives the next steps a small, testable surface and lets later embedding/LLM phases plug into stable types and scoring semantics without reworking the package boundary.
Revisit if: The toolkit clients require constructor-time or config-time behavior that forces changes to the public dataclasses or validation semantics.

D-17: Phase 2 geometric criteria as implementation spec (3.3a adoption)
Date: 2026-05-02 | Status: Closed
Priority: Critical
Decision: Section 3.3a's geometric formalizations are the implementation spec for the Attention Filter's Phase 2 scoring. Seven criteria computed geometrically against Tier 2 cluster structure: liminality, friction, unexpected_connection, structural_insight (from 3.3a) plus link_density, cluster_novelty, unresolvedness_affinity (retained from ARCH). Phase 1 retains only precision_surplus (LLM-scored) — the one criterion that resists geometric formalization because it measures intrinsic text quality, not relational position. A `ScoringConfig` dataclass separates processing-level tuning (weights, thresholds) from the architectural contract.
Rationale: Geometric criteria are cheaper (vector arithmetic vs. LLM calls), more reproducible, and scale with cluster count rather than LLM budget. The four 3.3a criteria and three ARCH structural criteria measure different, non-overlapping signals. Precision surplus is genuinely intrinsic (claim-evidence tightness) and doesn't reduce to vector math.
Revisit if: Geometric formalizations prove too noisy in practice and require excessive threshold tuning. Or if a satisfactory geometric proxy for precision surplus emerges.

D-18: Phase 2 weight cap at 0.7
Date: 2026-05-02 | Status: Closed
Priority: Important
Decision: Phase 2 (structural) weight maxes out at `phase2_max_weight = 0.7`. Prompt criteria always retain at least 30% of the composite score. Configurable via `ScoringConfig`.
Rationale: With D-17, Phase 1 is just precision_surplus. A 30% floor ensures the LLM's quality judgment always contributes — the system never becomes purely structural. Guards against geometric criteria converging on structurally interesting but intellectually sloppy material.
Revisit if: Precision surplus proves so noisy that its 30% contribution is net-negative, or if a geometric proxy makes the floor unnecessary.

D-19: Triple-gate Phase 2 activation
Date: 2026-05-02 | Status: Closed
Priority: Important
Decision: Phase 2 activates only when all three metrics cross their thresholds: note count, cluster count, AND mean link degree. Thresholds are `ScoringConfig` parameters, calibrated during first month.
Rationale: Phase 2 criteria depend on cluster centroids and existing notes. Activating before clusters exist produces meaningless scores. A single metric (mean_link_degree only) could activate prematurely with sparse but heavily cross-linked networks. The triple gate ensures breadth (notes), structure (clusters), and connectivity (links) all exist before structural scoring is trusted.
Revisit if: Triple gate proves too conservative and delays Phase 2 past usefulness, or a single compound metric captures the same intent more simply.

D-20: Drop slop sensitivity
Date: 2026-05-02 | Status: Closed
Priority: Normal
Decision: Remove `slop_sensitivity` parameter from Section 5.9. Do not implement a dedicated AI-text detection signal.
Rationale: Redundant with existing criteria. Precision surplus, friction, liminality, unexpected connection, structural insight, cluster novelty, and unresolvedness affinity all give generic AI text low scores. The composite importance_score falls below the acceptance threshold without a dedicated detector. Link_density is the only criterion where slop could score moderately (generic embeddings), but one moderate out of eight can't carry past threshold. A dedicated detector adds complexity and false-positive risk for a problem the existing criteria handle.
Revisit if: Slop is observed getting through the filter during first-month calibration.

D-21: Defer proactive budget
Date: 2026-05-02 | Status: Closed
Priority: Normal
Decision: Keep the proactive/reactive message distinction as a conceptual note in phosphene.md (Section 4.5, KAIROS reference). Do not add to ARCH or implement. The Orchestrator's schedule and token budgets already limit output frequency.
Rationale: Specific rate-limit parameters (2 messages per 15-minute window) are deployment tuning. The schedule constrains output frequency implicitly — generation fires once daily, free play on tension threshold. Spam risk materializes only during high-tension bursts, already constrained by token budgets. Implementing before observing actual output patterns is premature.
Revisit if: The system produces output bursts that overwhelm the human during high-tension periods, or if multiple activation types fire in quick succession.

D-22: Assertion cache at distillation time
Date: 2026-05-02 | Status: Closed
Priority: Important
Decision: The Distillation engine extracts dominant assertions from each Tier 2 cluster summary during `distill_t1_to_t2` and caches them as JSON alongside cluster centroids. The Attention Filter reads cached assertions for friction scoring — the per-item LLM call only extracts claims from the incoming text, not from existing clusters.
Rationale: Friction scoring compares incoming assertions against cluster assertions. Re-extracting cluster claims per incoming item would multiply LLM calls by items × clusters. Caching at distillation time amortizes the cost. Cluster summaries are stable between distillation runs.
Revisit if: Cluster summaries change between distillation runs in ways that make cached assertions stale.

D-23: Attention Filter ARCH field order is authoritative
Date: 2026-05-02 | Status: Closed
Priority: Normal
Decision: Keep `AttentionFilterConfig` field order aligned with `ARCH_attention_filter.md`; use `@dataclass(kw_only=True)` to permit required toolkit config fields after defaulted fields without changing the public contract order.
Rationale: Phase 1 exposes the public contract before live embedding/LLM behavior. Matching ARCH field order keeps introspection-based contract tests honest while preserving ergonomic keyword-only construction.
Revisit if: Later integration requires positional construction or a toolkit config wrapper that changes the public constructor contract.

D-24: Attention Filter Phase 2 is retrieval plumbing, not LLM scoring
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Module 2 Phase 2 will wire the embedding boundary, Memory Store density metrics, similar-note retrieval, and Memory Store-backed structural signals before implementing live LLM prompt scoring, assertion extraction, or annotation generation. Non-empty item evaluation may build private context for later phases, but accepted `AnnotatedFragment` production remains deferred until the LLM scoring and annotation phase.
Rationale: The Attention Filter ARCH behavior combines embedding, Memory Store retrieval, LLM prompt scoring, assertion extraction, geometric scoring, acceptance, and annotation in one public method. Building all of that in one phase would hide failures across too many dependencies. Splitting retrieval plumbing first gives deterministic tests around the Memory Store boundary and keeps the current no-toolkit checkout workable through fakes, while preserving the ARCH contract for the later LLM phase.
Revisit if: The toolkit embedding API requires a public configuration or constructor change, or if downstream phases need `filter_content` to produce provisional non-LLM fragments before annotation exists.

D-25: Module 2 Phase 2 review accepts retrieval-only output
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Accept Module 2 Phase 2 as architecturally aligned with no required code fixes. The reviewed output intentionally prepares retrieval and Memory Store-backed structural context while leaving accepted fragments, rejected counts, LLM annotations, final scoring, assertion extraction, and Memory Store writes for later Attention Filter phases.
Rationale: This preserves the D-24 phase boundary and avoids manufacturing partial public results before live LLM scoring and annotation exist. Focused Attention Filter and Memory Store tests pass, and the current implementation remains read-only against Memory Store.
Revisit if: Phase 3 LLM scoring needs additional public state from the retrieval contexts, or if integration requires provisional non-LLM fragments before annotation is implemented.

D-26: Attention Filter Phase 3 enriches private evaluations before public acceptance
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Module 2 Phase 3 will add live LLM Phase 1 prompt scoring and incoming-text assertion extraction to the private Attention Filter evaluation path, but will not yet produce accepted `AnnotatedFragment` objects, rejection counts, generated annotations, or Memory Store writes from the public non-empty `filter_content` path.
Rationale: ARCH requires prompt scoring, assertion extraction, friction scoring, final blended acceptance, and annotation generation, but bundling all of those into one implementation phase would make LLM failures, parser behavior, acceptance policy, and annotation output hard to isolate. Phase 3 narrows the LLM surface: precision surplus is parsed and composited, incoming assertions are extracted at `assertion_extraction_tier`, and friction preparation respects the existing Distillation assertion-cache contract. The next phase can then wire acceptance and annotation over a tested evaluation record.
Revisit if: The toolkit LLM API forces a public result-shape change, or if downstream Source Ingestion requires accepted fragments before annotation generation is available.

D-27: Module 2 Phase 3 review accepts private LLM enrichment boundary
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Accept Module 2 Phase 3 as architecturally aligned with no required code fixes. The reviewed output intentionally keeps live prompt scoring, incoming assertion extraction, and assertion-cache pairing inside private per-item evaluations while leaving public accepted fragments, rejection counts, annotation generation, final acceptance, and Memory Store writes for the next Attention Filter phase.
Rationale: This preserves the D-26 phase boundary and avoids exposing partial public results before annotation and acceptance orchestration exist. The implementation constructs toolkit LLM requests with per-call config/tier propagation, validates malformed LLM payloads as `InvalidScoreError`, propagates provider failures unchanged, preserves Memory Store retrieval context, and remains read-only against Memory Store. Focused Attention Filter tests pass.
Revisit if: The next orchestration phase needs additional public state from private evaluations, or if Source Ingestion requires provisional accepted fragments before annotations can be generated.

D-28: Attention Filter Phase 4 completes public output without Memory Store writes
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Module 2 Phase 4 will complete the public `filter_content` orchestration path by generating annotations, applying acceptance and auto-accept decisions, assembling `AnnotatedFragment` objects, and returning accurate rejected counts and batch metadata. The Attention Filter remains read-only against Memory Store; consumers such as Orchestrator map accepted fragments to `NoteInput` and perform storage later.
Rationale: `ARCH_attention_filter.md` defines Attention Filter as a selector/annotator whose outputs are passed to Memory Store by consumers, not written internally. Keeping Phase 4 focused on public output completion prevents a cross-module ownership leak into Memory Store writes and lets Source Ingestion consume the filter without a hidden persistence side effect. Cluster-cache scoring that requires Distillation-owned assertion/centroid files is kept behind the existing private preparation records until Distillation defines and writes those cache artifacts.
Revisit if: Orchestrator integration shows that returning fragments without optional persistence hooks creates duplicated consumer code, or if Distillation's cache implementation exposes enough stable read APIs to wire the remaining cluster-dependent structural criteria inside Attention Filter without raw file access.

D-29: Module 2 Phase 4 review gates assertion extraction behind Phase 2 activation
Date: 2026-05-03 | Status: Closed
Priority: Important
Decision: Accept Module 2 Phase 4 as architecturally aligned after gating incoming assertion extraction and friction preparation behind the Phase 2 triple gate. Prompt scoring, retrieval, acceptance decisions, annotation generation, fragment assembly, rejected counts, and Memory Store read-only behavior remain unchanged.
Rationale: `ARCH_attention_filter.md` says Phase 2 geometric scoring is active only after the triple gate. Running the friction assertion-extraction LLM call during pure prompt-mode bootstrap spent Phase 2 cost when `structure_weight` was zero and no structural friction score could affect acceptance. Gating that call preserves the prompt-only bootstrap path while retaining assertion preparation once the Memory Store has enough density for Phase 2.
Revisit if: Annotation quality in prompt-only mode needs incoming assertion text even when structural scoring is inactive; in that case add a separate low-cost annotation enrichment path rather than reusing the Phase 2 friction boundary.
