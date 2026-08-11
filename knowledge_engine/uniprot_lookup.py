"""Live protein/gene-target lookup against UniProt's public UniProtKB REST API.

M73 adds a sixth slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched, alongside M41's
Wikipedia lookup, M42's RxNorm lookup, M43's MeSH lookup, M44's PubChem
lookup, and M71's ClinicalTrials.gov lookup: none of the first five
sources cover what a drug's *biological target* actually is at the
protein/gene level. RxNorm normalizes a drug's own name; PubChem covers
small-molecule chemical structure; MeSH covers disease/procedure
terminology -- none resolves "PD-1" or "GLP-1 receptor" to the protein
UniProt entry a checkpoint-inhibitor or GLP-1-agonist paper assumes its
reader already knows. This module resolves a protein or gene name to
that entry's canonical identity, function summary, and gene symbol,
live against UniProt's REST API (`https://rest.uniprot.org/uniprotkb/`)
-- never evidence, never routed through `EvidenceRecord` promotion, the
same "background context, not a citable finding" boundary M41-M44/M71
drew.

Chosen as the sixth source because it fills a gap none of the first
five cover: this project's own oncology corpus is built entirely around
immune-checkpoint proteins (PD-1, PD-L1, CTLA-4) and its GLP-1 corpus
around a single receptor (GLP-1R) -- exactly the kind of
"background a domain expert already has" the design doc's Motivation
section describes, for the one class of term (protein/gene targets)
none of M41-M44/M71 resolve.

Verified live before writing this parser: `GET
/uniprotkb/search?query="<term>" AND organism_id:9606 AND
reviewed:true&format=json&fields=...` returns 200 with a `results` array
for a real term (confirmed against "PDCD1"/gene search resolving to
Q15116/PDCD1_HUMAN, "PD-L1" free-text resolving to Q9NZQ7/PD1L1_HUMAN,
and "GLP-1 receptor" resolving to P43220/GLP1R_HUMAN, the GLP-1 corpus's
own primary drug target); a term matching nothing returns 200 with an
empty `results` array rather than an error status, reported as
`found=False` the same way M44's PubChem lookup treats its own
not-found case rather than distinguishing "no match" from "bad query."
Restricting to `organism_id:9606` (human) and `reviewed:true`
(Swiss-Prot manually-reviewed entries only, excluding unreviewed
TrEMBL) is a deliberate precision choice matching this project's own
scope (human clinical evidence) and existing quality bar, not a
UniProt API requirement -- a broader, unfiltered search was
deliberately not built, since a caller wanting every organism or every
unreviewed entry is better served by UniProt's own web search directly.
The top-ranked match is returned; UniProt's own relevance ranking, not
this module, decides which entry that is.

UniProtKB's own data (except third-party-sourced cross-references) is
released under CC BY 4.0 (https://www.uniprot.org/help/license) --
unlike M71's ClinicalTrials.gov, whose registry content is
externally-submitted and not asserted as any particular license, this
module can name the actual license UniProt states for its own curated
content.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from http.client import IncompleteRead
from typing import Protocol
from urllib.parse import urlencode

from knowledge_engine.uniprot_http import TransportResponse

UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
UNIPROT_ENTRY_PERMALINK = "https://www.uniprot.org/uniprotkb"
UNIPROT_CONTENT_LICENSE = (
    "UniProtKB's own curated content is released under CC BY 4.0 "
    "(https://www.uniprot.org/help/license); third-party-sourced "
    "cross-references may carry their own separate terms."
)
_SEARCH_FIELDS = "accession,id,gene_names,protein_name,organism_name,cc_function,length"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class UniProtLookupError(RuntimeError):
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
class UniProtLookupResult:
    """One protein/gene term's UniProtKB lookup outcome.

    Background context only -- `found=True` never means "this project
    has evidence about this protein," only "UniProt has a matching
    reviewed human entry for this term." Whether a specific paper's
    claim about this target is actually correct is a human or
    future-reasoning-layer judgment this module does not make.
    """

    term: str
    found: bool
    accession: str | None
    entry_name: str | None
    protein_name: str | None
    gene_name: str | None
    organism: str | None
    function: str | None
    sequence_length: int | None
    source_url: str | None
    license: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class UniProtLookupService:
    """Resolve a protein/gene term to its UniProtKB entry without asserting it as evidence."""

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
            raise ValueError("UniProt lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("UniProt lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("UniProt lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, term: str) -> UniProtLookupResult:
        """Return one protein/gene term's top-ranked UniProtKB entry, or `found=False`."""

        normalized = term.strip()
        if not normalized:
            raise ValueError("UniProt lookup term must not be empty.")

        url = f"{UNIPROT_SEARCH_URL}?{urlencode(_search_params(normalized))}"
        response = self._get(url)
        retrieved_at = datetime.now(UTC).isoformat()

        value = _parse_json_object(response)
        results = value.get("results")
        if not isinstance(results, list):
            raise UniProtLookupError("UniProt response was missing required evidence.")
        if not results:
            return _not_found_result(normalized, retrieved_at)

        entry = results[0]
        if not isinstance(entry, dict):
            raise UniProtLookupError("UniProt response contained malformed evidence.")
        return _parse_result(normalized, entry, retrieved_at=retrieved_at)

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
                    raise UniProtLookupError(
                        f"UniProt lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise UniProtLookupError(
                    "UniProt lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise UniProtLookupError("UniProt lookup request retry state was invalid.")


def _search_params(term: str) -> dict[str, str]:
    escaped = term.replace('"', '\\"')
    query = f'"{escaped}" AND organism_id:9606 AND reviewed:true'
    return {"query": query, "format": "json", "fields": _SEARCH_FIELDS}


def _not_found_result(term: str, retrieved_at: str) -> UniProtLookupResult:
    return UniProtLookupResult(
        term=term,
        found=False,
        accession=None,
        entry_name=None,
        protein_name=None,
        gene_name=None,
        organism=None,
        function=None,
        sequence_length=None,
        source_url=None,
        license=None,
        retrieved_at=retrieved_at,
    )


def _parse_result(term: str, entry: dict[str, object], *, retrieved_at: str) -> UniProtLookupResult:
    accession = _optional_string(entry, "primaryAccession")
    entry_name = _optional_string(entry, "uniProtkbId")

    protein_description = _optional_dict(entry, "proteinDescription")
    recommended_name = _optional_dict(protein_description, "recommendedName")
    full_name = _optional_dict(recommended_name, "fullName")
    protein_name = _optional_string(full_name, "value")

    genes_raw = entry.get("genes")
    gene_name: str | None = None
    if isinstance(genes_raw, list) and genes_raw:
        first_gene = genes_raw[0]
        if isinstance(first_gene, dict):
            gene_name_entry = _optional_dict(first_gene, "geneName")
            gene_name = _optional_string(gene_name_entry, "value")

    organism = _optional_dict(entry, "organism")
    organism_name = _optional_string(organism, "scientificName")

    function = _first_function_comment(entry)

    sequence = _optional_dict(entry, "sequence")
    sequence_length = sequence.get("length")
    if sequence_length is not None and not isinstance(sequence_length, int):
        raise UniProtLookupError("UniProt response contained malformed evidence.")

    return UniProtLookupResult(
        term=term,
        found=True,
        accession=accession,
        entry_name=entry_name,
        protein_name=protein_name,
        gene_name=gene_name,
        organism=organism_name,
        function=function,
        sequence_length=sequence_length,
        source_url=f"{UNIPROT_ENTRY_PERMALINK}/{accession}/entry" if accession else None,
        license=UNIPROT_CONTENT_LICENSE,
        retrieved_at=retrieved_at,
    )


def _first_function_comment(entry: dict[str, object]) -> str | None:
    comments = entry.get("comments")
    if not isinstance(comments, list):
        return None
    for comment in comments:
        if not isinstance(comment, dict) or comment.get("commentType") != "FUNCTION":
            continue
        texts = comment.get("texts")
        if not isinstance(texts, list) or not texts:
            continue
        first_text = texts[0]
        if not isinstance(first_text, dict):
            continue
        value = first_text.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_json_object(response: TransportResponse) -> dict[str, object]:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UniProtLookupError("UniProt returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise UniProtLookupError("UniProt returned malformed JSON.")
    return value


def _optional_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise UniProtLookupError("UniProt response contained malformed evidence.")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise UniProtLookupError("UniProt response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
