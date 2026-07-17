"""Crossref provider orchestration with an injected, bounded transport."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Protocol
from urllib.parse import quote

from knowledge_engine.crossref import parse_crossref_work
from knowledge_engine.metadata_enrichment import (
    DiagnosticCode,
    MetadataProviderResult,
    MetadataQuery,
    ProviderDiagnostic,
)

CROSSREF_BASE_URL = "https://api.crossref.org/works/"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
DEFAULT_USER_AGENT = "knowledge-engine-core/0.2 metadata-preview"


@dataclass(frozen=True)
class TransportResponse:
    """Bounded HTTP response returned by an injected transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


class CrossrefTransport(Protocol):
    """Minimal transport contract required by the Crossref provider."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response without following unsafe redirects."""


class CrossrefProvider:
    """Metadata provider that classifies transport outcomes deterministically."""

    def __init__(
        self,
        *,
        transport: CrossrefTransport,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Crossref timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("Crossref response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("Crossref User-Agent must not be blank.")

        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent

    @property
    def name(self) -> str:
        return "crossref"

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        normalized_doi = query.normalized_doi
        url = f"{CROSSREF_BASE_URL}{quote(normalized_doi, safe='')}"
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
        except TimeoutError:
            return _diagnostic("timeout", "Crossref request timed out.", retryable=True)
        except OSError:
            return _diagnostic(
                "transport_error",
                "Crossref request failed before a response was received.",
                retryable=True,
            )

        if len(response.body) > self._max_response_bytes:
            return _diagnostic(
                "oversized_response",
                "Crossref response exceeded the configured size limit.",
            )
        if response.status_code == 404:
            return _diagnostic("no_match", "Crossref did not return a record for this DOI.")
        if response.status_code == 429:
            return _diagnostic("rate_limited", "Crossref rate limit was reached.", retryable=True)
        if 500 <= response.status_code <= 599:
            return _diagnostic(
                "provider_unavailable",
                "Crossref is temporarily unavailable.",
                retryable=True,
            )
        if response.status_code < 200 or response.status_code >= 300:
            return _diagnostic(
                "provider_unavailable",
                "Crossref returned an unsupported HTTP status.",
            )

        try:
            payload = json.loads(response.body)
        except (JSONDecodeError, UnicodeDecodeError):
            return _diagnostic("malformed_response", "Crossref returned malformed JSON.")

        return parse_crossref_work(payload, query=query, retrieved_at=self._clock())


def _diagnostic(
    code: DiagnosticCode,
    message: str,
    *,
    retryable: bool = False,
) -> MetadataProviderResult:
    return MetadataProviderResult(
        diagnostics=(
            ProviderDiagnostic(
                provider="crossref",
                code=code,
                message=message,
                retryable=retryable,
            ),
        )
    )
