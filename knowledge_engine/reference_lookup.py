"""Live background-grounding lookup against Wikipedia's REST summary API.

M41 builds the first slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched: a term or mechanism a
paper's claim text names (e.g. "GLP-1 receptor agonism", "SGLT2
inhibitor") has no equivalent grounding available anywhere in this
project's extraction pipeline today. This module looks such a term up
live against Wikipedia's public REST summary API
(https://en.wikipedia.org/api/rest_v1/page/summary/{term}) and returns
its plain-language description -- never evidence, never routed through
`EvidenceRecord` promotion, exactly the same "background context, not a
citable finding" boundary the design doc drew.

Chosen as the first source (over RxNorm/MeSH/PubChem, the design doc's
other candidates) because it needs no API key, has one well-known
response shape, and its content is under CC BY-SA -- a license family
`license_rules.py` already recognizes -- while still covering any
scientific term, not just drug names. Live lookup, not a stored corpus:
sidesteps the storage and per-title licensing decisions a stored-textbook
approach would require (see the design doc's "third option" section).
`retrieved_at`, `page_last_modified`, `revision`, and `permanent_url` are
recorded on every result so a future consumer needing this lookup's own
reproducibility (e.g. citing it as part of extraction provenance) has the
ordinary engineering hook the design doc named -- caching or snapshotting
the response actually used -- without this module needing to guess that
need in advance. `page_last_modified`/`source_url` alone are not enough
for that: `page_last_modified` is only second-resolution (two rapid edits
can share a timestamp) and `source_url` is Wikipedia's canonical page URL,
which always shows the *current* revision, not the one this lookup
actually returned. `revision` (Wikipedia's own stable revision ID) and
`permanent_url` (`{source_url}?oldid={revision}`, verified to resolve)
pin down the exact content this result reflects.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.client import IncompleteRead
from typing import Protocol
from urllib.parse import quote

from knowledge_engine.reference_lookup_http import TransportResponse

WIKIPEDIA_SUMMARY_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
WIKIPEDIA_CONTENT_LICENSE = "CC BY-SA"
"""Wikipedia's standard text-content license per the Wikimedia Foundation's
Terms of Use. Exact version terms are Wikimedia's to state authoritatively;
this project records the license family (the same one `license_rules.py`
already recognizes) rather than asserting a specific version number here."""

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ReferenceLookupError(RuntimeError):
    """Sanitized provider, response, or input failure."""


class GetTransport(Protocol):
    """Structural transport interface used by the lookup service."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


@dataclass(frozen=True)
class ReferenceLookupResult:
    """One term's background-grounding lookup outcome.

    Background context only -- `found=True` never means "this is
    evidence," only "Wikipedia has an article for this term." A caller
    deciding whether a term's meaning is relevant to a specific paper's
    claim is a human or future-reasoning-layer judgment this module does
    not make.
    """

    term: str
    found: bool
    title: str | None
    description: str | None
    extract: str | None
    page_type: str | None
    source_url: str | None
    revision: str | None
    permanent_url: str | None
    license: str | None
    page_last_modified: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class ReferenceLookupService:
    """Look up a term's plain-language grounding without asserting it as evidence."""

    def __init__(
        self,
        transport: GetTransport,
        *,
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 5_000_000,
        request_interval_seconds: float = 0.2,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if request_interval_seconds < 0:
            raise ValueError("Reference lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("Reference lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("Reference lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, term: str) -> ReferenceLookupResult:
        """Return one term's grounding, or `found=False` if Wikipedia has no article."""

        normalized = term.strip()
        if not normalized:
            raise ValueError("Term must not be empty.")

        url = f"{WIKIPEDIA_SUMMARY_API_URL}/{quote(normalized, safe='')}"
        response = self._get(url)
        retrieved_at = datetime.now(UTC).isoformat()
        if response.status_code == 404:
            return ReferenceLookupResult(
                term=normalized,
                found=False,
                title=None,
                description=None,
                extract=None,
                page_type=None,
                source_url=None,
                revision=None,
                permanent_url=None,
                license=None,
                page_last_modified=None,
                retrieved_at=retrieved_at,
            )
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReferenceLookupError("Wikipedia returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise ReferenceLookupError("Wikipedia returned malformed JSON.")

        return _parse_result(normalized, value, retrieved_at=retrieved_at)

    def _get(self, url: str) -> TransportResponse:
        for attempt in range(self.max_attempts):
            if attempt == 0:
                if self._request_count and self.request_interval_seconds:
                    self.sleep(self.request_interval_seconds)
            elif self.retry_backoff_seconds:
                self.sleep(self.retry_backoff_seconds * (2 ** (attempt - 1)))
            self._request_count += 1
            try:
                response = self.transport.get(
                    url=url,
                    headers=DEFAULT_HEADERS,
                    timeout_seconds=self.timeout_seconds,
                    max_response_bytes=self.max_response_bytes,
                )
            except (IncompleteRead, OSError, TimeoutError) as exc:
                if attempt + 1 == self.max_attempts:
                    raise ReferenceLookupError(
                        f"Reference lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code in (200, 404):
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise ReferenceLookupError(
                    "Reference lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise ReferenceLookupError("Reference lookup request retry state was invalid.")


def _parse_result(term: str, raw: dict[str, object], *, retrieved_at: str) -> ReferenceLookupResult:
    title = _optional_string(raw, "title")
    if title is None:
        raise ReferenceLookupError("Wikipedia response was missing required evidence.")

    content_urls = raw.get("content_urls")
    source_url = None
    if isinstance(content_urls, dict):
        desktop = content_urls.get("desktop")
        if isinstance(desktop, dict):
            source_url = _optional_string(desktop, "page")

    revision = _optional_string(raw, "revision")
    permanent_url = f"{source_url}?oldid={revision}" if source_url and revision else None

    return ReferenceLookupResult(
        term=term,
        found=True,
        title=title,
        description=_optional_string(raw, "description"),
        extract=_optional_string(raw, "extract"),
        page_type=_optional_string(raw, "type"),
        source_url=source_url,
        revision=revision,
        permanent_url=permanent_url,
        license=WIKIPEDIA_CONTENT_LICENSE,
        page_last_modified=_optional_string(raw, "timestamp"),
        retrieved_at=retrieved_at,
    )


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ReferenceLookupError("Wikipedia response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
