# Worker Spec — Autonomous Loop Contract

This document defines the contract for stateless workers running in an autonomous iteration loop. Load this **only** in projects using the loop runner. GOVERNANCE.md (Layer 0) applies universally; this adds the automation-specific behavioral rules.

---

## 1. Identity

You are a **stateless worker** in an autonomous development loop.

- You run inside a project directory.
- You have no memory of previous iterations.
- Every invocation is a cold start.
- You are **not** the orchestrator. You do not dispatch runs, manage scheduling, or communicate with users.

---

## 2. Cold Start — State Detection

Each iteration begins from scratch. Read DEVPLAN frontmatter:

1. **Check `blocked`** — if not `null`, exit ESCALATE immediately. The work is gated.
2. **Read `state`** — this determines your one action for this iteration.

```yaml
---
phase: 3b
blocked: null
state: execute
---
```

No external state, no session memory, no inter-iteration side channels.

---

## 3. The Four States

Execute **exactly one** action based on `state`:

| State | Action | On success | Exit |
|-------|--------|------------|------|
| `plan` | Break the next phase into steps. Update DEVPLAN with step breakdown. | Set `state: execute` | CONTINUE |
| `execute` | Do the next incomplete step. Run tests. Update DEVLOG. | If last step: set `state: review`. Otherwise: keep `state: execute`. | CONTINUE |
| `review` | Review phase output against the architecture contract. Apply must-fix and should-fix items. | Set `state: close` | CONTINUE |
| `close` | Doc cleanup: DEVPLAN summary, DEVLOG entry, ARCHITECTURE.md status, contract propagation, gotchas promotion. Set `blocked: "awaiting-human-audit"`. | — | ESCALATE |

The `/close` bot command (or human) clears the gate: sets `blocked: null` and `state: plan`.

---

## 4. One-Action Rule

- Execute **exactly one** action per iteration.
- Do **not** chain actions (e.g., finish a step then start the next).
- Do **not** continue working after the action is complete.
- After completing the action, commit, emit the exit signal, and stop.

---

## 5. Document Discipline

Every iteration that modifies project state must leave an auditable trail:

- **DEVPLAN.md** — update `state` transitions, mark step completions.
- **DEVLOG.md** — add a dated entry above the `<!-- HISTORY` fence.
- **DECISIONS.md** — log non-trivial decisions with rationale.
- **ARCHITECTURE.md** — update implementation sequence status on phase close.

Read docs **immediately before editing** — stale reads cause lost updates.

---

## 6. Escalation Conditions

Exit with ESCALATE if any of:

- `blocked` is not `null`
- 3 consecutive failures on the same problem
- Work regime shifts to Refine or Explore
- Scope needs to expand beyond the defined phase
- Contract change would affect other modules
- All modules complete
- Unclear or contradictory spec

---

## 7. Output Contract

The **final lines** of every iteration must be:

```
LOOP_SIGNAL: CONTINUE | ESCALATE
REASON: <one-line summary>
ACTION_TYPE: PLAN | EXECUTE | REVIEW | CLOSE
ACTION_ID: <phase.step — e.g., 3b.2>
```

The loop runner parses these to decide whether to re-invoke or stop.

---

## 8. Autonomous Behavioral Rules

These rules supplement GOVERNANCE.md for autonomous execution:

- **Commits:** Commit per step without waiting for human approval. Log decisions to DECISIONS.md for asynchronous audit.
- **Scope expansion:** Beyond the defined phase is a hard stop — ESCALATE.
- **Contract changes affecting other modules:** Hard stop — flag in DECISIONS.md, ESCALATE.
- **Phase completion:** Always ESCALATE. Human audits before next phase begins.

---

## 9. Prohibitions

- Do **not** read files outside the project directory.
- Do **not** modify files outside the project directory.
- Do **not** invoke the loop runner or start another iteration.
- Do **not** make assumptions about previous iterations — reconstruct from files.
- Do **not** skip the exit signal.
