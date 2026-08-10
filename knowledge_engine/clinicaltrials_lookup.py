"""Live clinical-trial-registry lookup against NLM/NIH's ClinicalTrials.gov API v2.

M71 adds a fifth slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched, alongside M41's
Wikipedia lookup, M42's RxNorm lookup, M43's MeSH lookup, and M44's
PubChem lookup: a trial registration ID a paper cites (e.g.
"NCT03652870") has no equivalent registry-level grounding in this
project's extraction pipeline today -- a paper's Abstract states its own
headline findings, but not the trial's registered design (phase, arms,
enrollment, sponsor, status) independently of what the paper chose to
report. This module resolves an NCT ID to that registry-level summary,
live against ClinicalTrials.gov's public API v2
(`https://clinicaltrials.gov/api/v2/`) -- never evidence, never routed
through `EvidenceRecord` promotion, the same "background context, not a
citable finding" boundary M41/M42/M43/M44 drew.

Chosen as the fifth source because it fills a gap none of the first four
cover: independent trial-registration metadata for a specific study
already cited by ID in this project's own corpus (e.g. the mental-health
corpus's `ev-mh-schrag-2026-adept-pd-nortriptyline-escitalopram-001`
record cites ClinicalTrials.gov ID NCT03652870 directly in its source
paper). A registry entry can also surface facts a single paper's Abstract
does not restate (e.g. the trial's full enrolled-arm intervention list,
its registered Phase, or its `overallStatus`), the same "background a
domain expert already has" role the design doc's Motivation section
describes for the other four sources.

Verified live before writing this parser: `GET
/api/v2/studies/{nctId}?format=json` returns 200 with a nested
`protocolSection` for a real, well-formed ID (confirmed against
NCT03652870, the Schrag ADepT-PD trial); a well-formed but unregistered
ID (NCT99999999) returns a clean 404; and a malformed ID (not matching
ClinicalTrials.gov's own `NCT` + 8-digit format) returns 400 with the
message "Parameter `nctId` has incorrect format" -- both are reported as
`found: false` by this module rather than distinguished into a separate
error path, since neither implies anything beyond "no matching
registration was found for that input," the same posture M44's PubChem
lookup takes for its own not-found case. Lowercase input
(`nct03652870`) is accepted by the API without normalization required
client-side.

ClinicalTrials.gov is operated by the U.S. National Library of Medicine
(part of NIH), but its registry content -- brief/official titles,
summaries, design fields, and status -- is entered by each trial's own
responsible party (sponsor or principal investigator), not authored by
NLM itself. This mirrors the same sponsor/depositor-vs-host distinction
M44's PubChem lookup already drew for compound records sourced from
external depositors like ChEBI -- `license` therefore does not assert a
blanket public-domain claim, only that this is a U.S. government-hosted
registry of externally-submitted content whose specific reuse terms
should be verified rather than assumed uniformly permissive.
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

from knowledge_engine.clinicaltrials_http import TransportResponse

CLINICALTRIALS_STUDY_URL = "https://clinicaltrials.gov/api/v2/studies"
CLINICALTRIALS_STUDY_PERMALINK = "https://clinicaltrials.gov/study"
CLINICALTRIALS_CONTENT_LICENSE = (
    "ClinicalTrials.gov is operated by the U.S. National Library of Medicine "
    "(NIH), but each trial's registry content (titles, summaries, design "
    "fields, status) is entered by that trial's own responsible party "
    "(sponsor or principal investigator), not authored by NLM itself -- "
    "not asserted as a blanket public-domain license; verify "
    "source-specific reuse terms before redistribution."
)

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_NOT_FOUND_STATUS_CODES = {400, 404}


class ClinicalTrialsLookupError(RuntimeError):
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
class ClinicalTrialsLookupResult:
    """One NCT ID's trial-registry lookup outcome.

    Background context only -- `found=True` never means "this is
    evidence," only "ClinicalTrials.gov has a matching registered study
    for this ID." A caller deciding whether a trial's registered design
    matches what a specific paper reported is a human or
    future-reasoning-layer judgment this module does not make.
    """

    nct_id: str
    found: bool
    brief_title: str | None
    official_title: str | None
    overall_status: str | None
    phases: tuple[str, ...]
    study_type: str | None
    conditions: tuple[str, ...]
    interventions: tuple[str, ...]
    enrollment_count: int | None
    lead_sponsor: str | None
    brief_summary: str | None
    source_url: str | None
    license: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class ClinicalTrialsLookupService:
    """Resolve an NCT ID to its registry record without asserting it as evidence."""

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
            raise ValueError("ClinicalTrials.gov lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("ClinicalTrials.gov lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("ClinicalTrials.gov lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, nct_id: str) -> ClinicalTrialsLookupResult:
        """Return one trial's registry record, or `found=False` if none matches."""

        normalized = nct_id.strip()
        if not normalized:
            raise ValueError("NCT ID must not be empty.")

        url = f"{CLINICALTRIALS_STUDY_URL}/{quote(normalized, safe='')}?format=json"
        response = self._get(url)
        retrieved_at = datetime.now(UTC).isoformat()
        if response.status_code in _NOT_FOUND_STATUS_CODES:
            return _not_found_result(normalized, retrieved_at)

        value = _parse_json_object(response)
        protocol_section = value.get("protocolSection")
        if not isinstance(protocol_section, dict):
            raise ClinicalTrialsLookupError(
                "ClinicalTrials.gov response was missing required evidence."
            )

        return _parse_result(normalized, protocol_section, retrieved_at=retrieved_at)

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
                    raise ClinicalTrialsLookupError(
                        f"ClinicalTrials.gov lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200 or response.status_code in _NOT_FOUND_STATUS_CODES:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise ClinicalTrialsLookupError(
                    "ClinicalTrials.gov lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise ClinicalTrialsLookupError(
            "ClinicalTrials.gov lookup request retry state was invalid."
        )


