"""Generator public entry point."""

from __future__ import annotations

from phosphene.gateway import InboundMessage
from phosphene.generator.errors import EmptyPersonalityError
from phosphene.generator.types import (
    AmbientContext,
    FreePlayTrigger,
    GenerationPrompt,
    GeneratorConfig,
    GeneratorOutput,
    PersonalitySnapshot,
)
from phosphene.memory_store import MemoryNote, NoteQuery


class Generator:
    """Stateless Generator facade.

    LLM-backed generation behavior is introduced in a later phase; this phase
    establishes the public constructor and method surface.
    """

    def __init__(self, memory_store: object) -> None:
        self.memory_store = memory_store

    def _load_personality_snapshot(
        self,
        ambient: AmbientContext,
        config: GeneratorConfig,
        *,
        topic_embedding: object | None = None,
    ) -> PersonalitySnapshot:
        context = self.memory_store.get_personality_context()
        personality_files = list(context.personality_files)
        if not personality_files:
            raise EmptyPersonalityError("no Tier 3 personality context exists")

        return PersonalitySnapshot(
            personality_files=personality_files,
            relevant_patterns=self._load_relevant_patterns(
                config,
                topic_embedding=topic_embedding,
            ),
            contradictions=[],
            ambient_context=ambient,
        )

    def _load_relevant_patterns(
        self,
        config: GeneratorConfig,
        *,
        topic_embedding: object | None = None,
    ) -> list[MemoryNote]:
        if not config.include_tier2_patterns or config.tier2_pattern_limit == 0:
            return []

        if topic_embedding is not None and hasattr(self.memory_store, "search_by_embedding"):
            results = self.memory_store.search_by_embedding(
                topic_embedding,
                tier=2,
                limit=config.tier2_pattern_limit,
            )
            return [note for note, _similarity in results]

        if hasattr(self.memory_store, "query_notes"):
            return list(
                self.memory_store.query_notes(
                    NoteQuery(
                        tier=2,
                        limit=config.tier2_pattern_limit,
                        order_by="importance",
                    )
                )
            )

        return []

    @staticmethod
    def _source_note_ids(snapshot: PersonalitySnapshot) -> list[str]:
        notes = [*snapshot.personality_files, *snapshot.relevant_patterns]
        return [str(note.note_id) for note in notes]

    def generate(
        self,
        prompt: GenerationPrompt,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def free_play(
        self,
        trigger: FreePlayTrigger,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")

    def respond(
        self,
        message: InboundMessage,
        ambient: AmbientContext,
        config: GeneratorConfig,
    ) -> GeneratorOutput:
        self._load_personality_snapshot(ambient, config)
        raise NotImplementedError("LLM generation is implemented in a later phase")
