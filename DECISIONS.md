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
