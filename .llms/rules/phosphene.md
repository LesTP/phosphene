# Phosphene

## Framework
This project follows the From Idea to Code governance framework.

## Always Loaded
- @PROJECT.md — scope, audience, constraints
- @ARCHITECTURE.md — component map, data flow, sequence
- @GOVERNANCE.md — development process reference

## Load for Current Module
Determine the active module from ARCHITECTURE.md's Implementation Sequence table — first module without "Complete" status. Then load:
- ARCH_[module].md — module contract and interface spec
- DEVPLAN.md — current status, phase plan, cold start summary
- DEVLOG.md — history (load when debugging or reviewing)

## Available Modules
<!-- Update this list as ARCH files are created -->
- Memory Store — three-tier hierarchical memory (ARCH_memory_store.md)
- Seeding — corpus-to-personality pipeline (ARCH_seeding.md)
- Attention Filter — personality-driven content selection and annotation (ARCH_attention_filter.md)
- Source Ingestion — adapters for content sources including human-share channel (ARCH_source_ingestion.md)
- Distillation — tier promotion with RAPTOR clustering and reflect-evolve (ARCH_distillation.md)
- Orchestrator — activation lifecycle, scheduling, lateral freedom, ambient context (ARCH_orchestrator.md)

## Reference Documents (load on demand)
- phosphene.md — comprehensive design document (conceptual foundations, prior art, full architecture rationale)
- prior_art.md — prior art survey

## Shared Dependencies
This project depends on modules from the toolkit project:
- toolkit/ARCH_embedding.md — text → vector embeddings
- toolkit/ARCH_clustering.md — semantic grouping
- toolkit/ARCH_llm_client.md — LLM API abstraction
- toolkit/ARCH_telegram_client.md — Telegram messaging

Toolkit location: c:\Users\myeluashvili\claude-code-workspace\projects\toolkit\

## Project-Specific Notes
<!-- Add operational knowledge, build commands, test commands as implementation progresses -->
