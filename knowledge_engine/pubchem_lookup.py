"""Live chemical-compound lookup against NLM/NCBI's PubChem PUG REST API.

M44 adds a fourth slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched, alongside M41's
Wikipedia lookup, M42's RxNorm lookup, and M43's MeSH lookup: a chemical
compound name a paper's claim text uses (e.g. "metformin",
"empagliflozin") has no equivalent structural grounding in this
project's extraction pipeline today. This module resolves such a name
to its PubChem Compound ID (CID) and structured chemical identifiers --
title, IUPAC name, molecular formula, molecular weight, and canonical
SMILES -- live against PubChem's public PUG REST API
(`https://pubchem.ncbi.nlm.nih.gov/rest/pug/`) -- never evidence, never
routed through `EvidenceRecord` promotion, the same "background
context, not a citable finding" boundary M41/M42/M43 drew.

Chosen as the fourth source (the design doc's last named live-lookup
candidate, after RxNorm/MeSH/PubChem) because it fills a gap none of the
first three cover: real chemical-structure data (a compound's molecular
formula, weight, and SMILES string), not just a normalized name (RxNorm)
or a controlled medical-concept vocabulary (MeSH). It needed its own
dedicated transport (`pubchem_http.py`): `pubchem.ncbi.nlm.nih.gov` is a
distinct NLM/NCBI host from both `eutils.ncbi.nlm.nih.gov` (M43's MeSH
lookup reuses `ncbi_http.py` directly) and `rxnav.nlm.nih.gov` (M42's
RxNorm lookup).

PubChem's `property` endpoint is an exact-name lookup (like RxNorm's,
not MeSH's full-text search): a name with no matching compound returns
a clean 404, verified live before writing this parser. One real API
quirk found the same way: requesting the `CanonicalSMILES` property
name (PubChem's older, still-documented name) returns the result under
a *different* response key, `ConnectivitySMILES` -- PubChem renamed the
property but keeps the old request name aliased for backward
compatibility without renaming the response key to match. This module
requests `ConnectivitySMILES` directly to avoid relying on that alias.

Also verified live: PubChem indexes whatever name strings were actually
deposited alongside real compounds, not a curated concept vocabulary --
querying "GLP-1 receptor agonist" (a mechanism class, not a specific
drug) resolves to a real, specific small-molecule compound (CID
177864544) that happens to have been deposited under that literal
name, not the general mechanism class a reader might expect. This
module reports whatever PubChem actually returns rather than guessing
what a caller "probably" meant.

A name can also resolve to more than one compound record -- verified
live: querying "estrogen" returns two distinct CIDs (21628493 and
12115739) sharing the same synonym. Silently returning the first would
misidentify the compound, the same guessing-among-ambiguous-candidates
mistake M43's original MeSH lookup made (and Codex review on this PR
caught here too); this module resolves a name only when the response
contains exactly one candidate, declining (`found: false`) otherwise --
never a guess among ambiguous candidates.

PubChem is not a blanket U.S. government work: it aggregates compound
names and identifiers from many external depositors -- verified live
that CID 4091 (metformin)'s own PubChem-hosted description is sourced
from ChEBI, a UK-based database, not authored by NCBI. NCBI/NLM's
general public-domain policy ("information created by or for the US
government on this site is within the public domain",
https://www.ncbi.nlm.nih.gov/home/about/policies/) covers only content
NCBI itself creates, not depositor-submitted content -- so `license`
does not assert a blanket public-domain claim for PubChem records (a
real gap Codex review on this PR caught in the first version, which had
wrongly labeled every result a U.S. government work). It instead states
that provenance is mixed and reuse terms should be verified
source-by-source, deliberately not forced into the `license_rules.py`
CC-family pattern that governs the separate paper corpus (which this
reference layer, per the design doc, is not part of).
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

from knowledge_engine.pubchem_http import TransportResponse

PUBCHEM_PROPERTY_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"
PUBCHEM_PROPERTIES = "Title,IUPACName,MolecularFormula,MolecularWeight,ConnectivitySMILES"
PUBCHEM_COMPOUND_PERMALINK = "https://pubchem.ncbi.nlm.nih.gov/compound"
PUBCHEM_CONTENT_LICENSE = (
    "PubChem (National Library of Medicine) aggregates compound names and "
    "identifiers from many external depositors (verified live: CID 4091's "
    "own PubChem description is sourced from ChEBI, not NCBI). NCBI's "
    "public-domain policy for government-authored content "
    "(https://www.ncbi.nlm.nih.gov/home/about/policies/) does not cover "
    "depositor-submitted content, so this is not asserted as a blanket "
    "public-domain license -- verify source-specific reuse terms before "
    "redistribution."
)

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class PubchemLookupError(RuntimeError):
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
class PubchemLookupResult:
    """One compound name's chemical-structure lookup outcome.

    Background context only -- `found=True` never means "this is
    evidence," only "PubChem has a matching compound record for this
    name." A caller deciding whether a compound is relevant to a
    specific paper's claim is a human or future-reasoning-layer
    judgment this module does not make.
    """

    term: str
    found: bool
    cid: str | None
    title: str | None
    iupac_name: str | None
    molecular_formula: str | None
    molecular_weight: str | None
    smiles: str | None
    source_url: str | None
    license: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class PubchemLookupService:
    """Resolve a compound name to its PubChem record without asserting it as evidence."""

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
            raise ValueError("PubChem lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("PubChem lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("PubChem lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, term: str) -> PubchemLookupResult:
        """Return one compound's PubChem record, or `found=False` if none matches."""

        normalized = term.strip()
        if not normalized:
            raise ValueError("Term must not be empty.")

        url = (
            f"{PUBCHEM_PROPERTY_URL}/{quote(normalized, safe='')}"
            f"/property/{PUBCHEM_PROPERTIES}/JSON"
        )
        response = self._get(url)
        retrieved_at = datetime.now(UTC).isoformat()
        if response.status_code == 404:
            return _not_found_result(normalized, retrieved_at)

        value = _parse_json_object(response)
        property_table = value.get("PropertyTable")
        if not isinstance(property_table, dict):
            raise PubchemLookupError("PubChem response was missing required evidence.")
        properties = property_table.get("Properties")
        if (
            not isinstance(properties, list)
            or not properties
            or not all(isinstance(entry, dict) for entry in properties)
        ):
            raise PubchemLookupError("PubChem response was missing required evidence.")
        if len(properties) > 1:
            return _not_found_result(normalized, retrieved_at)

        return _parse_result(normalized, properties[0], retrieved_at=retrieved_at)

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
                    raise PubchemLookupError(
                        f"PubChem lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code in (200, 404):
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise PubchemLookupError(
                    "PubChem lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise PubchemLookupError("PubChem lookup request retry state was invalid.")


def _not_found_result(term: str, retrieved_at: str) -> PubchemLookupResult:
    return PubchemLookupResult(
        term=term,
        found=False,
        cid=None,
        title=None,
        iupac_name=None,
        molecular_formula=None,
        molecular_weight=None,
        smiles=None,
        source_url=None,
        license=None,
        retrieved_at=retrieved_at,
    )


def _parse_result(
    term: str, properties: dict[str, object], *, retrieved_at: str
) -> PubchemLookupResult:
    cid = properties.get("CID")
    if not isinstance(cid, (int, str)) or not str(cid).strip():
        raise PubchemLookupError("PubChem response was missing required evidence.")
    cid_text = str(cid).strip()
    return PubchemLookupResult(
        term=term,
        found=True,
        cid=cid_text,
        title=_optional_string(properties, "Title"),
        iupac_name=_optional_string(properties, "IUPACName"),
        molecular_formula=_optional_string(properties, "MolecularFormula"),
        molecular_weight=_optional_string(properties, "MolecularWeight"),
        smiles=_optional_string(properties, "ConnectivitySMILES"),
        source_url=f"{PUBCHEM_COMPOUND_PERMALINK}/{cid_text}",
        license=PUBCHEM_CONTENT_LICENSE,
        retrieved_at=retrieved_at,
    )


def _parse_json_object(response: TransportResponse) -> dict[str, object]:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PubchemLookupError("PubChem returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise PubchemLookupError("PubChem returned malformed JSON.")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = str(value)
    if not isinstance(value, str):
        raise PubchemLookupError("PubChem response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
