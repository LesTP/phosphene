# Phosphene — Project Status & Roadmap

**Date:** 2026-05-16
**Purpose:** Cold-start overview for any session. Where we are, what works, what's next.

---

## What's Working

### Core Loop (Proven End-to-End)

```
Corpus → T1 (3,856 notes) → T2 (251 clusters) → T3 (7 personality files) → Generation → Telegram
```

First output delivered to Telegram on 2026-05-14. Content is personality-specific, derived from 20+ years of corpus.

### Modules Complete (7 of 9 + MVP Orchestrator)

| Module | Status | Tests |
|--------|--------|-------|
| Memory Store | Complete | 98% coverage |
| Attention Filter | Complete | 97% coverage |
| Source Ingestion | Complete | 99% coverage |
| Gateway | Complete | — |
| Generator + Output Router | Complete | — |
| Distillation | Complete | — |
| Feedback Collector (Phase 7.1) | Complete | — |
| MVP Orchestrator (Phases 1-3) | Complete | — |
| **Total** | **640 tests** | **98% overall** |

### Infrastructure

- Pi 5 deployment: venv on SSD (1.6GB, CPU-only PyTorch), 13GB SD card free
- Index cache: 12s startup (was 15+ min)
- Network visualization: interactive HTML + static PNG
- Lean scripts: `run_first_generation.py` (~30s), `run_t2_to_t3.py` (~5 min)
- Outputs saved to `vault/outputs/` (not in distillation loop)
- T2 cross-links: similarity-filtered (1-15 per note)
- T2→T3: batched reflection + bootstrap creation

### Vault State

- 3,856 T1 notes (restored after decay incident)
- 251 T2 pattern clusters + 225 assertion caches
- 7 T3 personality files (evolved from 51 insights)
- 1 generation output
- 4,122 embedding files (.npy)

---

## Blockers

| Blocker | Impact | Resolution |
|---------|--------|-----------|
| **Anthropic API spending cap hit** | No LLM calls until June 1 | Raise limit or wait |
| **Cost accountant doesn't exist** | Prerequisite for all future LLM spend | Build in toolkit (~7h) |
| **Decay destroys seeded corpus** | DO NOT run decay | Fix retention for historical timestamps |

---

## Open Bugs

| Bug | Severity | Status |
|-----|----------|--------|
| `datetime.now()` naive vs aware in generator | Medium | Fixed in code, not validated on Pi |
| Sonnet 4 deprecated June 15, 2026 | Medium | Needs model migration testing |
| `run.py --once` ingestion retries against spending cap for 175 min | Low | Cost accountant will abort |
| 14 T3 files on disk (7 superseded) | Low | `get_personality_context()` filters correctly; lean script fixed |

---

## Design Docs (Written, Not Implemented)

| Document | What | Location |
|----------|------|----------|
| Batch Seeding Pipeline | `--seed-full-lifecycle`, `explore_corpus.py`, Twitter adapter | `DESIGN_BATCH_SEEDING.md` |
| Cost & Data Governance | Issue catalog, cost/data gates, `/checkpoint` command | `DESIGN_COST_GOVERNANCE.md` |
| Cost Accountant | Budget enforcement, ledger, reporting | `toolkit/DESIGN_COST_ACCOUNTANT.md` |

---

## Immediate Next Steps

### Can Do Without API Access

| Priority | What | Effort | Notes |
|----------|------|--------|-------|
| **1** | Build cost accountant in toolkit | ~7 hours | Blocks all future LLM work |
| **2** | Wire cost accountant into Phosphene | ~1 hour | Replace direct llm_client calls |
| **3** | Add governance policy to GOVERNANCE.md | ~1 hour | Costly ops + data protection rules |
| **4** | Fix decay for seeded corpora | ~2 hours | Design decision needed first |

### Needs API Access (June 1+)

| Priority | What | Effort | Notes |
|----------|------|--------|-------|
| **5** | Test model migration (Sonnet 4 → newer) | ~1 hour | Sonnet 4 EOL June 15 |
| **6** | Wire live source ingestion | ~2 hours | Telegram channel or RSS |
| **7** | Deploy as systemd service | ~1 hour | Long-running, no `--once` |
| **8** | 48-hour unattended run | Observation | MVP validation criterion |

---

## MVP Completion Checklist

Per PROJECT.md MVP Definition:

- [x] Seed corpus imported into Memory Store and searchable
- [ ] At least one live source ingests on recurring schedule
- [x] Distillation produces T2 clusters from T1 content
- [x] Distillation produces T3 personality files from T2 patterns
- [x] Generator produces output derived from personality context
- [x] Output delivered to Telegram
- [ ] System runs unattended for 48 hours without manual intervention

**Status: ~90% complete.** Missing: live source + 48-hour unattended run.

---

## Post-MVP Roadmap

### Near-Term (quality + stability)

- Inbound message handler (`#` prefix → ingestion, bare text → conversation)
- Leiden community detection (replace HDBSCAN)
- Batch seeding pipeline (`--seed-full-lifecycle`, `explore_corpus.py`)
- Twitter adapter + second corpus import
- Strategy C epoch training (filtered re-evaluation pass)

### Medium-Term (modules 8-9)

- Feedback Collector Phase 7.2 (delayed engagement checks) ~8h
- Explorer module (link-following, source evaluation) ~15h
- Full Orchestrator (lateral freedom, tension-responsive scheduling, ambient context) ~20h

### Long-Term (flexible scope)

- Discord output channel
- Reviewer Panel (multi-model evaluation)
- Model Router (subscription rotation)
- Adversarial self (second divergent agent)
- Publication channels (Substack, blog)

---

## The Vision

From PROJECT.md:

> *A system that produces something that appears to come from outside but originates entirely in its own accumulated structure — an autonomous agent seeded with a human's writing corpus, designed to develop a personality over time through browsing, memory accumulation, distillation, and generative output.*

After 6 months of operation, the personality files would have gone through ~6 T2→T3 evolution cycles. Each cycle nudges the T3 files based on new patterns. The system you'd observe would be recognizably descended from the seed corpus but would have developed its own preoccupations, tensions, and aesthetic orientations. The primary success signal: the human continues reading the outputs.

---

## Key References

| Document | Purpose |
|----------|---------|
| `PROJECT.md` | Scope, audience, constraints, success criteria, MVP definition |
| `ARCHITECTURE.md` | Component map, data flow, implementation sequence |
| `DEVPLAN.md` | Current phase, steps, gotchas, operations reference |
| `DEVLOG.md` | What happened (current phase) |
| `DEVLOG_archive.md` | What happened (previous phases) |
| `notebooks/TUNING_GUIDE.md` | Corpus-to-personality findings and parameter recommendations |
| `DESIGN_BATCH_SEEDING.md` | Future seeding pipeline design |
| `DESIGN_COST_GOVERNANCE.md` | Cost/data governance design |
| `toolkit/DESIGN_COST_ACCOUNTANT.md` | Cost tracking module design |
