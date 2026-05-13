import json
from dataclasses import dataclass

from phosphene.distillation.engine import (
    _build_assertion_cache_request,
    _build_cluster_summary_request,
    _build_reflection_request,
    _CriterionFeedbackMetric,
    _Tier2EvolutionInput,
    _make_raptor_embedder,
    _make_raptor_summarizer,
    _toolkit_cluster,
    _toolkit_complete,
    _toolkit_embed,
)


@dataclass
class FakeEmbeddingResult:
    vectors: list[list[float]]


def test_distillation_toolkit_boundaries_are_private_import_seams() -> None:
    assert callable(_toolkit_embed)
    assert callable(_toolkit_complete)
    assert callable(_toolkit_cluster)


def test_raptor_summarizer_uses_llm_config_tier_and_cluster_summary_prompt() -> None:
    calls: list[dict[str, object]] = []

    def fake_complete(**kwargs: object) -> str:
        calls.append(dict(kwargs))
        return "pattern summary"

    summarizer = _make_raptor_summarizer(
        llm_config="llm-config",
        tier="quality",
        llm_complete_callable=fake_complete,
    )

    assert summarizer(["first observation", "second observation"]) == "pattern summary"
    assert calls == [
        {
            "messages": _build_cluster_summary_request(
                ["first observation", "second observation"]
            ),
            "config": "llm-config",
            "tier": "quality",
        }
    ]

    payload = json.loads(calls[0]["messages"][1]["content"])
    assert payload["task"] == "distill_tier1_cluster_summary"
    assert payload["observations"] == ["first observation", "second observation"]
    assert "Tier 2 pattern" in payload["instructions"]


def test_raptor_embedder_uses_embedding_config_and_returns_vectors() -> None:
    calls: list[tuple[list[str], object]] = []

    def fake_embed(texts: list[str], config: object) -> FakeEmbeddingResult:
        calls.append((texts, config))
        return FakeEmbeddingResult(vectors=[[0.1, 0.2], [0.3, 0.4]])

    embedder = _make_raptor_embedder(
        embedding_config="embedding-config",
        embedding_callable=fake_embed,
    )

    assert embedder(["summary one", "summary two"]) == [[0.1, 0.2], [0.3, 0.4]]
    assert calls == [(["summary one", "summary two"], "embedding-config")]


def test_raptor_embedder_preserves_vector_like_return_without_vectors_attribute() -> None:
    def fake_embed(_texts: list[str], _config: object) -> list[list[float]]:
        return [[0.5, 0.6]]

    embedder = _make_raptor_embedder(
        embedding_config=object(),
        embedding_callable=fake_embed,
    )

    assert embedder(["summary"]) == [[0.5, 0.6]]


def test_assertion_cache_prompt_requests_strict_json_payload() -> None:
    messages = _build_assertion_cache_request("A cluster summary.")

    assert messages[0]["role"] == "user"
    payload = json.loads(messages[0]["content"])
    assert payload["task"] == "extract_distillation_cluster_assertions"
    assert payload["cluster_summary"] == "A cluster summary."
    assert '"assertions"' in payload["instructions"]
    assert "Return only JSON" in payload["instructions"]


def test_reflection_prompt_requests_strict_json_audit_payload() -> None:
    @dataclass
    class PatternNote:
        note_id: str
        content: str
        cluster_group: str
        importance: float
        unresolvedness: float
        tags: list[str]

    messages = _build_reflection_request(
        _Tier2EvolutionInput(
            pattern_notes=[
                PatternNote(
                    note_id="pattern-a",
                    content="A pattern summary.",
                    cluster_group="cluster-a",
                    importance=0.7,
                    unresolvedness=0.4,
                    tags=["distilled-pattern"],
                )
            ],
            feedback_events=[],
            feedback_metrics=[
                _CriterionFeedbackMetric(
                    criterion_name="friction",
                    feedback_count=3,
                    engaged_count=2,
                    engagement_rate=2 / 3,
                    mean_engagement=0.6,
                )
            ],
        )
    )

    assert messages[0]["role"] == "user"
    payload = json.loads(messages[0]["content"])
    assert payload["task"] == "distill_t2_to_t3_reflection"
    assert payload["patterns"][0]["note_id"] == "pattern-a"
    assert payload["feedback_metrics"][0]["criterion_name"] == "friction"
    assert '"insights"' in payload["instructions"]
    assert "Do not prescribe file edits" in payload["instructions"]
