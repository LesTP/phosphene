"""Attention Filter exception hierarchy."""


class AttentionFilterError(Exception):
    """Base class for Attention Filter errors."""


class InvalidScoreError(AttentionFilterError):
    """Raised when a score or scoring threshold falls outside its valid range."""
