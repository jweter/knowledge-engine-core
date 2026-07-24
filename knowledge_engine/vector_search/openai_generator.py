"""External-API `EmbeddingGenerator` targeting the OpenAI embeddings endpoint.

Uses stdlib `urllib` rather than the `openai` SDK or `requests`, matching the
transport pattern already established for every other outbound HTTP call in
this project (`knowledge_engine/ncbi_http.py`, `knowledge_engine/crossref_http.py`,
`knowledge_engine/google_drive_http.py`): a bounded, host-allowlisted, HTTPS-only
transport with a dependency-injected opener for deterministic tests. This is
option 2 from `docs/phase3_design.md`'s embedding-generation decision --
corpus text is sent to a third party over the network, a materially
different trust posture than the read-only NCBI/Crossref/PMC fetches
already in use.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from email.message import Message
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_OPENAI_API_HOST = "api.openai.com"
_OPENAI_EMBEDDINGS_URL = f"https://{_OPENAI_API_HOST}/v1/embeddings"

_KNOWN_MODEL_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_MAX_RESPONSE_BYTES = 10_000_000


class OpenAiEmbeddingError(RuntimeError):
    """Sanitized OpenAI embeddings transport failure."""


class HttpResponse(Protocol):
    headers: Message
    status: int

    def read(self) -> bytes: ...

    def __enter__(self) -> HttpResponse: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


OpenUrl = Callable[[Request], HttpResponse]


class OpenAiEmbeddingGenerator:
    """`EmbeddingGenerator` backed by OpenAI's `/v1/embeddings` endpoint."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "text-embedding-3-small",
        opener: OpenUrl | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key or api_key != api_key.strip():
            raise OpenAiEmbeddingError("An OpenAI API key is required.")
        if model not in _KNOWN_MODEL_DIMENSIONS:
            known = ", ".join(sorted(_KNOWN_MODEL_DIMENSIONS))
            raise OpenAiEmbeddingError(f"Unknown OpenAI embedding model {model!r}. Known: {known}.")
        self._api_key = api_key
        self._model = model
        self._opener = opener or _default_opener(timeout_seconds)

    @property
    def model_id(self) -> str:
        return f"openai:{self._model}"

    @property
    def dimension(self) -> int:
        return _KNOWN_MODEL_DIMENSIONS[self._model]

    def generate(self, text: str) -> tuple[float, ...]:
        if not text or not text.strip():
            raise OpenAiEmbeddingError("Cannot generate an embedding for empty text.")

        body = json.dumps({"input": text, "model": self._model}).encode("utf-8")
        request = Request(
            _OPENAI_EMBEDDINGS_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self._opener(request) as response:
                raw = _read_bounded(response)
        except HTTPError as error:
            raise OpenAiEmbeddingError(
                f"OpenAI embeddings request failed with status {error.code}."
            ) from None
        except URLError:
            raise OpenAiEmbeddingError("OpenAI embeddings request failed.") from None

        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise OpenAiEmbeddingError("OpenAI returned an invalid response.") from None

        vector = _extract_embedding(payload)
        if len(vector) != self.dimension:
            raise OpenAiEmbeddingError(
                f"OpenAI returned a {len(vector)}-dimension vector, expected {self.dimension}."
            )
        return vector


def _default_opener(timeout_seconds: float) -> OpenUrl:
    def _open(request: Request) -> HttpResponse:
        return cast(HttpResponse, urlopen(request, timeout=timeout_seconds))

    return _open


def _read_bounded(response: HttpResponse) -> bytes:
    body = response.read()
    if len(body) > _MAX_RESPONSE_BYTES:
        raise OpenAiEmbeddingError("OpenAI response exceeded the configured size limit.")
    return body


def _extract_embedding(payload: object) -> tuple[float, ...]:
    if not isinstance(payload, dict):
        raise OpenAiEmbeddingError("OpenAI returned an invalid response.")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise OpenAiEmbeddingError("OpenAI returned an invalid response.")
    first = data[0]
    if not isinstance(first, dict):
        raise OpenAiEmbeddingError("OpenAI returned an invalid response.")
    embedding = first.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise OpenAiEmbeddingError("OpenAI returned an invalid response.")
    if not all(isinstance(component, int | float) for component in embedding):
        raise OpenAiEmbeddingError("OpenAI returned an invalid response.")
    return tuple(float(component) for component in embedding)
