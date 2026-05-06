from dataclasses import dataclass, field

import pytest

from phosphene.distillation import (
    DistillationConfig,
    DistillationEngine,
    ReflectionInsight,
)
from phosphene.distillation.engine import (
    _build_evolution_proposal_artifact,
    _build_evolution_request,
    _build_reflection_audit_artifact,
    _criterion_feedback_metrics,
    _effective_inertia,
    _parse_evolution_proposals,
    _parse_reflection_insights,
    _prepare_personality_files,
)
from phosphene.distillation.errors import (
    DistillationError,
    DistillationLockError,
    NoPatternDataError,
)


@dataclass
class EvolutionNote:
    note_id: str
    content: str = ""
    title: str = ""
    source: str | None = None
    importance: float = 0.0
    unresolvedness: float = 0.0
    links: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    friction_target: str | None = None
    cluster_group: str | None = None
    version_count: int | None = None


@dataclass
class EvolutionPersonalityContext:
    personality_files: list[EvolutionNote]
    version_id: str = "personality-version"


class EvolutionMemoryStore:
    def __init__(
        self,
        vault_path,
        *,
        tier2_notes: list[EvolutionNote] | None = None,
        feedback_events: list[EvolutionNote] | None = None,
        personality_context: EvolutionPersonalityContext | None = None,
    ) -> None:
        self.vault_path = vault_path
        self.tier2_notes = tier2_notes or []
        self.feedback_events = feedback_events or []
        self.personality_context = personality_context or EvolutionPersonalityContext(
            personality_files=[
                EvolutionNote(
                    "personality-a",
                    title="Stable stance",
                    content="Keep existing stance.",
                    version_count=2,
                )
            ]
        )
        self.queries = []
        self.write_calls: list[str] = []
        self.personality_context_calls = 0

    def query_notes(self, query):
        self.queries.append(query)
        if query.tier == 2:
            notes = self.tier2_notes
        elif query.source == "feedback":
            notes = self.feedback_events
        else:
            notes = []
        return notes[: query.limit]

    def store_note(self, *_args: object, **_kwargs: object) -> str:
        self.write_calls.append("store_note")
        raise AssertionError("T2 to T3 preparation must not store notes")

    def update_note(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("update_note")
        raise AssertionError("T2 to T3 preparation must not update notes")

    def add_links(self, *_args: object, **_kwargs: object) -> None:
        self.write_calls.append("add_links")
        raise AssertionError("T2 to T3 preparation must not add links")

    def get_personality_context(self) -> object:
        self.personality_context_calls += 1
        return self.personality_context

    def supersede(self, *_args: object, **_kwargs: object) -> object:
        self.write_calls.append("supersede")
        raise AssertionError("T2 to T3 preparation must not supersede notes")


def test_prepare_tier2_evolution_input_queries_patterns_and_feedback_metrics(tmp_path) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        tier2_notes=[
            EvolutionNote("pattern-a", content="first pattern", cluster_group="a"),
            EvolutionNote("pattern-b", content="second pattern", cluster_group="b"),
        ],
        feedback_events=[
            EvolutionNote(
                "feedback-1",
                source="feedback",
                importance=0.8,
                tags=["criterion:precision_surplus"],
            ),
            EvolutionNote(
                "feedback-2",
                source="feedback",
                importance=0.2,
                unresolvedness=0.7,
                tags=["criterion=precision surplus", "criterion:friction"],
                friction_target="pattern-a",
            ),
            EvolutionNote(
                "feedback-3",
                source="feedback",
                importance=0.1,
                tags=["criterion:friction"],
            ),
        ],
    )
    engine = DistillationEngine(store)

    prepared = engine._prepare_tier2_evolution_input(
        DistillationConfig(llm_config=object(), embedding_config=object())
    )

    assert [note.note_id for note in prepared.pattern_notes] == ["pattern-a", "pattern-b"]
    assert [event.note_id for event in prepared.feedback_events] == [
        "feedback-1",
        "feedback-2",
        "feedback-3",
    ]
    assert [query.tier for query in store.queries] == [2, 1]
    assert store.queries[0].order_by == "created_at"
    assert store.queries[0].descending is False
    assert store.queries[1].source == "feedback"
    metric_counts = [
        (metric.criterion_name, metric.feedback_count)
        for metric in prepared.feedback_metrics
    ]
    assert metric_counts == [
        ("friction", 2),
        ("precision_surplus", 2),
    ]
    assert [metric.engaged_count for metric in prepared.feedback_metrics] == [1, 2]
    assert [metric.engagement_rate for metric in prepared.feedback_metrics] == pytest.approx(
        [0.5, 1.0]
    )
    assert [metric.mean_engagement for metric in prepared.feedback_metrics] == pytest.approx(
        [0.4, 0.75]
    )
    assert store.write_calls == []


