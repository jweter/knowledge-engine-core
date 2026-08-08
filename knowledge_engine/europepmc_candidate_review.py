"""Deterministic adjudication worksheets for Europe PMC candidates.

Mirrors `candidate_review.py`'s accept/reject/hold-with-reason-codes shape
for M14's PubMed/PMC pipeline, but is a deliberately separate, independently
versioned engine rather than a retrofit of that mature, heavily-rehearsed
module: identity and full-text evidence work differently here (no PMCID to
anchor identity for the non-PMC content this pipeline targets; no single
official PDF bucket to allowlist the way PMC's S3 bucket is). Scientific-scope
and license rules ARE shared -- see `scientific_scope.py`/`license_rules.py`
-- since those criteria are the same regardless of which discovery source
found a candidate.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

from knowledge_engine.europepmc_http import EUROPEPMC_PDF_HOST
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.scientific_scope import (
    GLP1_METABOLIC_SCOPE,
    ScopeVocabulary,
    evaluate_scientific_scope,
)
from knowledge_engine.utils import normalize_doi

EUROPEPMC_ADJUDICATION_RULES_VERSION = "m34-europepmc-candidate-adjudication-v1"


class EuropePmcCandidateReviewError(RuntimeError):
    """Sanitized candidate-adjudication preparation failure."""


@dataclass(frozen=True)
class EuropePmcCandidateReviewItem:
    """One candidate with an explicit deterministic adjudication result."""

    europepmc_id: str
    source: str
    pmid: str | None
    pmcid: str | None
    doi: str | None
    title: str
    abstract: str | None
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    in_pmc: bool
    open_access: bool
    reported_license: str | None
    pdf_url: str | None
    pdf_host: str | None
    decision: str
    reason_codes: tuple[str, ...]
    rules_version: str
    adjudicated_at: str
    inclusion_rule_result: str
    identity_rule_result: str
    license_rule_result: str
    full_text_rule_result: str
    pmc_overlap_rule_result: str
    duplicate_rule_result: str
    evidence_provenance: tuple[str, ...]
    unresolved_ambiguities: tuple[str, ...]


@dataclass(frozen=True)
class EuropePmcCandidateReviewWorksheet:
    """Stable adjudication worksheet that cannot itself authorize acquisition."""

    schema_version: int
    source_query: str
    source_cursor_mark: str
    source_limit: int
    candidate_count: int
    rules_version: str
    items: tuple[EuropePmcCandidateReviewItem, ...]

    def to_json(self) -> str:
        """Render stable, auditable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def prepare_europepmc_candidate_review(
    candidates_path: Path,
    *,
    vocabulary: ScopeVocabulary = GLP1_METABOLIC_SCOPE,
) -> EuropePmcCandidateReviewWorksheet:
    """Validate discovery output and create explicit adjudication records.

    `vocabulary` defaults to the original GLP-1/metabolic-disease scope
    terms -- pass a different `ScopeVocabulary` (see
    `knowledge_engine.scientific_scope`) to adjudicate a different corpus.
    """

    if candidates_path.is_symlink():
        raise EuropePmcCandidateReviewError("Candidate input must not be a symbolic link.")
    try:
        payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EuropePmcCandidateReviewError("Candidate input is not valid discovery JSON.") from exc
    if not isinstance(payload, dict):
        raise EuropePmcCandidateReviewError("Candidate input is not valid discovery JSON.")

    query = _required_string(payload, "query")
    cursor_mark = _required_string(payload, "cursor_mark")
    limit = _required_positive_int(payload, "limit")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or payload.get("candidate_count") != len(candidates):
        raise EuropePmcCandidateReviewError("Candidate input count does not reconcile.")

    adjudicated_at = datetime.now(UTC).isoformat()
    items: list[EuropePmcCandidateReviewItem] = []
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise EuropePmcCandidateReviewError("Candidate input contains a malformed item.")
        europepmc_id = _required_string(candidate, "europepmc_id")
        if europepmc_id in seen_ids:
            raise EuropePmcCandidateReviewError("Candidate input contains a duplicate id.")
        seen_ids.add(europepmc_id)

        doi = _optional_string(candidate, "doi")
        duplicate_rule_result = "passed_exact_identifier_uniqueness"
        if doi is not None:
            normalized_doi = normalize_doi(doi)
            if normalized_doi in seen_dois:
                raise EuropePmcCandidateReviewError("Candidate input contains a duplicate DOI.")
            seen_dois.add(normalized_doi)

        open_access = candidate.get("open_access")
        if not isinstance(open_access, bool):
            raise EuropePmcCandidateReviewError("Candidate input contains malformed OA evidence.")
        in_pmc = candidate.get("in_pmc")
        if not isinstance(in_pmc, bool):
            raise EuropePmcCandidateReviewError("Candidate input contains malformed PMC evidence.")

        title = _required_string(candidate, "title")
        abstract = _optional_string(candidate, "abstract")
        reported_license = _optional_string(candidate, "license")
        pdf_url = _optional_string(candidate, "pdf_url")
        pdf_host = _optional_string(candidate, "pdf_host")
        decision = _adjudicate(
            title=title,
            abstract=abstract,
            doi=doi,
            open_access=open_access,
            in_pmc=in_pmc,
            reported_license=reported_license,
            pdf_url=pdf_url,
            pdf_host=pdf_host,
            vocabulary=vocabulary,
        )
        items.append(
            EuropePmcCandidateReviewItem(
                europepmc_id=europepmc_id,
                source=_required_string(candidate, "source"),
                pmid=_optional_string(candidate, "pmid"),
                pmcid=_optional_string(candidate, "pmcid"),
                doi=doi,
                title=title,
                abstract=abstract,
                authors=_authors(candidate),
                publication_year=_optional_year(candidate, "publication_year"),
                venue=_optional_string(candidate, "venue"),
                in_pmc=in_pmc,
                open_access=open_access,
                reported_license=reported_license,
                pdf_url=pdf_url,
                pdf_host=pdf_host,
                adjudicated_at=adjudicated_at,
                duplicate_rule_result=duplicate_rule_result,
                evidence_provenance=("europepmc_search",),
                **decision,
            )
        )

    return EuropePmcCandidateReviewWorksheet(
        schema_version=1,
        source_query=query,
        source_cursor_mark=cursor_mark,
        source_limit=limit,
        candidate_count=len(items),
        rules_version=EUROPEPMC_ADJUDICATION_RULES_VERSION,
        items=tuple(items),
    )