def _not_found_result(nct_id: str, retrieved_at: str) -> ClinicalTrialsLookupResult:
    return ClinicalTrialsLookupResult(
        nct_id=nct_id,
        found=False,
        brief_title=None,
        official_title=None,
        overall_status=None,
        phases=(),
        study_type=None,
        conditions=(),
        interventions=(),
        enrollment_count=None,
        lead_sponsor=None,
        brief_summary=None,
        source_url=None,
        license=None,
        retrieved_at=retrieved_at,
    )


def _parse_result(
    nct_id: str, protocol_section: dict[str, object], *, retrieved_at: str
) -> ClinicalTrialsLookupResult:
    identification = _optional_dict(protocol_section, "identificationModule")
    resolved_nct_id = _optional_string(identification, "nctId") or nct_id
    status_module = _optional_dict(protocol_section, "statusModule")
    design_module = _optional_dict(protocol_section, "designModule")
    conditions_module = _optional_dict(protocol_section, "conditionsModule")
    arms_module = _optional_dict(protocol_section, "armsInterventionsModule")
    sponsor_module = _optional_dict(protocol_section, "sponsorCollaboratorsModule")
    description_module = _optional_dict(protocol_section, "descriptionModule")

    lead_sponsor_entry = _optional_dict(sponsor_module, "leadSponsor")
    enrollment_info = _optional_dict(design_module, "enrollmentInfo")
    enrollment_count = enrollment_info.get("count")
    if enrollment_count is not None and not isinstance(enrollment_count, int):
        raise ClinicalTrialsLookupError("ClinicalTrials.gov response contained malformed evidence.")

    interventions_raw = arms_module.get("interventions")
    interventions: tuple[str, ...] = ()
    if isinstance(interventions_raw, list):
        interventions = tuple(
            name
            for entry in interventions_raw
            if isinstance(entry, dict)
            and isinstance(name := entry.get("name"), str)
            and name.strip()
        )

    return ClinicalTrialsLookupResult(
        nct_id=resolved_nct_id,
        found=True,
        brief_title=_optional_string(identification, "briefTitle"),
        official_title=_optional_string(identification, "officialTitle"),
        overall_status=_optional_string(status_module, "overallStatus"),
        phases=_optional_string_tuple(design_module, "phases"),
        study_type=_optional_string(design_module, "studyType"),
        conditions=_optional_string_tuple(conditions_module, "conditions"),
        interventions=interventions,
        enrollment_count=enrollment_count,
        lead_sponsor=_optional_string(lead_sponsor_entry, "name"),
        brief_summary=_optional_string(description_module, "briefSummary"),
        source_url=f"{CLINICALTRIALS_STUDY_PERMALINK}/{resolved_nct_id}",
        license=CLINICALTRIALS_CONTENT_LICENSE,
        retrieved_at=retrieved_at,
    )


def _parse_json_object(response: TransportResponse) -> dict[str, object]:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClinicalTrialsLookupError("ClinicalTrials.gov returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise ClinicalTrialsLookupError("ClinicalTrials.gov returned malformed JSON.")
    return value


def _optional_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ClinicalTrialsLookupError("ClinicalTrials.gov response contained malformed evidence.")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ClinicalTrialsLookupError("ClinicalTrials.gov response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _optional_string_tuple(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
        raise ClinicalTrialsLookupError("ClinicalTrials.gov response contained malformed evidence.")
    return tuple(entry.strip() for entry in value if entry.strip())