def test_prepare_tier2_evolution_input_respects_disabled_feedback(tmp_path) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        tier2_notes=[EvolutionNote("pattern-a", content="first pattern")],
        feedback_events=[
            EvolutionNote("feedback-1", source="feedback", tags=["criterion:friction"])
        ],
    )
    engine = DistillationEngine(store)

    prepared = engine._prepare_tier2_evolution_input(
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            incorporate_feedback=False,
        )
    )

    assert [query.tier for query in store.queries] == [2]
    assert prepared.feedback_events == []
    assert prepared.feedback_metrics == []
    assert store.write_calls == []


def test_reflection_audit_artifact_calls_llm_and_parses_validated_insights(tmp_path) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        tier2_notes=[
            EvolutionNote(
                "pattern-a",
                content="first pattern",
                importance=0.8,
                cluster_group="cluster-a",
                tags=["distilled-pattern"],
            )
        ],
        feedback_events=[
            EvolutionNote(
                "feedback-1",
                source="feedback",
                importance=0.9,
                tags=["criterion:friction"],
            )
        ],
    )
    prepared = DistillationEngine(store)._prepare_tier2_evolution_input(
        DistillationConfig(llm_config=object(), embedding_config=object())
    )
    calls: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return (
            '{"insights": [{"content": "A recurring tension is emerging.", '
            '"source_pattern_ids": ["pattern-a"], '
            '"insight_type": "recurring_tension", "confidence": 0.75}]}'
        )

    artifact = _build_reflection_audit_artifact(
        prepared,
        DistillationConfig(
            llm_config="llm-config",
            embedding_config=object(),
            reflection_tier="reflect-tier",
        ),
        llm_complete_callable=fake_complete,
    )

    assert calls == [
        {
            "messages": artifact.request_messages,
            "config": "llm-config",
            "tier": "reflect-tier",
        }
    ]
    assert artifact.raw_response.startswith('{"insights"')
    assert len(artifact.insights) == 1
    assert artifact.insights[0].content == "A recurring tension is emerging."
    assert artifact.insights[0].source_pattern_ids == ["pattern-a"]
    assert artifact.insights[0].insight_type == "recurring_tension"
    assert artifact.insights[0].confidence == pytest.approx(0.75)
    assert store.write_calls == []


def test_prepare_personality_files_computes_version_count_inertia() -> None:
    context = EvolutionPersonalityContext(
        personality_files=[
            EvolutionNote(
                "personality-a",
                title="Stable stance",
                content="Keep existing stance.",
                version_count=5,
            ),
            EvolutionNote(
                "personality-b",
                title="Tagged stance",
                content="Use tag version count.",
                tags=["version_count:3"],
            ),
        ]
    )

    prepared = _prepare_personality_files(
        context,
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            inertia_per_cycle=0.5,
            max_inertia=2.0,
        ),
    )

    assert [(item.note_id, item.version_count) for item in prepared] == [
        ("personality-a", 5),
        ("personality-b", 3),
    ]
    assert [item.inertia for item in prepared] == pytest.approx([2.0, 2.0])
    assert _effective_inertia(
        2,
        DistillationConfig(
            llm_config=object(),
            embedding_config=object(),
            inertia_per_cycle=0.25,
        ),
    ) == pytest.approx(1.25)


