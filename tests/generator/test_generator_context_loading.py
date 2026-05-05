from dataclasses import dataclass
from datetime import datetime

import pytest

from phosphene.generator import EmptyPersonalityError, GenerationPrompt, Generator, GeneratorConfig
from phosphene.memory_store import MemoryNote, PersonalityContext


def make_note(note_id: str, *, tier: int = 3, importance: float = 0.0) -> MemoryNote:
    return MemoryNote(
        note_id=note_id,
        tier=tier,
        content=f"{note_id} body",
        title=note_id,
        importance=importance,
        unresolvedness=0.0,
        links=[],
        tags=[],
        source=None,
        friction_target=None,
        embedding=None,
        attractor_relevance=None,
        cluster_group=None,
        supersedes=None,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
        link_count=0,
        decay_deadline=None,
    )


@dataclass
class FakeMemoryStore:
    personality_files: list[MemoryNote]
    query_results: list[MemoryNote] | None = None
    search_results: list[tuple[MemoryNote, float]] | None = None

    def __post_init__(self) -> None:
        self.context_calls = 0
        self.query_calls: list[object] = []
        self.search_calls: list[tuple[object, int | None, int]] = []
        self.write_calls = 0

    def get_personality_context(self) -> PersonalityContext:
        self.context_calls += 1
        return PersonalityContext(
            personality_files=list(self.personality_files),
            version_id=f"version-{self.context_calls}",
        )

    def query_notes(self, query: object) -> list[MemoryNote]:
        self.query_calls.append(query)
        return list(self.query_results or [])

    def search_by_embedding(
        self,
        embedding: object,
        *,
        tier: int | None = None,
        limit: int = 10,
    ) -> list[tuple[MemoryNote, float]]:
        self.search_calls.append((embedding, tier, limit))
        return list(self.search_results or [])

    def store_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def update_note(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls += 1


def test_snapshot_loads_fresh_tier_three_context_and_preserves_source_ids() -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2, importance=0.8)
    store = FakeMemoryStore([personality], query_results=[pattern])
    generator = Generator(store)

    snapshot = generator._load_personality_snapshot(
        {"hour": 12},
        GeneratorConfig(llm_config=object()),
    )

    assert store.context_calls == 1
    assert snapshot.personality_files == [personality]
    assert snapshot.relevant_patterns == [pattern]
    assert snapshot.contradictions == []
    assert snapshot.ambient_context == {"hour": 12}
    assert generator._source_note_ids(snapshot) == ["personality-1", "pattern-1"]
    assert store.write_calls == 0


def test_snapshot_raises_empty_personality_when_tier_three_context_absent() -> None:
    store = FakeMemoryStore([])

    with pytest.raises(EmptyPersonalityError, match="Tier 3"):
        Generator(store)._load_personality_snapshot(
            {},
            GeneratorConfig(llm_config=object()),
        )

    assert store.query_calls == []
    assert store.search_calls == []
    assert store.write_calls == 0


def test_public_generation_methods_check_empty_personality_before_llm_phase() -> None:
    store = FakeMemoryStore([])

    with pytest.raises(EmptyPersonalityError):
        Generator(store).generate(
            GenerationPrompt(topic="density"),
            {},
            GeneratorConfig(llm_config=object()),
        )


def test_tier_two_enrichment_can_use_embedding_search_boundary() -> None:
    personality = make_note("personality-1", tier=3)
    pattern = make_note("pattern-1", tier=2)
    embedding = object()
    store = FakeMemoryStore([personality], search_results=[(pattern, 0.91)])

    snapshot = Generator(store)._load_personality_snapshot(
        {},
        GeneratorConfig(llm_config=object(), tier2_pattern_limit=3),
        topic_embedding=embedding,
    )

    assert snapshot.relevant_patterns == [pattern]
    assert store.search_calls == [(embedding, 2, 3)]
    assert store.query_calls == []
    assert store.write_calls == 0


def test_tier_two_enrichment_can_be_disabled() -> None:
    store = FakeMemoryStore([make_note("personality-1", tier=3)])

    snapshot = Generator(store)._load_personality_snapshot(
        {},
        GeneratorConfig(llm_config=object(), include_tier2_patterns=False),
    )

    assert snapshot.relevant_patterns == []
    assert store.query_calls == []
    assert store.search_calls == []
