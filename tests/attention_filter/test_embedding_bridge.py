from dataclasses import dataclass

import numpy as np
import pytest

from phosphene.attention_filter import AttentionFilterConfig
from phosphene.attention_filter.filter import _embed_content


@dataclass
class EmbeddingResult:
    vectors: list[np.ndarray]


def make_config(**overrides: object) -> AttentionFilterConfig:
    values = {
        "llm_config": object(),
        "embedding_config": object(),
    }
    values.update(overrides)
    return AttentionFilterConfig(**values)


def test_embedding_bridge_passes_content_and_embedding_config_to_callable() -> None:
    calls = []
    embedding_config = object()
    embedding = np.array([0.1, 0.2])

    def fake_embed(texts: list[str], config: object) -> EmbeddingResult:
        calls.append((texts, config))
        return EmbeddingResult(vectors=[embedding])

    result = _embed_content(
        "specific source text",
        make_config(embedding_config=embedding_config),
        embedding_callable=fake_embed,
    )

    assert calls == [(["specific source text"], embedding_config)]
    assert np.array_equal(result, embedding)


def test_embedding_bridge_propagates_embedding_errors_unchanged() -> None:
    class EmbeddingFailure(Exception):
        pass

    failure = EmbeddingFailure("model unavailable")

    def failing_embed(texts: list[str], config: object) -> EmbeddingResult:
        raise failure

    with pytest.raises(EmbeddingFailure) as exc_info:
        _embed_content("text", make_config(), embedding_callable=failing_embed)

    assert exc_info.value is failure