def test_evolution_request_includes_insights_personality_files_and_inertia() -> None:
    personality_context = EvolutionPersonalityContext(
        personality_files=[
            EvolutionNote(
                "personality-a",
                title="Stable stance",
                content="Keep existing stance.",
                version_count=2,
            )
        ],
        version_id="version-123",
    )
    prepared_files = _prepare_personality_files(
        personality_context,
        DistillationConfig(llm_config=object(), embedding_config=object()),
    )

    messages = _build_evolution_request(
        [
            distillation_insight := ReflectionInsight(
                content="The stance is under useful pressure.",
                source_pattern_ids=["pattern-a"],
                insight_type="evolution",
                confidence=0.8,
            )
        ],
        prepared_files,
        personality_context,
    )

    assert messages[0]["role"] == "user"
    assert distillation_insight.content in messages[0]["content"]
    assert '"personality_version_id": "version-123"' in messages[0]["content"]
    assert '"note_id": "personality-a"' in messages[0]["content"]
    assert '"effective_inertia": 1.25' in messages[0]["content"]


def test_evolution_proposal_artifact_calls_evolution_tier_and_parses_proposals() -> None:
    personality_context = EvolutionPersonalityContext(
        personality_files=[
            EvolutionNote(
                "personality-a",
                title="Old stance",
                content="Old content.",
                version_count=1,
            ),
            EvolutionNote(
                "personality-b",
                title="Stable stance",
                content="Stable content.",
                version_count=4,
            ),
        ]
    )
    prepared_files = _prepare_personality_files(
        personality_context,
        DistillationConfig(llm_config=object(), embedding_config=object()),
    )
    calls: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return (
            '{"personality_proposals": ['
            '{"note_id": "personality-a", "action": "supersede", '
            '"new_title": "New stance", "new_content": "New content.", '
            '"change_summary": "Resolved pressure."},'
            '{"note_id": "personality-b", "action": "unchanged"}], '
            '"criteria_adjustments": [{"criterion_name": "precision surplus", '
            '"old_weight": 1.0, "new_weight": 1.1, '
            '"evidence": "High engagement."}]}'
        )

    artifact = _build_evolution_proposal_artifact(
        [
            ReflectionInsight(
                content="A contradiction should be resolved.",
                source_pattern_ids=["pattern-a"],
                insight_type="contradiction",
                confidence=0.9,
            )
        ],
        prepared_files,
        personality_context,
        DistillationConfig(
            llm_config="llm-config",
            embedding_config=object(),
            evolution_tier="evolve-tier",
        ),
        llm_complete_callable=fake_complete,
    )

    assert calls == [
        {
            "messages": artifact.request_messages,
            "config": "llm-config",
            "tier": "evolve-tier",
        }
    ]
    assert artifact.supersession_proposals[0].old_note_id == "personality-a"
    assert artifact.supersession_proposals[0].new_title == "New stance"
    assert artifact.supersession_proposals[0].new_content == "New content."
    assert artifact.supersession_proposals[0].change_summary == "Resolved pressure."
    assert artifact.unchanged_ids == ["personality-b"]
    assert artifact.criteria_adjustments[0].criterion_name == "precision_surplus"
    assert artifact.criteria_adjustments[0].new_weight == pytest.approx(1.1)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("not json", "valid JSON"),
        ('{"personality_proposals": "nope"}', "personality_proposals list"),
        ('{"personality_proposals": [{"note_id": "personality-x", "action": "unchanged"}]}', "unknown"),
        ('{"personality_proposals": [{"note_id": "personality-a", "action": "delete"}]}', "supersede or unchanged"),
        ('{"personality_proposals": [{"note_id": "personality-a", "action": "supersede", "new_title": "", "new_content": "x", "change_summary": "x"}]}', "new_title cannot be empty"),
        ('{"personality_proposals": [{"note_id": "personality-a", "action": "supersede", "new_title": "x", "new_content": "", "change_summary": "x"}]}', "new_content cannot be empty"),
        ('{"personality_proposals": [{"note_id": "personality-a", "action": "unchanged"}], "criteria_adjustments": "nope"}', "criteria_adjustments must be a list"),
        ('{"personality_proposals": [{"note_id": "personality-a", "action": "unchanged"}], "criteria_adjustments": [{"criterion_name": "friction", "old_weight": true, "new_weight": 1.0, "evidence": "x"}]}', "old_weight must be numeric"),
    ],
)
def test_parse_evolution_proposals_rejects_malformed_responses(
    response: str,
    message: str,
) -> None:
    with pytest.raises(DistillationError, match=message):
        _parse_evolution_proposals(
            response,
            valid_personality_ids={"personality-a"},
        )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("not json", "valid JSON"),
        ('{"insights": "nope"}', "insights list"),
        ('{"insights": [{"content": "", "source_pattern_ids": ["pattern-a"], "insight_type": "new_pattern", "confidence": 0.2}]}', "content cannot be empty"),
        ('{"insights": [{"content": "x", "source_pattern_ids": [], "insight_type": "new_pattern", "confidence": 0.2}]}', "source_pattern_ids cannot be empty"),
        ('{"insights": [{"content": "x", "source_pattern_ids": ["pattern-x"], "insight_type": "new_pattern", "confidence": 0.2}]}', "unknown pattern ids"),
        ('{"insights": [{"content": "x", "source_pattern_ids": ["pattern-a"], "insight_type": "mood", "confidence": 0.2}]}', "insight_type"),
        ('{"insights": [{"content": "x", "source_pattern_ids": ["pattern-a"], "insight_type": "new_pattern", "confidence": 2}]}', r"confidence must be in \[0.0, 1.0\]"),
    ],
)
def test_parse_reflection_insights_rejects_malformed_responses(
    response: str,
    message: str,
) -> None:
    with pytest.raises(DistillationError, match=message):
        _parse_reflection_insights(response, valid_pattern_ids={"pattern-a"})


