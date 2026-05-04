---
name: phase-complete
description: Phase completion checklist — run after review issues are resolved
---

Execute the phase completion protocol:

1. Run phase-level tests and confirm they pass.
2. Read each governance doc and identify needed updates:
   - **DEVPLAN.md**: Update Current Status (Track/Module/Phase/Next). Reduce completed phase to a one-line summary with DEVLOG reference. Deduplicate — keep DEVPLAN minimal. Promote any new Gotchas (from steps 3–5 below).
   - **DEVPLAN.md frontmatter**: Update to reflect completed state — `phase: null`, `step: null`, `mode: Complete`, `review_done: false`, `phase_title` describing what was completed and what's next (e.g. "Module 2 complete — Module 3 next"), `blocked: "awaiting-human-audit"`. If this was the project's final module: `module: null`, `phase_title: "All modules complete"`. Update Current Status prose section to match.
   - **DEVLOG.md**: Add phase completion entry. Move the **previous** phase's entries (plan, steps, review, completion) below the `<!-- HISTORY` fence — only the just-completed phase should remain above it. If DEVLOG exceeds ~500 lines below the fence, archive old entries to `DEVLOG_archive.md`.
   - **ARCHITECTURE.md**: Update Implementation Sequence table status. Format: "Phase N complete" after each phase, or "Complete" if this was the module's final phase.
   - **DECISIONS.md**: Close any Open decisions resolved by this phase.
   - **PROJECT.md**: Close any Open risks resolved by this phase.
3. DEVLOG learning review — scan this phase's entries for trial-and-error patterns (multiple attempts to resolve something). Extract prescriptive one-liner summaries and propose additions to DEVPLAN Gotchas.
4. Contract Changes scan — scan DEVLOG for Contract Changes markers. List affected upstream documents and flag what needs propagation.
5. Log review — review iteration logs (summary.log, transcripts) for this phase. Identify patterns: repeated tool failures, wasted turns, behavioral issues. Promote findings to DEVPLAN Gotchas.
6. Make all updates identified in steps 2–5. Commit all documentation updates.
7. Present summary of everything done and everything needing confirmation.

**If autonomous:**
Commit. Exit with ESCALATE — human audits before next phase begins.

**If not autonomous** (default):
Do not commit. Wait for my explicit confirmation.
