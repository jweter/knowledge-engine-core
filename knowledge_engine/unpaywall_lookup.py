"""Review-first Unpaywall OA-location/license evidence lookup.

M36 adds Unpaywall (https://unpaywall.org) as a fourth external evidence
source, but in a deliberately different shape from M14/M34/M35's
discovery-then-adjudication pipelines. Two facts, both verified empirically
against the live API before building this module, make a topic-search
discovery pipeline the wrong design here:

- Unpaywall's `/v2/search` endpoint -- the one that would support a
  PubMed/Europe PMC/CORE-style `--query` discovery command -- returned a
  consistent `500 Internal Server Error` across multiple distinct queries
  and retries at build time (confirmed via direct `curl`, not assumed). The
  route exists (it is not a `404`), so this reads as the service being
  broken or deprecated, not a transient blip.
- Even where Unpaywall's API works reliably -- `GET /v2/{doi}`, a per-DOI
  lookup -- it returns no abstract and no scientific-scope signal beyond a
  bare title, and every URL it returns points to some third-party publisher
  or repository (there is no single "Unpaywall's own host" the way CORE has
  `core.ac.uk` or Europe PMC has `europepmc.org`). Unpaywall's real value
  here is resolving a *known* DOI's best open-access location and license,
  not minting new candidates from a topic.

This module is therefore an **evidence lookup, not a discovery-and-
adjudication pipeline**: given one or more DOIs (typically DOIs already
surfaced -- and possibly `held` -- by `pubmed_discovery.py`,
`europepmc_discovery.py`, or `core_discovery.py`), it queries Unpaywall's
official per-DOI endpoint and reports what Unpaywall knows: OA status, best
OA location, license, and every OA location it has on file, plus this
project's own `license_rule_result` (via the shared `license_rules.py`) so
a human reviewer can see at a glance whether Unpaywall's reported license
would clear this project's reusable-license bar. It makes **no**
accept/reject/hold decision of its own -- that remains the responsibility
of whichever pipeline's `held` candidate this evidence is being used to
re-examine.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from http.client import IncompleteRead
from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode

from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.unpaywall_http import TransportResponse
from knowledge_engine.utils import normalize_doi

UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_MAX_BATCH_SIZE = 100

_CC_LICENSE_TOKENS = {
    "cc-by": "CC BY",
    "cc-by-sa": "CC BY-SA",
    "cc-by-nd": "CC BY-ND",
    "cc-by-nc": "CC BY-NC",
    "cc-by-nc-sa": "CC BY-NC-SA",
    "cc-by-nc-nd": "CC BY-NC-ND",
    "cc0": "CC0",
}
"""Maps Unpaywall's real, confirmed license token format (e.g. `"cc-by"`,
lowercase and hyphenated) to the `"CC BY"`-style format
`license_rules.evaluate_license` expects. Non-CC tokens (e.g.
`"publisher-specific-oa"`, `"implied-oa"`) are passed through unchanged and
correctly evaluate as unsupported -- they are not unrestricted-reuse
licenses this project accepts."""


class UnpaywallLookupError(RuntimeError):
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
class UnpaywallLocation:
    """One OA location Unpaywall has on file for a DOI."""

    url: str
    host_type: str | None
    license: str | None
    is_best: bool


@dataclass(frozen=True)
class UnpaywallRecord:
    """Unpaywall's OA-location/license evidence for one resolved DOI."""

    title: str | None
    is_oa: bool
    oa_status: str | None
    best_oa_location_url: str | None
    best_oa_location_license: str | None
    license_rule_result: str
    oa_locations: tuple[UnpaywallLocation, ...]


