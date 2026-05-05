"""Generator public entry point."""

from __future__ import annotations

from phosphene.gateway import InboundMessage
from phosphene.generator.types import (
    AmbientContext,
    FreePlayTrigger,
    GenerationPrompt,
    GeneratorConfig,
    GeneratorOutput,
)


class Generator:
    """Stateless Generator facade.

    LLM-backed generation behavior is introduced in a later phase; this phase
    establishes the public constructor and method surface.
    """

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def generate(
        self,
        prompt: GenerationPrompt,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def free_play(
        self,
        trigger: FreePlayTrigger,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def respond(
        self,
        message: InboundMessage,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        raise NotImplementedError("LLM generation is implemented in a later phase")
