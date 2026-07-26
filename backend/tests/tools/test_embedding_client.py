from types import SimpleNamespace

import pytest

from src.tools.embedding_client import (
    EmbeddingCallBlocked,
    EmbeddingClient,
    EmbeddingClientError,
)
from src.tools.embed_document_chunks import (
    chunk_embedding_input_hash,
    normalize_embedding_input,
)


class FakeAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str = "provider error"):
        super().__init__(message)
        self.status_code = status_code


def _response(vectors=None, model="BAAI/bge-m3"):
    return SimpleNamespace(
        model=model,
        data=[
            SimpleNamespace(embedding=vector, index=index)
            for index, vector in enumerate(vectors or [[0.1] * 1024])
        ],
        usage=SimpleNamespace(prompt_tokens=8, total_tokens=8),
    )


def test_embedding_client_blocks_when_disabled():
    calls = []
    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(EmbeddingCallBlocked):
        client.embed_texts(["text"], embedding_enabled=False)

    assert calls == []


def test_embedding_client_sends_bge_m3_request_without_dimensions():
    calls = []

    def fake_embeddings_create(**kwargs):
        calls.append(kwargs)
        return _response([[0.2] * 1024])

    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=fake_embeddings_create,
        sleep_fn=lambda _seconds: None,
    )

    result = client.embed_texts(["温室气体排放"], embedding_enabled=True)

    assert result.model == "BAAI/bge-m3"
    assert result.embeddings == [[0.2] * 1024]
    assert result.usage == {"prompt_tokens": 8, "total_tokens": 8}
    assert len(calls) == 1
    assert calls[0]["model"] == "BAAI/bge-m3"
    assert calls[0]["input"] == ["温室气体排放"]
    assert calls[0]["encoding_format"] == "float"
    assert "dimensions" not in calls[0]


@pytest.mark.parametrize("status_code", [429, 503, 504])
def test_embedding_client_retries_transient_provider_errors(status_code):
    calls = []

    def fail(**kwargs):
        calls.append(kwargs)
        raise FakeAPIError(status_code)

    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        embedding_factory=fail,
        max_retries=2,
        retry_delay_seconds=0,
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(EmbeddingClientError) as exc_info:
        client.embed_texts(["text"], embedding_enabled=True)

    assert exc_info.value.retry_count == 2
    assert len(calls) == 3


def test_embedding_client_rejects_unexpected_dimension():
    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        expected_dim=1024,
        embedding_factory=lambda **_kwargs: _response([[0.1] * 3]),
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(EmbeddingClientError) as exc_info:
        client.embed_texts(["text"], embedding_enabled=True)

    assert exc_info.value.error_code == "embedding_dimension_mismatch"


def test_embedding_client_rejects_response_count_mismatch():
    client = EmbeddingClient(
        model="BAAI/bge-m3",
        api_key="key",
        base_url="https://api.siliconflow.cn/v1",
        expected_dim=1024,
        embedding_factory=lambda **_kwargs: _response([[0.1] * 1024]),
        sleep_fn=lambda _seconds: None,
    )

    with pytest.raises(EmbeddingClientError) as exc_info:
        client.embed_texts(["first", "second"], embedding_enabled=True)

    assert exc_info.value.error_code == "embedding_count_mismatch"


def test_chunk_embedding_input_hash_changes_with_text_and_model():
    first = chunk_embedding_input_hash(
        "文本",
        provider="siliconflow",
        model="BAAI/bge-m3",
    )
    same = chunk_embedding_input_hash(
        "文本",
        provider="siliconflow",
        model="BAAI/bge-m3",
    )
    different_text = chunk_embedding_input_hash(
        "另一个文本",
        provider="siliconflow",
        model="BAAI/bge-m3",
    )
    different_model = chunk_embedding_input_hash(
        "文本",
        provider="siliconflow",
        model="BAAI/bge-large-zh-v1.5",
    )

    assert first == same
    assert len(first) == 64
    assert first != different_text
    assert first != different_model


def test_normalize_embedding_input_is_deterministic_and_bounded():
    normalized = normalize_embedding_input(
        "  温室气体\n\n排放  ",
        max_chars=6,
    )

    assert normalized == "温室气体 排"
    assert len(normalized) == 6
