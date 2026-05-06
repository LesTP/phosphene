"""Distillation exception hierarchy."""


class DistillationError(Exception):
    """Base class for Distillation errors."""


class DistillationLockError(DistillationError):
    """Raised when another distillation run is already active."""


class InsufficientDataError(DistillationError):
    """Raised when there is not enough Tier 1 material to promote."""


class NoPatternDataError(DistillationError):
    """Raised when there is no Tier 2 pattern material to evolve."""


class DistillationConfigError(DistillationError):
    """Raised when Distillation configuration is invalid."""