@dataclass(frozen=True)
class UnpaywallLookupResult:
    """One DOI's lookup outcome: found evidence, or not in Unpaywall's index."""

    doi: str
    found: bool
    record: UnpaywallRecord | None

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class UnpaywallBatchResult:
    """Deterministic lookup output for a bounded batch of DOIs."""

    requested_count: int
    results: tuple[UnpaywallLookupResult, ...]

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        payload = {
            "requested_count": self.requested_count,
            "found_count": sum(1 for result in self.results if result.found),
            "not_found_count": sum(1 for result in self.results if not result.found),
            "results": [asdict(result) for result in self.results],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


class UnpaywallLookupService:
    """Look up per-DOI OA-location/license evidence without downloading papers."""

    def __init__(
        self,
        transport: GetTransport,
        *,
        email: str,
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 5_000_000,
        request_interval_seconds: float = 0.2,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 2.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not email.strip():
            raise ValueError("Unpaywall email must not be empty.")
        if request_interval_seconds < 0:
            raise ValueError("Unpaywall request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("Unpaywall max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("Unpaywall retry backoff must be non-negative.")
        self.transport = transport
        self.email = email.strip()
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, doi: str) -> UnpaywallLookupResult:
        """Return one DOI's evidence, or `found=False` if Unpaywall has no record."""

        normalized = normalize_doi(doi)
        if not normalized:
            raise ValueError("DOI must not be empty.")

        query = urlencode({"email": self.email})
        url = f"{UNPAYWALL_API_URL}/{quote(normalized, safe='/:')}?{query}"
        response = self._get(url)
        if response.status_code == 404:
            return UnpaywallLookupResult(doi=normalized, found=False, record=None)
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnpaywallLookupError("Unpaywall returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise UnpaywallLookupError("Unpaywall returned malformed JSON.")

        return UnpaywallLookupResult(doi=normalized, found=True, record=_parse_record(value))

    def lookup_many(self, dois: Sequence[str]) -> UnpaywallBatchResult:
        """Return a bounded batch of per-DOI evidence, one lookup per DOI."""

        if not dois:
            raise ValueError("At least one DOI is required.")
        if len(dois) > _MAX_BATCH_SIZE:
            raise ValueError(f"Batch lookups are limited to {_MAX_BATCH_SIZE} DOIs.")

        results = tuple(self.lookup(doi) for doi in dois)
        return UnpaywallBatchResult(requested_count=len(dois), results=results)

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
                    raise UnpaywallLookupError(
                        f"Unpaywall lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code in (200, 404):
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise UnpaywallLookupError(
                    "Unpaywall lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise UnpaywallLookupError("Unpaywall lookup request retry state was invalid.")


def parse_dois_file(path: Path) -> tuple[str, ...]:
    """Read a `{"dois": [...]}` JSON file of DOIs for `lookup_many`."""

    if path.is_symlink():
        raise UnpaywallLookupError("DOIs input must not be a symbolic link.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnpaywallLookupError("DOIs input is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise UnpaywallLookupError("DOIs input is not valid JSON.")
    dois = payload.get("dois")
    if not isinstance(dois, list) or not dois:
        raise UnpaywallLookupError('DOIs input must contain a non-empty "dois" array.')
    if not all(isinstance(doi, str) and doi.strip() for doi in dois):
        raise UnpaywallLookupError("DOIs input contains a malformed DOI entry.")
    return tuple(dois)


def _parse_record(raw: dict[str, object]) -> UnpaywallRecord:
    is_oa = raw.get("is_oa")
    if not isinstance(is_oa, bool):
        raise UnpaywallLookupError("Unpaywall response was missing required evidence.")

    best_url, best_license = _best_location_evidence(raw.get("best_oa_location"))
    return UnpaywallRecord(
        title=_optional_string(raw, "title"),
        is_oa=is_oa,
        oa_status=_optional_string(raw, "oa_status"),
        best_oa_location_url=best_url,
        best_oa_location_license=best_license,
        license_rule_result=evaluate_license(_normalize_license(best_license)),
        oa_locations=_parse_locations(raw.get("oa_locations")),
    )


def _best_location_evidence(raw: object) -> tuple[str | None, str | None]:
    if not isinstance(raw, dict):
        return None, None
    url = raw.get("url")
    license_value = raw.get("license")
    return (
        url if isinstance(url, str) and url.strip() else None,
        license_value if isinstance(license_value, str) and license_value.strip() else None,
    )


def _parse_locations(raw: object) -> tuple[UnpaywallLocation, ...]:
    if not isinstance(raw, list):
        return ()
    locations: list[UnpaywallLocation] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        host_type = entry.get("host_type")
        license_value = entry.get("license")
        is_best = entry.get("is_best")
        locations.append(
            UnpaywallLocation(
                url=url.strip(),
                host_type=host_type if isinstance(host_type, str) and host_type.strip() else None,
                license=license_value
                if isinstance(license_value, str) and license_value.strip()
                else None,
                is_best=is_best is True,
            )
        )
    return tuple(locations)


def _normalize_license(raw_license: str | None) -> str | None:
    if raw_license is None:
        return None
    return _CC_LICENSE_TOKENS.get(raw_license.strip().lower(), raw_license.strip())


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UnpaywallLookupError("Unpaywall response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