class _AdjudicationDecision(TypedDict):
    decision: str
    reason_codes: tuple[str, ...]
    rules_version: str
    inclusion_rule_result: str
    identity_rule_result: str
    license_rule_result: str
    full_text_rule_result: str
    pmc_overlap_rule_result: str
    unresolved_ambiguities: tuple[str, ...]


def _adjudicate(
    *,
    title: str,
    abstract: str | None,
    doi: str | None,
    open_access: bool,
    in_pmc: bool,
    reported_license: str | None,
    pdf_url: str | None,
    pdf_host: str | None,
    vocabulary: ScopeVocabulary = GLP1_METABOLIC_SCOPE,
) -> _AdjudicationDecision:
    inclusion = evaluate_scientific_scope(title, abstract, vocabulary=vocabulary)
    identity = "passed" if doi is not None else "incomplete_missing_doi"
    license_result = evaluate_license(reported_license)
    full_text = _full_text_result(pdf_url, pdf_host)
    pmc_overlap = "out_of_scope_already_in_pmc" if in_pmc else "passed"

    if not open_access:
        return {
            "decision": "rejected",
            "reason_codes": ("NO_VERIFIED_REUSABLE_FULL_TEXT",),
            "rules_version": EUROPEPMC_ADJUDICATION_RULES_VERSION,
            "inclusion_rule_result": inclusion,
            "identity_rule_result": identity,
            "license_rule_result": "not_evaluated_without_oa_record",
            "full_text_rule_result": "not_available",
            "pmc_overlap_rule_result": pmc_overlap,
            "unresolved_ambiguities": (),
        }

    if in_pmc:
        return {
            "decision": "rejected",
            "reason_codes": ("DUPLICATE_OF_PMC_PIPELINE_SCOPE",),
            "rules_version": EUROPEPMC_ADJUDICATION_RULES_VERSION,
            "inclusion_rule_result": inclusion,
            "identity_rule_result": identity,
            "license_rule_result": license_result,
            "full_text_rule_result": full_text,
            "pmc_overlap_rule_result": pmc_overlap,
            "unresolved_ambiguities": (),
        }

    ambiguities: list[str] = []
    reasons: list[str] = []
    if inclusion != "passed":
        ambiguities.append("scientific_relevance")
        reasons.append("SCIENTIFIC_SCOPE_INSUFFICIENT")
    if identity != "passed":
        ambiguities.append("identity")
        reasons.append("IDENTITY_EVIDENCE_INCOMPLETE")
    if license_result != "passed":
        ambiguities.append("license")
        reasons.append("LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED")
    if full_text != "passed":
        ambiguities.append("full_text")
        reasons.append("APPROVED_FULL_TEXT_LOCATION_INVALID")

    if ambiguities:
        return {
            "decision": "held",
            "reason_codes": tuple(reasons),
            "rules_version": EUROPEPMC_ADJUDICATION_RULES_VERSION,
            "inclusion_rule_result": inclusion,
            "identity_rule_result": identity,
            "license_rule_result": license_result,
            "full_text_rule_result": full_text,
            "pmc_overlap_rule_result": pmc_overlap,
            "unresolved_ambiguities": tuple(ambiguities),
        }

    return {
        "decision": "accepted",
        "reason_codes": ("ALL_REQUIRED_RULES_PASSED",),
        "rules_version": EUROPEPMC_ADJUDICATION_RULES_VERSION,
        "inclusion_rule_result": inclusion,
        "identity_rule_result": identity,
        "license_rule_result": license_result,
        "full_text_rule_result": full_text,
        "pmc_overlap_rule_result": pmc_overlap,
        "unresolved_ambiguities": (),
    }


def _full_text_result(pdf_url: str | None, pdf_host: str | None) -> str:
    if pdf_url is None or pdf_host is None:
        return "incomplete_missing_pdf_url"
    if pdf_host != EUROPEPMC_PDF_HOST:
        return "held_third_party_host"
    parsed = urlparse(pdf_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != EUROPEPMC_PDF_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        return "invalid_approved_pdf_url"
    return "passed"


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EuropePmcCandidateReviewError("Candidate input is missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise EuropePmcCandidateReviewError("Candidate input contains malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _authors(payload: dict[str, object]) -> tuple[str, ...]:
    value = payload.get("authors", [])
    if not isinstance(value, list) or not all(
        isinstance(author, str) and author.strip() for author in value
    ):
        raise EuropePmcCandidateReviewError("Candidate input contains malformed author evidence.")
    return tuple(author.strip() for author in value)


def _optional_year(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 9999:
        raise EuropePmcCandidateReviewError(
            "Candidate input contains malformed publication evidence."
        )
    return value


def _required_positive_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise EuropePmcCandidateReviewError(
            "Candidate input contains malformed discovery metadata."
        )
    return value
