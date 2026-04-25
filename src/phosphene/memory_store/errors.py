"""Memory Store exception hierarchy."""


class MemoryStoreError(Exception):
    """Base class for Memory Store errors."""


class VaultError(MemoryStoreError):
    """Raised when the vault cannot be opened or written."""


class InvalidTierError(MemoryStoreError):
    """Raised when a tier is not one of 1, 2, or 3."""


class TitleTooLongError(MemoryStoreError):
    """Raised when a note title exceeds the ARCH limit."""


class InvalidScoreError(MemoryStoreError):
    """Raised when a score field falls outside its valid range."""


class NoteNotFoundError(MemoryStoreError):
    """Raised when a note id cannot be found."""


class DimensionMismatchError(MemoryStoreError):
    """Raised when embedding dimensions do not match."""


class TierMismatchError(MemoryStoreError):
    """Raised when an operation requires a different note tier."""


class AlreadySupersededError(MemoryStoreError):
    """Raised when a note has already been superseded."""
