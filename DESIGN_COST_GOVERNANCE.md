# Design: Cost & Data Governance

**Date:** 2026-05-15
**Context:** After 18 documented issues across Phosphene MVP development, resulting in ~$60+ untracked API spend, data loss from unprotected decay, and wasted compute from unbounded retry loops. This document catalogs all incidents, identifies failure patterns, and proposes governance rules enforceable through the cost accountant (toolkit) and a data protection gate (governance policy).
**Scope:** Cross-project. Rules apply to all projects using the governance framework.
**Status:** Design discussion. Pending refinement and GOVERNANCE.md integration.

---

## Part 1: Issue Catalog

### A. Unnecessary Spend

| # | Issue | What Happened | Cost |
|---|-------|--------------|------|
| 1 | `--seed-only` vs `--seed-direct` | `--seed-only` ran LLM attention filter on every note. `--seed-direct` (embedding only) was free. Wrong mode chosen. | ~$35 |
| 5 | Sonnet 4.5 refuses bilingual content | `stop_reason: refusal` on bilingual LJ content. Repeated attempts before switching to Sonnet 4. | Wasted API calls |
| 8 | Cluster summary overflow | 300+ note clusters sent as single prompt → exceeded context window. Failed, retried, failed again. | Wasted API calls |
| 11 | LLM ID hallucination | LLM used short numeric IDs instead of long slugs. 3/9 reflection batches produced 0 usable insights. | ~$0.30 wasted |
| 14 | 175-min retry against spending cap | Ingestion retried "usage limits reached" error for 3 hours. Every retry got same error, 0 work done. | Wasted 3 hours |

### B. Data Loss / No Backup

| # | Issue | What Happened | Cost |
|---|-------|--------------|------|
| 9 | Note ID collision | Same title+timestamp → same filename → 62% of T1 notes silently overwritten during seeding. | Time to reseed |
| 16 | Decay destroyed 86% of T1 | Historical `created_at` timestamps (2002-2026) instantly exceeded retention window. No backup taken. First decay run pruned 3,335 of 3,856 notes. | ~$5-10 re-distillation value at risk (T2 survived) |
| 17 | `--once` runs decay as side effect | "Testing generation" via `run.py --once` also triggered decay. The destructive side effect wasn't anticipated. | Triggered issue #16 |

### C. Expected Experimentation (Normal)

| # | Issue | What Happened | Cost |
|---|-------|--------------|------|
| 2 | Monolingual embedding model | `all-MiniLM-L6-v2` clustered by language, not topic. Switched to multilingual. | Time (free) |
| 3 | HDBSCAN on raw 384-dim | One mega-cluster, 76% noise. Needed UMAP reduction first. | Time (free) |
| 4 | Coherence threshold too strict | 0.4 rejected most clusters with multilingual model. Lowered to 0.25. | Time (free) |

### D. Integration / Design Gaps

| # | Issue | What Happened | Cost |
|---|-------|--------------|------|
| 6 | RAPTOR summary propagation bug | Normalizer read from wrong path — T2 got raw text instead of LLM summaries. | Time |
| 10 | T2→T2 all-to-all cross-links | 225-node complete graph at bootstrap scale. Fixed with similarity filtering. | Time |
| 12 | T2→T3 context overflow | 251 T2 notes = ~202K tokens, exceeding context budget. Worker escalated correctly. | None (caught) |
| 13 | No T3 bootstrap path | Evolution only modifies existing T3 files — empty vault had nothing to modify. | None (caught) |

### E. Hidden Side Effects / Stale State

| # | Issue | What Happened | Cost |
|---|-------|--------------|------|
| 15 | Datetime naive vs aware | `datetime.now()` compared to UTC-aware timestamps → generation crashed. | None (bug fix) |
| 18 | 14 T3 files instead of 7 | Lean script read raw files instead of `get_personality_context()`. Superseded files included. | Suboptimal output |
| 7 | API rate limit retries | 429 errors → 60s backoff → unbounded retry loop. Not budget-capped. | Wasted time |

---

## Part 2: Failure Pattern Analysis

