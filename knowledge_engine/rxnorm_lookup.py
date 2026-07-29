"""Live drug/pharmacology-terminology lookup against NLM's RxNorm API.

M42 adds a second slice of the reference knowledge layer
`docs/reference_knowledge_layer_design.md` sketched, alongside M41's
Wikipedia lookup: a drug name a paper's claim text uses (e.g.
"semaglutide", "empagliflozin") has no equivalent grounding in this
project's extraction pipeline today. This module resolves such a term to
its RxNorm normalized concept (RxCUI, canonical name, and term type --
e.g. "IN" for an ingredient, "BN" for a brand name) live against RxNav's
public REST API (https://rxnav.nlm.nih.gov/REST/) -- never evidence,
never routed through `EvidenceRecord` promotion, the same "background
context, not a citable finding" boundary M41 drew.

Chosen as the second source (over MeSH/PubChem/UniProt, the design doc's
other live-lookup candidates) because it needs no API key, is the
candidate the design doc specifically called out as reusing NCBI-adjacent
infrastructure, and complements Wikipedia's broad-but-encyclopedic
coverage with an authoritative, structured drug-name normalization this
project's diabetes/GLP-1 corpus concretely needs. RxNorm's own concept
model does *not* merge a brand name and its generic ingredient into one
identifier -- "Ozempic" (RxCUI 1991307, term type "BN") and "semaglutide"
(RxCUI 1991302, term type "IN") are, correctly, two distinct RxNorm
concepts, the same way this project's own schema keeps genuinely
different entities separate rather than collapsing them for convenience.
What *does* recognize them as the same underlying drug is RxNorm's own
ingredient relationship: this module resolves every term's `ingredients`
-- the underlying "IN"-type concept(s) reachable from its RxCUI via
RxNav's `related.json?tty=IN` endpoint, verified live to return
`semaglutide` (RxCUI 1991302) for both "semaglutide" and "Ozempic", and
to return multiple ingredients for a combination-drug brand (e.g.
"Glyxambi" resolves to both "linagliptin" and "empagliflozin"). A caller
that needs to recognize a brand name and its generic as equivalent
compares `ingredients`, not the top-level `rxcui`. RxNorm returns
structured facts (names, term types, ingredient relationships), not
explanatory prose -- the design doc's own caveat about the
RxNorm/MeSH/PubChem family versus Wikipedia's prose.

RxNorm content is NLM's own "non-proprietary content" per RxNav's Terms
of Service (https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html) -- not
a Creative Commons license, so `license` records that phrase directly
rather than forcing it into the `license_rules.py` CC-family pattern that
governs the separate paper corpus (which this reference layer, per the
design doc, is deliberately not part of).

Unlike Wikipedia's canonical page URL (which always resolves to the
*current* revision, requiring a separate `permanent_url`), RxNav's
concept-search permalink is already keyed to a specific RxCUI, so
`source_url` alone is a stable citation target here -- there is no
separate "permanent vs. current" distinction to preserve, unlike M41's
Wikipedia `revision`/`permanent_url` fields.
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

from knowledge_engine.rxnorm_http import TransportResponse

RXNORM_RXCUI_URL = "https://rxnav.nlm.nih.gov/REST/rxcui.json"
RXNORM_PROPERTIES_URL = "https://rxnav.nlm.nih.gov/REST/rxcui"
RXNORM_RELATED_INGREDIENT_TTY = "IN"
RXNORM_CONCEPT_PERMALINK = "https://mor.nlm.nih.gov/RxNav/search"
RXNORM_CONTENT_LICENSE = "Non-proprietary content, National Library of Medicine (RxNorm API)"

DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "knowledge-engine-core/0.2",
}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RxNormLookupError(RuntimeError):
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
class RxNormIngredient:
    """One ingredient-level RxNorm concept reachable from a looked-up term."""

    rxcui: str
    name: str


@dataclass(frozen=True)
class RxNormLookupResult:
    """One term's drug-terminology lookup outcome.

    Background context only -- `found=True` never means "this is
    evidence," only "RxNorm has a normalized concept for this term." A
    caller deciding whether a drug's identity is relevant to a specific
    paper's claim is a human or future-reasoning-layer judgment this
    module does not make.

    `rxcui`/`name`/`term_type` describe the term's *own* RxNorm concept,
    which for a brand name is the brand concept itself, not its generic
    ingredient -- RxNorm keeps those distinct by design. `ingredients`
    holds the underlying ingredient-level concept(s) this term resolves
    to; compare `ingredients` (not `rxcui`) to recognize a brand name and
    its generic as the same underlying drug.
    """

    term: str
    found: bool
    rxcui: str | None
    name: str | None
    term_type: str | None
    synonym: str | None
    ingredients: tuple[RxNormIngredient, ...]
    source_url: str | None
    license: str | None
    retrieved_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class RxNormLookupService:
    """Resolve a drug term to its RxNorm concept without asserting it as evidence."""

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
            raise ValueError("RxNorm lookup request interval must be non-negative.")
        if max_attempts < 1:
            raise ValueError("RxNorm lookup max attempts must be positive.")
        if retry_backoff_seconds < 0:
            raise ValueError("RxNorm lookup retry backoff must be non-negative.")
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.request_interval_seconds = request_interval_seconds
        self.max_attempts = max_attempts
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._request_count = 0

    def lookup(self, term: str) -> RxNormLookupResult:
        """Return one term's RxNorm concept, or `found=False` if none matches."""

        normalized = term.strip()
        if not normalized:
            raise ValueError("Term must not be empty.")

        retrieved_at = datetime.now(UTC).isoformat()
        rxcui = self._find_rxcui(normalized)
        if rxcui is None:
            return RxNormLookupResult(
                term=normalized,
                found=False,
                rxcui=None,
                name=None,
                term_type=None,
                synonym=None,
                ingredients=(),
                source_url=None,
                license=None,
                retrieved_at=retrieved_at,
            )

        properties = self._fetch_properties(rxcui)
        ingredients = self._fetch_ingredients(rxcui)
        source_url = f"{RXNORM_CONCEPT_PERMALINK}?searchBy=RXCUI&searchTerm={quote(rxcui, safe='')}"
        return RxNormLookupResult(
            term=normalized,
            found=True,
            rxcui=rxcui,
            name=_optional_string(properties, "name"),
            term_type=_optional_string(properties, "tty"),
            synonym=_optional_string(properties, "synonym"),
            ingredients=ingredients,
            source_url=source_url,
            license=RXNORM_CONTENT_LICENSE,
            retrieved_at=retrieved_at,
        )

    def _find_rxcui(self, term: str) -> str | None:
        url = f"{RXNORM_RXCUI_URL}?name={quote(term, safe='')}"
        value = _parse_json_object(self._get(url))
        id_group = value.get("idGroup")
        if not isinstance(id_group, dict):
            raise RxNormLookupError("RxNorm response was missing required evidence.")
        rxnorm_ids = id_group.get("rxnormId")
        if rxnorm_ids is None:
            return None
        if not isinstance(rxnorm_ids, list) or not rxnorm_ids or not isinstance(rxnorm_ids[0], str):
            raise RxNormLookupError("RxNorm response contained malformed evidence.")
        return rxnorm_ids[0]

    def _fetch_properties(self, rxcui: str) -> dict[str, object]:
        url = f"{RXNORM_PROPERTIES_URL}/{quote(rxcui, safe='')}/properties.json"
        value = _parse_json_object(self._get(url))
        properties = value.get("properties")
        if not isinstance(properties, dict):
            raise RxNormLookupError("RxNorm response was missing required evidence.")
        return properties

    def _fetch_ingredients(self, rxcui: str) -> tuple[RxNormIngredient, ...]:
        url = (
            f"{RXNORM_PROPERTIES_URL}/{quote(rxcui, safe='')}/related.json"
            f"?tty={RXNORM_RELATED_INGREDIENT_TTY}"
        )
        value = _parse_json_object(self._get(url))
        related_group = value.get("relatedGroup")
        if not isinstance(related_group, dict):
            raise RxNormLookupError("RxNorm response was missing required evidence.")
        concept_groups = related_group.get("conceptGroup")
        if not isinstance(concept_groups, list):
            raise RxNormLookupError("RxNorm response was missing required evidence.")

        ingredients: list[RxNormIngredient] = []
        for group in concept_groups:
            if not isinstance(group, dict) or group.get("tty") != RXNORM_RELATED_INGREDIENT_TTY:
                continue
            concept_properties = group.get("conceptProperties")
            if concept_properties is None:
                continue
            if not isinstance(concept_properties, list):
                raise RxNormLookupError("RxNorm response contained malformed evidence.")
            for concept in concept_properties:
                if not isinstance(concept, dict):
                    raise RxNormLookupError("RxNorm response contained malformed evidence.")
                ingredient_rxcui = _optional_string(concept, "rxcui")
                ingredient_name = _optional_string(concept, "name")
                if ingredient_rxcui is None or ingredient_name is None:
                    raise RxNormLookupError("RxNorm response contained malformed evidence.")
                ingredients.append(RxNormIngredient(rxcui=ingredient_rxcui, name=ingredient_name))
        return tuple(ingredients)

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
                    raise RxNormLookupError(
                        f"RxNorm lookup request failed after {attempt + 1} attempt(s)."
                    ) from exc
                continue
            if response.status_code == 200:
                return response
            if (
                response.status_code not in _RETRYABLE_STATUS_CODES
                or attempt + 1 == self.max_attempts
            ):
                raise RxNormLookupError(
                    "RxNorm lookup request returned a non-success status "
                    f"({response.status_code}) after {attempt + 1} attempt(s)."
                )
        raise RxNormLookupError("RxNorm lookup request retry state was invalid.")


def _parse_json_object(response: TransportResponse) -> dict[str, object]:
    try:
        value = json.loads(response.body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RxNormLookupError("RxNorm returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise RxNormLookupError("RxNorm returned malformed JSON.")
    return value


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RxNormLookupError("RxNorm response contained malformed evidence.")
    normalized = value.strip()
    return normalized or None
