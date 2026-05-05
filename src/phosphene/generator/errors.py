"""Generator exception hierarchy."""


class GeneratorError(Exception):
    """Base class for Generator errors."""


class GeneratorConfigError(GeneratorError):
    """Raised when Generator or Router configuration is invalid."""


class EmptyPersonalityError(GeneratorError):
    """Raised when no Tier 3 personality context exists for generation."""


class LLMAPIError(GeneratorError):
    """Raised when the generation LLM boundary fails."""