| Pattern | Issues | Frequency | Severity | Governance Response |
|---------|--------|-----------|----------|-------------------|
| **Unnecessary spend** | 1, 5, 8, 11, 14 | High | Medium-High | Cost accountant (structural enforcement) |
| **Data loss without backup** | 9, 16, 17 | Low | Critical | Data protection gate (procedural + structural) |
| **Expected experimentation** | 2, 3, 4 | Expected | Low | None — this is normal development. Tuning pipeline automates it. |
| **Integration gaps at bootstrap** | 6, 10, 12, 13 | One-time | Medium | Already fixed. Not recurring. |
| **Hidden side effects** | 7, 15, 17, 18 | Medium | Medium | Side-effect awareness for multi-task tools |
| **Unbounded retries** | 7, 14 | Medium | Medium | Cost accountant abort on hard errors |

Categories C and D don't need governance changes — they're normal development and one-time fixes respectively. Categories A, B, E need structural protection.

---

## Part 3: Two Governance Mechanisms

### Mechanism 1: Cost Gate (addresses A, F — unnecessary spend, unbounded retries)

**What:** The cost accountant module in `toolkit/cost_accountant/`. All LLM API calls must pass through it. Structural enforcement — you literally cannot call the API without going through the gate.

**Triggers:** Any operation that makes external API calls (LLM, embedding API if paid, external services).

**Enforcement:**
- Pre-call: estimate cost, check against budget
- Post-call: record actual cost to ledger
- On rate limit or spending cap error: abort immediately (no retry)
- On budget exceeded: raise `BudgetExceededError` (no fallthrough)
- Session-level: cumulative tracking, human-readable report

**Implementation:** See `toolkit/DESIGN_COST_ACCOUNTANT.md` for full API design.

**Friction level:** Zero for the developer. The accountant is transparent when within budget — calls pass through normally. It only intervenes when something is wrong (over budget, rate limit, spending cap). Cost estimates and approval happen once per operation (batch level), not per call.

### Mechanism 2: Data Protection Gate (addresses B, E — data loss, side effects)

**What:** A governance policy + lightweight code enforcement. Operations that could destroy or modify valuable data require protection before proceeding.

**Triggers:** The gate fires when BOTH conditions are true:
1. The operation is **destructive** (modifies or deletes existing data in batch)
2. The data is **valuable** (costs money or significant time to recreate)

**Data value classification:**

| Category | Examples | Replaceable? | Gate Required? |
|----------|----------|-------------|---------------|
| **Irreplaceable** | Original corpus exports, human-authored content | No | Always |
| **Costly to recreate** | T2 clusters (~$5-10), T3 personality files (~$2-5), generation outputs | Yes, at cost | Yes |
| **Free to recreate** | T1 from `--seed-direct`, embeddings, index cache | Yes, free | No |
| **Ephemeral** | Logs, temp files | Disposable | No |

**Operation classification:**

| Operation Type | Examples | Gate Required? |
|---------------|----------|---------------|
| **Additive** | `store_note()`, file creation | No |
| **Modifying** | `update_note()`, `supersede()` | Only if data is costly/irreplaceable |
| **Destructive batch** | `run_decay()`, vault clear, `--once` with decay | Yes |
| **Multi-task** | `run.py --once`, cron loop | Requires side-effect listing |

**Protection protocol (when gate fires):**

1. **Snapshot first** — `cp -r vault vault_backup_$(date +%Y%m%d%H%M)` before any destructive batch operation on costly data. Takes seconds, prevents hours of rework.
2. **Dry-run or sample test** — if the operation supports `--dry-run`, run it first. If it affects 100+ items, test on 5-10 first.
3. **List side effects** — for multi-task tools, explicitly enumerate all tasks that will execute. Identify destructive ones. Disable them if this is a test run.

**Friction level:** Low. The gate only fires for destructive operations on valuable data. Most development work (writing code, running tests, additive operations) never triggers it. When it does trigger, the actions are fast (snapshot takes seconds, dry-run takes seconds).

---

## Part 4: What Goes Where

### GOVERNANCE.md additions

```markdown
### Costly Operations

Operations that spend money require:
1. A cost estimate before execution (stated explicitly in DEVLOG or console)
2. A budget cap enforced in code (via toolkit/cost_accountant)
3. Explicit human approval for operations estimated >$1
4. Immediate abort on spending cap or hard rate limit errors (no retry loops)

### Valuable Data Protection

Before any destructive batch operation on data that costs money or significant
time to recreate:
1. Snapshot the data (cp -r vault vault_backup_TIMESTAMP)
2. If 100+ items affected: test on a 5-10 item sample first
3. For multi-task tools: list all tasks, identify destructive side effects

Data value is determined by recreation cost:
- Irreplaceable (original exports): always protect
- Costly (LLM-generated T2/T3/outputs): protect before destructive ops
- Free (seed-direct T1, embeddings, cache): no protection needed
```

