"""Distillation engine public constructor."""

from __future__ import annotations

from collections.abc import Callable

from phosphene.distillation.errors import DistillationConfigError

_REQUIRED_MEMORY_STORE_METHODS = (
    "query_notes",
    "store_note",
    "update_note",
    "add_links",
    "get_personality_context",
    "supersede",
)


class DistillationEngine:
    """Coordinate tier promotion through a Memory Store.

    Phase 1 starts with the constructor-only public shell. Gate evaluation,
    metadata, locking, and synthesis operations are added in subsequent steps.
    """

    def __init__(self, memory_store):
        _validate_memory_store(memory_store)
        self.memory_store = memory_store


def _validate_memory_store(memory_store: object) -> None:
    if memory_store is None:
        raise DistillationConfigError("memory_store is required")

    for method_name in _REQUIRED_MEMORY_STORE_METHODS:
        method = getattr(memory_store, method_name, None)
        if not isinstance(method, Callable):
            raise DistillationConfigError(f"memory_store must provide {method_name}()")

    if getattr(memory_store, "vault_path", None) is None:
        raise DistillationConfigError("memory_store must expose vault_path")
