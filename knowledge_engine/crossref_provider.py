"""Crossref provider orchestration with an injected, bounded transport."""

from __future__ import annotations

import dataclasses
import json
import time
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

# Issue #433 item 2's final per-provider slice, following
# semantic_scholar_provider.py/openalex_provider.py/arxiv_provider.py's
# established pattern: a bounded, exponential-backoff retry for transient
# failures only. `DEFAULT_MAX_ATTEMPTS` counts the *first* attempt plus every
# retry (3 == up to 2 retries). Only a genuinely transient condition -- an
# HTTP 429 rate-limit response, a 5xx provider-unavailable response, a
# request timeout, or a connection-level transport error -- is retried;
# every other outcome (a 404 "no match", an oversized/malformed response, or
# any other unsupported HTTP status) is a real result and is never retried,
# matching `CrossrefProvider.lookup()`'s own pre-existing
# `ProviderDiagnostic.retryable` classification for each of those codes.
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 1.0


class ResponseTooLargeError(OSError):
    """Raised when a provider response exceeds the configured byte limit."""


@dataclass(frozen=True)
class TransportResponse:
    """Bounded HTTP response returned by an injected transport."""

    status_code: int
    body: bytes
    headers: Mapping[str, str]


@dataclass(frozen=True)
class _TransientFailure:
    """A retry-eligible transport outcome, or a terminal one classified early.

    ``retryable`` distinguishes the two: `True` for the four transient
    conditions (429, 5xx, timeout, transport error) the retry loop may act
    on, `False` for an oversized response caught before any status code was
    even available to classify (never retried, matching the pre-existing
    non-retryable `oversized_response` diagnostic).
    """

    code: DiagnosticCode
    message: str
    retryable: bool
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class _RequestOutcome:
    """Result of one logical (possibly retried) request.

    Exactly one of ``response``/``failure`` is set. ``retry_attempt_count`` and
    ``rate_limited_observed`` describe the whole retry loop, not just the final
    attempt, so `lookup()` reports accurate retry/rate-limit facts regardless
    of which branch it takes.
    """

    response: TransportResponse | None
    failure: _TransientFailure | None
    retry_attempt_count: int
    rate_limited_observed: bool


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
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Crossref timeout must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("Crossref response limit must be positive.")
        if not user_agent.strip():
            raise ValueError("Crossref User-Agent must not be blank.")
        if max_attempts < 1:
            raise ValueError("Crossref max_attempts must be at least 1.")
        if retry_backoff_seconds < 0:
            raise ValueError("Crossref retry backoff must not be negative.")

        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._user_agent = user_agent
        self._max_attempts = max_attempts
        self._retry_backoff_seconds = retry_backoff_seconds
        self._sleep = sleep or time.sleep

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

        outcome = self._request_with_retries(url=url, headers=headers)
        if outcome.failure is not None:
            return _diagnostic(
                outcome.failure.code,
                outcome.failure.message,
                retryable=outcome.failure.retryable,
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            )
        response = outcome.response
        assert response is not None

        if len(response.body) > self._max_response_bytes:
            return _diagnostic(
                "oversized_response",
                "Crossref response exceeded the configured size limit.",
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            )
        if response.status_code == 404:
            return _diagnostic(
                "no_match",
                "Crossref did not return a record for this DOI.",
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            )
        if response.status_code < 200 or response.status_code >= 300:
            return _diagnostic(
                "provider_unavailable",
                "Crossref returned an unsupported HTTP status.",
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            )

        try:
            payload = json.loads(response.body)
        except (JSONDecodeError, UnicodeDecodeError):
            return _diagnostic(
                "malformed_response",
                "Crossref returned malformed JSON.",
                retry_attempt_count=outcome.retry_attempt_count,
                rate_limited_observed=outcome.rate_limited_observed,
            )

        result = parse_crossref_work(payload, query=query, retrieved_at=self._clock())
        return dataclasses.replace(
            result,
            retry_attempt_count=outcome.retry_attempt_count,
            rate_limited_observed=outcome.rate_limited_observed,
        )

    def _request_with_retries(self, *, url: str, headers: Mapping[str, str]) -> _RequestOutcome:
        """Perform one logical request, retrying transient failures in place.

        A bounded loop (`self._max_attempts` total attempts, exponential
        backoff between them via `self._sleep`) retries only a 429, a 5xx, a
        timeout, or a connection-level transport error -- never a 404, an
        oversized/malformed response, or any other unsupported HTTP status,
        all of which are real outcomes rather than a transient condition
        worth retrying. The final response or failure is returned alongside
        how many retries were actually needed and whether any attempt
        observed a rate-limit response, so `lookup()` can build an honest
        result regardless of which branch it takes.
        """

        retry_attempt_count = 0
        rate_limited_observed = False
        attempt = 0
        while True:
            attempt += 1
            attempt_result = self._attempt(url=url, headers=headers)
            if isinstance(attempt_result, TransportResponse):
                return _RequestOutcome(
                    response=attempt_result,
                    failure=None,
                    retry_attempt_count=retry_attempt_count,
                    rate_limited_observed=rate_limited_observed,
                )
            if attempt_result.code == "rate_limited":
                rate_limited_observed = True
            if attempt_result.retryable and attempt < self._max_attempts:
                retry_attempt_count += 1
                backoff_seconds = self._retry_backoff_seconds * (2 ** (attempt - 1))
                if attempt_result.retry_after_seconds is not None:
                    backoff_seconds = max(backoff_seconds, attempt_result.retry_after_seconds)
                self._sleep(backoff_seconds)
                continue
            return _RequestOutcome(
                response=None,
                failure=attempt_result,
                retry_attempt_count=retry_attempt_count,
                rate_limited_observed=rate_limited_observed,
            )

    def _attempt(
        self, *, url: str, headers: Mapping[str, str]
    ) -> TransportResponse | _TransientFailure:
        """Perform exactly one HTTP attempt and map it to a response or failure.

        Only the four transient conditions are classified here; every other
        status code (200, 404, other unsupported statuses) is returned as a
        `TransportResponse` so `lookup()`'s own existing post-response
        classification (oversized body, 404, malformed JSON) is unchanged.
        """

        try:
            response = self._transport.get(
                url=url,
                headers=headers,
                timeout_seconds=self._timeout_seconds,
                max_response_bytes=self._max_response_bytes,
            )
        except ResponseTooLargeError:
            return _TransientFailure(
                "oversized_response",
                "Crossref response exceeded the configured size limit.",
                retryable=False,
            )
        except TimeoutError:
            return _TransientFailure("timeout", "Crossref request timed out.", retryable=True)
        except OSError:
            return _TransientFailure(
                "transport_error",
                "Crossref request failed before a response was received.",
                retryable=True,
            )

        if response.status_code == 429:
            return _TransientFailure(
                "rate_limited",
                "Crossref rate limit was reached.",
                retryable=True,
                retry_after_seconds=_parse_retry_after_seconds(response.headers),
            )
        if 500 <= response.status_code <= 599:
            return _TransientFailure(
                "provider_unavailable",
                "Crossref is temporarily unavailable.",
                retryable=True,
            )
        return response


def _parse_retry_after_seconds(headers: Mapping[str, str]) -> float | None:
    """Parse a 429 response's ``Retry-After`` header, if present and a delay-seconds form.

    Only the numeric delay-seconds form is honored; a missing, non-numeric, or
    negative value returns `None` so the caller falls back to its own computed
    backoff rather than fabricating a wait time.
    """

    for key, value in headers.items():
        if key.lower() != "retry-after":
            continue
        try:
            seconds = float(value.strip())
        except ValueError:
            return None
        return seconds if seconds >= 0 else None
    return None


def _diagnostic(
    code: DiagnosticCode,
    message: str,
    *,
    retryable: bool = False,
    retry_attempt_count: int = 0,
    rate_limited_observed: bool = False,
) -> MetadataProviderResult:
    return MetadataProviderResult(
        diagnostics=(
            ProviderDiagnostic(
                provider="crossref",
                code=code,
                message=message,
                retryable=retryable,
            ),
        ),
        retry_attempt_count=retry_attempt_count,
        rate_limited_observed=rate_limited_observed,
    )
