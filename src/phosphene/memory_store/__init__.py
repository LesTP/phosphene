"""Public Memory Store API surface."""

from phosphene.memory_store.errors import (
    AlreadySupersededError,
    DimensionMismatchError,
    InvalidScoreError,
    InvalidTierError,
    MemoryStoreError,
    NoteNotFoundError,
    TierMismatchError,
    TitleTooLongError,
    VaultError,
)
from phosphene.memory_store.store import MemoryStore
from phosphene.memory_store.types import (
    DecayReport,
    DensityMetrics,
    IndexEntry,
    MemoryNote,
    MemoryStoreConfig,
    NoteInput,
    NotePatch,
    NoteQuery,
    PersonalityContext,
)

__all__ = [
    "AlreadySupersededError",
    "DecayReport",
    "DensityMetrics",
    "DimensionMismatchError",
    "IndexEntry",
    "InvalidScoreError",
    "InvalidTierError",
    "MemoryStore",
    "MemoryNote",
    "MemoryStoreConfig",
    "MemoryStoreError",
    "NoteInput",
    "NoteNotFoundError",
    "NotePatch",
    "NoteQuery",
    "PersonalityContext",
    "TierMismatchError",
    "TitleTooLongError",
    "VaultError",
]
