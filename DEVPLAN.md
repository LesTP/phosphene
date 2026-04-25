---
module: MEMORY_STORE
phase: 1
phase_title: null
step: 0 of 0
mode: Discuss
blocked: null
regime: Build
review_done: false
---

# Phosphene — Development Plan

<!-- This file is the primary state document for autonomous iteration.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses. -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step. -->

- **What this is** — Autonomous personality agent with hierarchical memory, attention filtering, and personality development through distillation.
- **Key constraints** — Python 3.12+. Depends on toolkit/ (sibling project, all modules complete). Obsidian-compatible markdown storage. LLM API costs managed via subscription rotation and model tier system. Runs on Raspberry Pi 5 (orchestration only, inference via API).
- **Gotchas** —
  - toolkit/ is an external dependency — import from it, never modify it
  - Memory Store uses consumer-provided embeddings (no toolkit/embedding dependency in the store itself)
  - All 10 ARCH files define contracts — implementation must match signatures exactly
  - Model selection policy D-5: single primary model during establishment phase (~90 days)
  - NTFS drives: use `bash script.sh`, not `./script.sh`

## Current Status

- **Phase** — Not started
- **Focus** — Initial setup — first module (Memory Store) ready for Phase Plan
- **Blocked/Broken** — None

## Module 1: Memory Store

<!-- Break into phases during the Phase Plan action. Start with:
Phase 1: Core data model and CRUD
Phase 2: Index layer and queries
Phase 3: Embedding search and graph operations
Phase 4: Decay and density metrics
-->

<!-- HISTORY — Worker: stop reading here. Everything below is completed phase history. -->
