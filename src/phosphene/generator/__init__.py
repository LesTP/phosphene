"""Public Generator + Output Router API surface."""

from phosphene.generator.errors import (
    EmptyPersonalityError,
    GeneratorConfigError,
    GeneratorError,
    LLMAPIError,
)
from phosphene.generator.generator import Generator
from phosphene.generator.router import route
from phosphene.generator.types import (
    Contradiction,
    FreePlayTrigger,
    GenerationPrompt,
    GeneratorConfig,
    GeneratorOutput,
    LengthThresholds,
    PersonalitySnapshot,
    RouterConfig,
)

__all__ = [
    "Contradiction",
    "EmptyPersonalityError",
    "FreePlayTrigger",
    "GenerationPrompt",
    "Generator",
    "GeneratorConfig",
    "GeneratorConfigError",
    "GeneratorError",
    "GeneratorOutput",
    "LLMAPIError",
    "LengthThresholds",
    "PersonalitySnapshot",
    "RouterConfig",
    "route",
]
