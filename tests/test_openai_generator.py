from __future__ import annotations

import json
from email.message import Message
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from knowledge_engine.vector_search import OpenAiEmbeddingError, OpenAiEmbeddingGenerator
from knowledge_engine.vector_search.openai_generator import OpenUrl

_SMALL_DIMENSION = 1536


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.headers = Message()
        self.status = 200

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


def _opener_returning(payload: dict[str, object]) -> tuple[list[Request], OpenUrl]:
    requests: list[Request] = []

    def opener(request: Request) -> _FakeResponse:
        requests.append(request)
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    return requests, opener


def _embedding_payload(dimension: int = _SMALL_DIMENSION) -> dict[str, object]:
    return {"data": [{"embedding": [0.001 * i for i in range(dimension)]}]}


def test_model_id_and_dimension_reflect_the_configured_model() -> None:
    _, opener = _opener_returning(_embedding_payload())
    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    assert generator.model_id == "openai:text-embedding-3-small"
    assert generator.dimension == _SMALL_DIMENSION


def test_generate_sends_bearer_auth_and_returns_the_embedding() -> None:
    requests, opener = _opener_returning(_embedding_payload())
    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    vector = generator.generate("some paper text")

    assert len(vector) == _SMALL_DIMENSION
    assert vector[1] == pytest.approx(0.001)
    assert len(requests) == 1
    assert requests[0].get_header("Authorization") == "Bearer sk-test"
    sent_data = requests[0].data
    assert isinstance(sent_data, bytes)
    sent_body = json.loads(sent_data)
    assert sent_body == {"input": "some paper text", "model": "text-embedding-3-small"}


def test_generate_rejects_empty_text() -> None:
    _, opener = _opener_returning(_embedding_payload())
    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="empty text"):
        generator.generate("   ")


def test_rejects_empty_api_key() -> None:
    with pytest.raises(OpenAiEmbeddingError, match="API key is required"):
        OpenAiEmbeddingGenerator(api_key="")


def test_rejects_unknown_model() -> None:
    with pytest.raises(OpenAiEmbeddingError, match="Unknown OpenAI embedding model"):
        OpenAiEmbeddingGenerator(api_key="sk-test", model="not-a-real-model")


def test_rejects_a_dimension_mismatch_from_the_api() -> None:
    _, opener = _opener_returning(_embedding_payload(dimension=3))
    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="3-dimension vector, expected 1536"):
        generator.generate("text")


def test_rejects_an_invalid_json_response() -> None:
    def opener(request: Request) -> _FakeResponse:
        return _FakeResponse(b"not json")

    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="invalid response"):
        generator.generate("text")


def test_rejects_a_response_missing_the_embedding_field() -> None:
    def opener(request: Request) -> _FakeResponse:
        return _FakeResponse(json.dumps({"data": [{}]}).encode("utf-8"))

    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="invalid response"):
        generator.generate("text")


def test_wraps_an_http_error() -> None:
    def opener(request: Request) -> _FakeResponse:
        raise HTTPError(request.full_url, 401, "Unauthorized", Message(), None)

    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="status 401"):
        generator.generate("text")


def test_wraps_a_url_error() -> None:
    def opener(request: Request) -> _FakeResponse:
        raise URLError("no network")

    generator = OpenAiEmbeddingGenerator(api_key="sk-test", opener=opener)

    with pytest.raises(OpenAiEmbeddingError, match="request failed"):
        generator.generate("text")