### WORKER_SPEC.md additions

```markdown
### §3 addition: Before executing destructive batch operations

If the current step modifies or deletes data classified as "costly" or
"irreplaceable" in GOVERNANCE.md §Valuable Data Protection:
1. Take a snapshot before proceeding
2. Log the protection action in DEVLOG
3. If snapshot is not possible: ESCALATE

If the current step involves LLM API calls:
1. Estimate cost and log it
2. Confirm budget is configured in the cost accountant
3. If estimated cost >$1 and no human approval in the step specification: ESCALATE
```

### Toolkit additions

- `toolkit/cost_accountant/` — new module (see `DESIGN_COST_ACCOUNTANT.md`)
- All LLM-consuming projects wire through the accountant

### Per-project additions

Each project that uses LLM calls adds to its DEVPLAN gotchas:
```
- **Cost accountant required** — all LLM calls must go through
  toolkit/cost_accountant. No direct llm_client.complete() calls
  in production code paths.
```

---

## Part 5: What This Would Have Caught

| Issue | Would Cost Gate catch it? | Would Data Protection Gate catch it? |
|-------|--------------------------|--------------------------------------|
| 1. `--seed-only` $35 spend | **Yes** — estimate would show $35 vs $0 | No |
| 5. Sonnet 4.5 refusals | **Yes** — repeated failures would abort | No |
| 8. Context overflow | **Yes** — input size check before call | No |
| 9. Note ID collision | No | **Yes** — but only if recognized as destructive (silent overwrite) |
| 11. LLM ID hallucination | Partially — would log wasted calls | No |
| 14. 175-min retry loop | **Yes** — abort on "usage limits" error | No |
| 16. Decay destroyed T1 | No (free operation) | **Yes** — destructive batch on costly data, snapshot required |
| 17. `--once` runs decay | No | **Yes** — side effect listing would flag decay |

**Combined coverage: 7 of 8 preventable issues caught.** Issue 9 (silent overwrite) is a code bug — neither gate catches silent data corruption. That requires defensive coding (check-before-write).

---

## Part 6: Implementation Priority

| Priority | What | Effort | Blocks |
|----------|------|--------|--------|
| **P0** | GOVERNANCE.md policy additions | 1 hour | Nothing — policy is free |
| **P0** | WORKER_SPEC.md additions | 30 min | Nothing |
| **P1** | `toolkit/cost_accountant` module | 7 hours | All future LLM operations |
| **P2** | Wire accountant into Phosphene | 1 hour | Phosphene LLM resume |
| **P2** | `tools/cost_report.py` | 30 min | Spend visibility |
| **P3** | Decay `--dry-run` mode | 2 hours | Safe decay testing |
| **P3** | `run.py --once --skip-decay` flag | 30 min | Safe orchestrator testing |

P0 items (policy) can be done immediately and apply to all future work even before the cost accountant is built. P1 (cost accountant) is the main structural enforcement. P2-P3 are per-project hardening.

---

## Part 7: Interactive Session Safety — The `/checkpoint` Command

### The Problem with Boundaries

The governance framework was built for supervised development and extended to autonomous work. The autonomous worker has clear state transitions (plan → execute → review → close) with safety checks at each boundary. But most costly failures happened during **interactive sessions**, which have no fixed boundaries:

- Sessions start and stop informally — you might stop, come back, continue the same session
- Work follows human attention — exploring, refining, getting distracted, coming back
- The transition from "safe operation" (read a file) to "dangerous operation" (run $5 LLM batch on production data) is invisible — both feel like "the next step"

Formalizing interactive sessions with rigid structure would kill their value. The solution is structural gates (cost accountant, decay backup requirement) for hard safety, plus an **on-demand checkpoint** for soft awareness.

### Proposed: `/checkpoint` Command

A slash command you can run at any point during a session — before stopping, before handing off to the worker, after a major operation, when switching topics, or never if the session was just reading code.

**What it does:**

