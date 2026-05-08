"""Orchestrator exception hierarchy."""


class OrchestratorError(Exception):
    """Base class for Orchestrator errors."""


class ConfigError(OrchestratorError):
    """Raised when Orchestrator configuration is invalid."""


class UnknownTaskTypeError(OrchestratorError):
    """Raised when an activation task type is not recognized."""
