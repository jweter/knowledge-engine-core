"""Live medical-concept lookup against NLM's MeSH database via E-utilities.

M43 adds a third slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched, alongside M41's
Wikipedia lookup and M42's RxNorm lookup: a disease, procedure, or
mechanism term a paper's claim text uses (e.g. "obesity", "type 2
diabetes") has no equivalent grounding in this project's extraction
pipeline today. This module resolves such a term to its canonical NLM
Medical Subject Headings (MeSH) descriptor -- a MeSH ID, preferred
heading, scope note (definition), and entry-term synonyms -- live
against NCBI's public E-utilities API (`db=mesh`) -- never evidence,
never routed through `EvidenceRecord` promotion, the same "background
context, not a citable finding" boundary M41/M42 drew.

Chosen as the third source (over PubChem, the design doc's remaining
live-lookup candidate) because MeSH's medical-concept hierarchy
complements Wikipedia's broad prose and RxNorm's drug-specific
normalization with something neither provides: NLM's own controlled
vocabulary for diseases, procedures, and biomedical concepts generally,
not just drug names. It also needed no new transport module: `db=mesh`
queries go through `eutils.ncbi.nlm.nih.gov`, a host `ncbi_http.py`
already allowlists for PubMed/PMC literature discovery, so this module
reuses `UrllibNcbiTransport` directly rather than building a dedicated
one the way M42's RxNorm lookup had to (RxNav is a different host) --
exactly the reuse the design doc's "third option" section anticipated.

MeSH's `esearch` endpoint is a full-text search, not an exact-match
lookup like RxNorm's: querying "obesity" returns dozens of loosely
related candidates (e.g. "Anti-Obesity Agents", "Pediatric Obesity"),
verified live before writing this parser. Naively taking the first
result would have silently returned the wrong concept for every term
tested (`obesity`, `type 2 diabetes`, `SGLT2 inhibitor`). This module
instead resolves a term only when exactly one candidate is both a true
MeSH descriptor record (`ds_recordtype == "descriptor"`, excluding the
"pharmacological-action" and "supplemental-record" candidates that
otherwise share the same entry terms) and has the queried term as one
of its own entry-term synonyms, verified case-insensitively -- and only
when that is true of *exactly one* candidate among *every* candidate
`esearch` reports, not just a first-page sample: a Codex review on
PR #182 caught that the original version capped `esearch` at 20
results and returned whichever candidate matched first, when the
project's own documentation already recorded 37 candidates for
"obesity" alone (and "cancer" returns 409). Fixed by fetching up to
`MESH_SEARCH_MAX_CANDIDATES` candidates and explicitly declining to
resolve (returning `found: false`, the same as a genuine no-match) if
the reported total exceeds what was fetched, or if more than one exact
match exists among what was checked -- an overly broad or genuinely
ambiguous term is never resolved by guessing which candidate is
"probably" right. A term with no exact match, or too many candidates to
check exhaustively, returns `found: false` rather than guessing --
confirmed live for "GLP-1 receptor agonist" (singular), which MeSH's
own entry terms only record in the plural ("GLP-1 Receptor Agonists"),
so it correctly does not resolve; a caller wanting that concept needs
the plural form MeSH actually uses, the same precision-over-recall
tradeoff a controlled vocabulary always makes relative to Wikipedia's
title-matching or RxNorm's brand-name coverage.

MeSH data is NLM's own free, non-proprietary content (no license fee
or royalty per NLM's published MeSH Terms and Conditions,
https://www.nlm.nih.gov/databases/download/terms_and_conditions_mesh.html)
-- not a Creative Commons license, so `license` records that phrase
directly rather than forcing it into the `license_rules.py` CC-family
pattern that governs the separate paper corpus (which this reference
layer, per the design doc, is deliberately not part of).
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

from knowledge_engine.ncbi_http import TransportResponse

MESH_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
MESH_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
MESH_PERMALINK = "https://id.nlm.nih.gov/mesh"
MESH_CONTENT_LICENSE = "Free, non-proprietary content, National Library of Medicine (MeSH)"
MESH_SEARCH_MAX_CANDIDATES = 200
"""Upper bound on how many `esearch` candidates one lookup will fetch and
check. Verified generous for real medical terms this project has tested
(37 for "obesity", the broadest single disease term tried) -- but a
single generic word like "cancer" (409) or "diabetes" (102, within bound
but still broad) can exceed or approach it. When `esearch` reports more
candidates than this bound fetches, `lookup` declines to resolve rather
than searching a partial, arbitrarily-ordered subset and risking a false
`found: false` for a term whose true descriptor just wasn't in the
window checked."""
MESH_DESCRIPTOR_RECORD_TYPE = "descriptor"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class MeshLookupError(RuntimeError):
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
class MeshLookupResult:
    """One term's medical-concept lookup outcome.

    Background context only -- `found=True` never means "this is
    evidence," only "MeSH has a matching descriptor for this term." A
    caller deciding whether a concept is relevant to a specific paper's
    claim is a human or future-reasoning-layer judgment this module
    does not make.
    """

    term: str
    found: bool
    mesh_id: str | None
    heading: str | None
    scope_note: str | None
    synonyms: tuple[str, ...]
    source_url: str | None
    license: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class MeshLookupService:
    """Resolve a medical term to its MeSH descriptor without asserting it as evidence."""

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
            raise ValueError("MeSH lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("MeSH lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("MeSH lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, term: str) -> MeshLookupResult:
        """Return one term's MeSH descriptor, or `found=False` if none matches exactly."""

        normalized = term.strip()
        if not normalized:
            raise ValueError("Term must not be empty.")

        retrieved_at = datetime.now(UTC).isoformat()
        total_count, candidate_uids = self._search(normalized)
        if total_count == 0:
            return _not_found_result(normalized, retrieved_at)
        if total_count > len(candidate_uids):
            # More candidates exist than this lookup fetched -- too broad to
            # check exhaustively, so decline rather than risk missing the
            # true match outside the window actually checked.
            return _not_found_result(normalized, retrieved_at)

        summaries = self._fetch_summaries(candidate_uids)
        matches = _find_exact_descriptor_matches(normalized, candidate_uids, summaries)
        if len(matches) != 1:
            return _not_found_result(normalized, retrieved_at)

        return _parse_result(normalized, matches[0], retrieved_at=retrieved_at)

    def _search(self, term: str) -> tuple[int, list[str]]:
        url = (
            f"{MESH_ESEARCH_URL}?db=mesh&retmode=json&retmax={MESH_SEARCH_MAX_CANDIDATES}"
            f"&term={quote(term, safe='')}"
        )
        value = _parse_json_object(self._get(url))
        esearchresult = value.get("esearchresult")
        if not isinstance(esearchresult, dict):
            raise MeshLookupError("MeSH response was missing required evidence.")
        count_text = esearchresult.get("count")
        if not isinstance(count_text, str) or not count_text.isdigit():
            raise MeshLookupError("MeSH response contained malformed evidence.")
        idlist = esearchresult.get("idlist")
        if not isinstance(idlist, list) or not all(isinstance(uid, str) for uid in idlist):
            raise MeshLookupError("MeSH response contained malformed evidence.")
        return int(count_text), idlist

    def _fetch_summaries(self, uids: list[str]) -> dict[str, object]:
        joined = ",".join(quote(uid, safe="") for uid in uids)
        url = f"{MESH_ESUMMARY_URL}?db=mesh&retmode=json&id={joined}"
        value = _parse_json_object(self._get(url))
        result = value.get("result")
        if not isinstance(result, dict):
            raise MeshLookupError("MeSH response was missing required evidence.")
        return result

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
                    raise MeshLookupError(
                        f"MeSH lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise MeshLookupError(
                    "MeSH lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise MeshLookupError("MeSH lookup request retry state was invalid.")


def _find_exact_descriptor_matches(
    term: str, ordered_uids: list[str], summaries: dict[str, object]
) -> list[dict[str, object]]:
    """Return every candidate that is both a true descriptor and an exact entry-term
    match. Callers must treat anything other than exactly one match as unresolved --
    never guess among multiple candidates that all claim the same entry term."""

    normalized_term = term.lower()
    matches: list[dict[str, object]] = []
    for uid in ordered_uids:
        record = summaries.get(uid)
        if not isinstance(record, dict):
            continue
        if record.get("ds_recordtype") != MESH_DESCRIPTOR_RECORD_TYPE:
            continue
        meshterms = record.get("ds_meshterms")
        if not isinstance(meshterms, list):
            continue
        if any(
            isinstance(entry, str) and entry.strip().lower() == normalized_term
            for entry in meshterms
        ):
            matches.append(record)
    return matches


def _not_found_result(term: str, retrieved_at: str) -> MeshLookupResult:
    return MeshLookupResult(
        term=term,
        found=False,
        mesh_id=None,
        heading=None,
        scope_note=None,
        synonyms=(),
        source_url=None,
        license=None,
        retrieved_at=retrieved_at,
    )


def _parse_result(term: str, record: dict[str, object], *, retrieved_at: str) -> MeshLookupResult:
    mesh_id = _required_string(record, "ds_meshui")
    meshterms = record.get("ds_meshterms")
    if not isinstance(meshterms, list) or not meshterms or not isinstance(meshterms[0], str):
        raise MeshLookupError("MeSH response was missing required evidence.")
    heading = meshterms[0].strip()
    synonyms = tuple(
        entry.strip() for entry in meshterms[1:] if isinstance(entry, str) and entry.strip()
    )
    return MeshLookupResult(
        term=term,
        found=True,
        mesh_id=mesh_id,
        heading=heading,
        scope_note=_optional_string(record, "ds_scopenote"),
        synonyms=synonyms,
        source_url=f"{MESH_PERMALINK}/{mesh_id}",
        license=MESH_CONTENT_LICENSE,
        retrieved_at=retrieved_at,
    )


def _parse_json_object(response: TransportResponse) -> dict[str, object]:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MeshLookupError("MeSH returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise MeshLookupError("MeSH returned malformed JSON.")
    return value


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MeshLookupError("MeSH response was missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MeshLookupError("MeSH response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