def test_distill_t2_to_t3_raises_no_pattern_data_before_feedback_or_writes(tmp_path) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        feedback_events=[
            EvolutionNote("feedback-1", source="feedback", tags=["criterion:friction"])
        ],
    )
    engine = DistillationEngine(store)

    with pytest.raises(NoPatternDataError, match="requires at least one Tier 2 pattern note"):
        engine.distill_t2_to_t3(
            DistillationConfig(llm_config=object(), embedding_config=object())
        )

    assert [query.tier for query in store.queries] == [2]
    assert store.write_calls == []
    assert engine._read_run_metadata().last_t2_to_t3_run is None
    assert engine._is_consolidation_locked() is False


def test_distill_t2_to_t3_lock_rejects_concurrent_run_before_queries(tmp_path) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        tier2_notes=[EvolutionNote("pattern-a")],
    )
    engine = DistillationEngine(store)

    with engine._acquire_consolidation_lock():
        with pytest.raises(DistillationLockError, match="already active"):
            engine.distill_t2_to_t3(
                DistillationConfig(llm_config=object(), embedding_config=object())
            )

    assert store.queries == []
    assert store.write_calls == []


def test_distill_t2_to_t3_preparation_releases_lock_without_writes(
    tmp_path,
    monkeypatch,
) -> None:
    store = EvolutionMemoryStore(
        tmp_path / "vault",
        tier2_notes=[EvolutionNote("pattern-a", content="first pattern")],
    )
    engine = DistillationEngine(store)
    calls: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        if len(calls) == 1:
            return (
                '{"insights": [{"content": "A new pattern is visible.", '
                '"source_pattern_ids": ["pattern-a"], "insight_type": "new_pattern", '
                '"confidence": 0.8}]}'
            )
        return (
            '{"personality_proposals": ['
            '{"note_id": "personality-a", "action": "unchanged"}], '
            '"criteria_adjustments": []}'
        )

    monkeypatch.setattr("phosphene.distillation.engine._toolkit_complete", fake_complete)

    with pytest.raises(NotImplementedError, match="Phase 3"):
        engine.distill_t2_to_t3(
            DistillationConfig(llm_config=object(), embedding_config=object())
        )

    assert [query.tier for query in store.queries] == [2, 1]
    assert len(calls) == 2
    assert calls[1]["tier"] == DistillationConfig(
        llm_config=object(),
        embedding_config=object(),
    ).evolution_tier
    assert store.personality_context_calls == 1
    assert store.write_calls == []
    assert engine._read_run_metadata().last_t2_to_t3_run is None
    assert engine._is_consolidation_locked() is False


def test_criterion_feedback_metrics_ignore_events_without_criteria() -> None:
    metrics = _criterion_feedback_metrics(
        [
            EvolutionNote("feedback-a", importance=0.9),
            EvolutionNote("feedback-b", importance=0.6, tags=["criterion:friction"]),
        ]
    )

    assert [metric.criterion_name for metric in metrics] == ["friction"]
