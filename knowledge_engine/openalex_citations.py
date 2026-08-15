"""Bounded OpenAlex citation traversal with explicit provenance and failure state."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from json import JSONDecodeError
from urllib.parse import urlencode

from knowledge_engine.citation_discovery import (
    CitationDirection,
    CitationEdge,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import ProviderOutcome, ProviderStatus
from knowledge_engine.openalex_provider import (
    OPENALEX_WORKS_URL,
    DEFAULT_MAX_RESPONSE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    OpenAlexTransport,
    ResponseTooLargeError,
)

MAX_CITATION_TRAVERSAL = 100


class OpenAlexCitationProvider:
    """Traverse OpenAlex reference/citation edges without hiding partial failure."""

    def __init__(
        self,
        *,
        transport: OpenAlexTransport,
        api_key: str | None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("OpenAlex timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("OpenAlex response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("OpenAlex User-Agent must not be blank.")
        if api_key is not None and not api_key.strip():
            raise ValueError("OpenAlex API key must not be blank when provided.")

        self._transport = transport
        self._api_key = api_key.strip() if api_key is not None else None
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent

    @property
    def configured(self) -> bool:
        return self._api_key is not None

    def references(self, seed_id: str, *, limit: int = 25) -> CitationTraversalResult:
        """Return works directly referenced by the OpenAlex seed work."""
        seed = _normalize_openalex_id(seed_id)
        _validate_limit(limit)
        if self._api_key is None:
            return _disabled(seed, CitationDirection.REFERENCES, limit)

        query = urlencode(
            {
                "select": "id,referenced_works",
                "api_key": self._api_key,
            }
        )
        response = self._request(f"{OPENALEX_WORKS_URL}/{seed}?{query}")
        if isinstance(response, ProviderStatus):
            return _result(seed, CitationDirection.REFERENCES, limit, response)

        try:
            payload = json.loads(response)
        except (JSONDecodeError, UnicodeDecodeError):
            return _failed(seed, CitationDirection.REFERENCES, limit, "malformed_response")
        if not isinstance(payload, Mapping):
            return _failed(seed, CitationDirection.REFERENCES, limit, "malformed_response")

        raw_refs = payload.get("referenced_works")
        if not isinstance(raw_refs, list):
            return _failed(seed, CitationDirection.REFERENCES, limit, "malformed_response")

        observed_at = self._clock().astimezone(UTC).isoformat()
        targets: list[str] = []
        for raw in raw_refs:
            if not isinstance(raw, str):
                continue
            try:
                normalized = _normalize_openalex_id(raw)
            except ValueError:
                continue
            if normalized not in targets:
                targets.append(normalized)
            if len(targets) >= limit:
                break

        edges = tuple(
            CitationEdge(
                provider="openalex",
                source_id=seed,
                target_id=target,
                observed_at=observed_at,
            )
            for target in targets
        )
        return _success(seed, CitationDirection.REFERENCES, limit, edges)

    def cited_by(self, seed_id: str, *, limit: int = 25) -> CitationTraversalResult:
        """Return works that directly cite the OpenAlex seed work."""
        seed = _normalize_openalex_id(seed_id)
        _validate_limit(limit)
        if self._api_key is None:
            return _disabled(seed, CitationDirection.CITED_BY, limit)

        query = urlencode(
            {
                "filter": f"cites:{seed}",
                "select": "id",
                "per_page": str(limit),
                "api_key": self._api_key,
            }
        )
        response = self._request(f"{OPENALEX_WORKS_URL}?{query}")
        if isinstance(response, ProviderStatus):
            return _result(seed, CitationDirection.CITED_BY, limit, response)

        try:
            payload = json.loads(response)
        except (JSONDecodeError, UnicodeDecodeError):
            return _failed(seed, CitationDirection.CITED_BY, limit, "malformed_response")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("results"), list):
            return _failed(seed, CitationDirection.CITED_BY, limit, "malformed_response")

        observed_at = self._clock().astimezone(UTC).isoformat()
        sources: list[str] = []
        for item in payload["results"]:
            if not isinstance(item, Mapping) or not isinstance(item.get("id"), str):
                continue
            try:
                normalized = _normalize_openalex_id(item["id"])
            except ValueError:
                continue
            if normalized not in sources:
                sources.append(normalized)
            if len(sources) >= limit:
                break

        edges = tuple(
            CitationEdge(
                provider="openalex",
                source_id=source,
                target_id=seed,
                observed_at=observed_at,
            )
            for source in sources
        )
        return _success(seed, CitationDirection.CITED_BY, limit, edges)

    def _request(self, url: str) -> bytes | ProviderStatus:
        headers = {
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }
        try:
            response = self._transport.get(
                url=url,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
                max_response_bytes=self._max_response_bytes,
            )
        except ResponseTooLargeError:
            return _status(ProviderOutcome.FAILED, True, "oversized_response")
        except TimeoutError:
            return _status(ProviderOutcome.UNAVAILABLE, True, "timeout")
        except OSError:
            return _status(ProviderOutcome.UNAVAILABLE, True, "transport_error")

        if len(response.body) > self._max_response_bytes:
            return _status(ProviderOutcome.FAILED, True, "oversized_response")
        if response.status_code == 404:
            return _status(ProviderOutcome.EMPTY, True)
        if response.status_code == 429:
            return _status(ProviderOutcome.RATE_LIMITED, True, "rate_limited")
        if response.status_code in {401, 403}:
            return _status(ProviderOutcome.FAILED, True, "authentication_failed")
        if 500 <= response.status_code <= 599:
            return _status(ProviderOutcome.UNAVAILABLE, True, "provider_unavailable")
        if response.status_code < 200 or response.status_code >= 300:
            return _status(ProviderOutcome.FAILED, True, "unsupported_http_status")
        return response.body


def _normalize_openalex_id(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if normalized.lower().startswith("https://openalex.org/"):
        normalized = normalized.rsplit("/", 1)[-1]
    if len(normalized) >= 2 and normalized[0].upper() == "W" and normalized[1:].isdigit():
        return f"W{normalized[1:]}"
    raise ValueError("Citation traversal requires an OpenAlex work ID.")


def _validate_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_CITATION_TRAVERSAL:
        raise ValueError(
            f"Citation traversal limit must be between 1 and {MAX_CITATION_TRAVERSAL}."
        )


def _status(
    outcome: ProviderOutcome,
    attempted: bool,
    reason: str | None = None,
    *,
    result_count: int = 0,
) -> ProviderStatus:
    return ProviderStatus(
        provider="openalex",
        outcome=outcome,
        attempted=attempted,
        result_count=result_count,
        reason=reason,
    )


def _result(
    seed: str,
    direction: CitationDirection,
    limit: int,
    status: ProviderStatus,
    edges: tuple[CitationEdge, ...] = (),
) -> CitationTraversalResult:
    return CitationTraversalResult(
        provider="openalex",
        seed_id=seed,
        direction=direction,
        requested_limit=limit,
        provider_status=status,
        edges=edges,
    )


def _disabled(seed: str, direction: CitationDirection, limit: int) -> CitationTraversalResult:
    return _result(
        seed,
        direction,
        limit,
        _status(ProviderOutcome.DISABLED, False, "missing_api_key"),
    )


def _failed(
    seed: str,
    direction: CitationDirection,
    limit: int,
    reason: str,
) -> CitationTraversalResult:
    return _result(seed, direction, limit, _status(ProviderOutcome.FAILED, True, reason))


def _success(
    seed: str,
    direction: CitationDirection,
    limit: int,
    edges: tuple[CitationEdge, ...],
) -> CitationTraversalResult:
    outcome = ProviderOutcome.SUCCESS if edges else ProviderOutcome.EMPTY
    return _result(
        seed,
        direction,
        limit,
        _status(outcome, True, result_count=len(edges)),
        edges,
    )