1. **Audit costly operations** — scan for new LLM call sites (functions calling `llm_client.complete()` or `cost_accountant.complete()`) not in the project's costly ops manifest. Report any unclassified call sites.

2. **Audit data classifications** — scan vault directories and data paths for unclassified locations. Report any directories containing data that hasn't been assigned a value tier (irreplaceable / costly / free / ephemeral).

3. **Audit tools/commands** — scan `tools/*.py` and `run.py` subcommands for entries not in the operations table. Report any unclassified commands.

4. **Update DEVLOG** — append a checkpoint entry summarizing what happened since the last checkpoint or session start.

5. **Commit** — offer to commit uncommitted changes.

6. **Print summary** — "2 new unclassified LLM call sites, vault/outputs/ not classified, 3 files uncommitted."

**Properties:**
- **On-demand** — you run it when it feels right, not at a forced boundary
- **Idempotent** — running it twice is harmless, running it mid-session is fine
- **Lightweight** — takes 30 seconds, doesn't interrupt flow
- **Covers both modes** — works for supervised sessions and as part of autonomous phase close
- **Optional** — not required by governance. The structural gates (cost accountant, code-level enforcement) handle hard safety regardless

### Relationship to Existing Commands

| Command | When | What |
|---------|------|------|
| `/step-done` | After each autonomous step | Log, commit, prep for next step |
| `/phase-review` | End of autonomous phase | Review code against architecture |
| `/phase-complete` | Phase close | Doc cleanup, archival, gate |
| `/checkpoint` (new) | **Anytime** | Audit cost/data flags, update DEVLOG, commit |

`/checkpoint` is lighter than `/phase-review` and usable outside the autonomous loop. It could be incorporated into `/phase-complete` as a substep for autonomous work.

### How It Prevents the Issues We Hit

| Issue | Would `/checkpoint` have caught it? |
|-------|-------------------------------------|
| `--seed-only` $35 spend | Possibly — if run before the seed, it would have noted unclassified operations |
| Decay destroyed T1 | Possibly — if run after T2→T3 and before `--once`, it would have flagged `run_decay()` as unclassified destructive |
| 175-min retry | No — this is a runtime issue, needs cost accountant |
| 14 T3 files | No — this is a code bug |

`/checkpoint` is a soft defense — it catches classification gaps. The hard defense (cost accountant, code gates) catches runtime issues.

---

## Part 8: Optionality — Subscription vs Pay-Per-Call

### The Cost Spectrum

Different projects have different cost profiles:

| Profile | Example | Cost Mechanism | Optimization |
|---------|---------|---------------|--------------|
| **Subscription (token budget)** | Devmate sessions, Claude Pro | Fixed monthly, optimize tokens | Tiered context loading, DEVLOG archival, DEVPLAN summarization, batch worker steps |
| **Pay-per-call (cash)** | Anthropic API, OpenRouter | Variable, direct cash spend | Cost accountant, budget caps, rate limit abort |
| **Free (local compute)** | Embedding, UMAP, HDBSCAN | CPU/time only | No cost governance needed |

The cost governance mechanisms (accountant, data protection, `/checkpoint`) should be **opt-in per project**, not globally mandatory. A project using only subscription-based models doesn't need the cost accountant. A project with no LLM calls doesn't need cost audit.

### Configuration

Each project declares its cost profile in PROJECT.md or DEVPLAN:

```markdown
## Cost Profile
- **LLM calls:** Pay-per-call (Anthropic API). Cost accountant required.
- **Embedding:** Free (local). No cost governance.
- **Data value tiers:** See .safety.yaml
```

Projects without this section use the default: no cost accountant, standard governance only.

### Overlap with Existing Token Optimizations

The existing governance already optimizes for token cost:
- Tiered context loading (don't load docs you don't need)
- DEVLOG archiving (keep active log short)
- DEVPLAN summarization (get shorter as work progresses)
- Batch worker steps (reduce cold-start overhead)

These optimizations serve a different goal (keep context within limits) but the principle is the same: **don't waste resources.** The cost accountant extends this principle from "don't waste context tokens" to "don't waste API dollars." The data protection gate extends it from "don't waste time" to "don't waste the artifacts of previous time/money investment."

All three (token optimization, cost governance, data protection) are instances of the same meta-rule: **be aware of what's expensive, and be careful with it.**
