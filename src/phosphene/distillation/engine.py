"""Distillation engine public constructor."""

from __future__ import annotations


class DistillationEngine:
    """Coordinate tier promotion through a Memory Store.

    Phase 1 starts with the constructor-only public shell. Gate evaluation,
    metadata, locking, and synthesis operations are added in subsequent steps.
    """

    def __init__(self, memory_store):
        self.memory_store = memory_store
