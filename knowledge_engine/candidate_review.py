"""Deterministic adjudication worksheets for PubMed/PMC candidates."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

from knowledge_engine.ncbi_http import PMC_CLOUD_PDF_HOST

ADJUDICATION_RULES_VERSION = "m14-candidate-adjudication-v9"
_ALLOWED_LICENSE_PATTERN = re.compile(
    r"^(?:CC BY(?: (?:1\.0|2\.0|2\.5|3\.0|4\.0))?|CC0(?: 1\.0)?)$"
)
"""Matches only unrestricted licenses: exactly "CC BY" or "CC0", optionally
followed by one of their real published version numbers (CC BY: 1.0, 2.0, 2.5,
3.0, or 4.0; CC0: only 1.0 exists). Deliberately does not match "CC BY-NC",
"CC BY-NC-ND", "CC BY-NC-SA", or "CC BY-SA" - those restrict commercial use
and/or derivative works, which conflicts with this project's extraction and
redistribution of derived evidence records (Phase 2). The version allowlist
(rather than a loose `[0-9.]*` pattern) also ensures a version that passes
here always has a real Creative Commons deed URL - see `license_deed_url`."""
_DISEASE_TERMS = (
    "obesity",
    "obese",
    "overweight",
    "type 2 diabetes",
    "type ii diabetes",
    "t2d",
    "metabolic syndrome",
)
_INTERVENTION_TERMS = (
    "treatment",
    "therapy",
    "therapeutic",
    "intervention",
    "pharmacotherapy",
    "drug",
    "medication",
    "glp-1",
    "glp1",
    "glucagon-like peptide-1",
    "semaglutide",
    "liraglutide",
    "tirzepatide",
    "metformin",
    "sglt2",
    "sodium-glucose cotransporter 2",
)
_PEDIATRIC_POPULATION_TERMS = (
    "pediatric",
    "paediatric",
    "child",
    "infant",
    "neonat",
    "adolescent",
    "youth",
)
_ADULT_INCLUSION_TERMS = ("adult",)
"""Matches only the title -- not the abstract, unlike the disease/intervention
terms above. An adult study's abstract can mention pediatric research as
background context without the study itself being pediatric; a title is a
much stronger population signal. `exclusion_criteria.md` requires excluding
sources "limited to" pediatric populations, not merely mentioning one -- a
title also naming an adult population (e.g. "...in adolescents and adults")
is evidence of a mixed-age study, not one limited to pediatric, so
`_ADULT_INCLUSION_TERMS` overrides the pediatric match rather than holding
otherwise-valid adult-inclusive evidence. A title match with no adult term
returns a non-"passed" scope result, which routes to `held` (never a silent
rejection), matching how every other scope-insufficient title is already
treated."""
_NON_PRIMARY_TITLE_PREFIXES = (
    "correction:",
    "corrigendum:",
    "erratum:",
    "retraction:",
    "retracted:",
    "publisher correction:",
    "author correction:",
)
"""A correction/erratum/retraction notice for an original article is not
itself a scientific paper, systematic review, meta-analysis, or clinical
research report -- it is typically a page or two amending a figure, table,
or author list in the original. Journals mark these with a stable title
prefix, so checking the title's start (case-insensitively) is a reliable,
still-deterministic signal, unlike scanning for "correction" as a bare
substring, which would also match a legitimate title like "Confidence
interval correction for measurement bias in obesity studies"."""


class CandidateReviewError(RuntimeError):
    """Sanitized candidate-adjudication preparation failure."""


@dataclass(frozen=True)
class CandidateReviewItem:
    """One candidate with an explicit deterministic adjudication result."""

    pmid: str
    title: str
    abstract: str | None
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    doi: str | None
    pmcid: str | None
    open_access: bool
    reported_license: str | None
    pdf_url: str | None
    discovery_status: str
    decision: str
    reason_codes: tuple[str, ...]
    rules_version: str
    adjudicated_at: str
    inclusion_rule_result: str
    identity_rule_result: str
    license_rule_result: str
    full_text_rule_result: str
    duplicate_rule_result: str
    evidence_provenance: tuple[str, ...]
    unresolved_ambiguities: tuple[str, ...]


@dataclass(frozen=True)
class CandidateReviewWorksheet:
    """Stable adjudication worksheet that cannot itself authorize acquisition."""

    schema_version: int
    source_query: str
    source_retstart: int
    source_limit: int
    candidate_count: int
    rules_version: str
    items: tuple[CandidateReviewItem, ...]

    def to_json(self) -> str:
        """Render stable, auditable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def prepare_candidate_review(candidates_path: Path) -> CandidateReviewWorksheet:
    """Validate discovery output and create explicit adjudication records."""

    if candidates_path.is_symlink():
        raise CandidateReviewError("Candidate input must not be a symbolic link.")
    try:
        payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateReviewError("Candidate input is not valid discovery JSON.") from exc
    if not isinstance(payload, dict):
        raise CandidateReviewError("Candidate input is not valid discovery JSON.")

    query = _required_string(payload, "query")
    retstart = _required_nonnegative_int(payload, "retstart")
    limit = _discovery_limit(payload)
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or payload.get("candidate_count") != len(candidates):
        raise CandidateReviewError("Candidate input count does not reconcile.")

    adjudicated_at = datetime.now(UTC).isoformat()
    items: list[CandidateReviewItem] = []
    seen_pmids: set[str] = set()
    seen_pmcids: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise CandidateReviewError("Candidate input contains a malformed item.")
        pmid = _required_string(candidate, "pmid")
        if pmid in seen_pmids:
            raise CandidateReviewError("Candidate input contains a duplicate PMID.")
        seen_pmids.add(pmid)

        pmcid = _optional_string(candidate, "pmcid")
        if pmcid is not None:
            if pmcid in seen_pmcids:
                raise CandidateReviewError("Candidate input contains a duplicate PMCID.")
            seen_pmcids.add(pmcid)

        open_access = candidate.get("open_access")
        if not isinstance(open_access, bool):
            raise CandidateReviewError("Candidate input contains malformed OA evidence.")
        status = _required_string(candidate, "status")
        if status not in {"oa_verified", "metadata_only"}:
            raise CandidateReviewError("Candidate input contains an unsupported discovery status.")
        if open_access != (status == "oa_verified"):
            raise CandidateReviewError("Candidate OA evidence does not reconcile.")

        title = _required_string(candidate, "title")
        abstract = _optional_string(candidate, "abstract")
        reported_license = _optional_string(candidate, "license")
        pdf_url = _optional_string(candidate, "pdf_url")
        decision = _adjudicate(
            title=title,
            abstract=abstract,
            pmcid=pmcid,
            status=status,
            reported_license=reported_license,
            pdf_url=pdf_url,
        )
        items.append(
            CandidateReviewItem(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=_authors(candidate),
                publication_year=_optional_year(candidate, "publication_year"),
                venue=_optional_string(candidate, "venue"),
                doi=_optional_string(candidate, "doi"),
                pmcid=pmcid,
                open_access=open_access,
                reported_license=reported_license,
                pdf_url=pdf_url,
                discovery_status=status,
                adjudicated_at=adjudicated_at,
                duplicate_rule_result="passed_exact_identifier_uniqueness",
                evidence_provenance=("pubmed_metadata", "pmc_cloud_service"),
                **decision,
            )
        )

    return CandidateReviewWorksheet(
        schema_version=2,
        source_query=query,
        source_retstart=retstart,
        source_limit=limit,
        candidate_count=len(items),
        rules_version=ADJUDICATION_RULES_VERSION,
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
    unresolved_ambiguities: tuple[str, ...]


def _adjudicate(
    *,
    title: str,
    abstract: str | None,
    pmcid: str | None,
    status: str,
    reported_license: str | None,
    pdf_url: str | None,
) -> _AdjudicationDecision:
    inclusion = _scientific_scope(title, abstract)
    identity = "passed" if pmcid is not None else "incomplete_missing_pmcid"
    license_result = _license_result(reported_license)
    full_text = _full_text_result(pdf_url)

    if status == "metadata_only":
        return {
            "decision": "rejected",
            "reason_codes": ("NO_VERIFIED_REUSABLE_FULL_TEXT",),
            "rules_version": ADJUDICATION_RULES_VERSION,
            "inclusion_rule_result": inclusion,
            "identity_rule_result": identity,
            "license_rule_result": "not_evaluated_without_oa_record",
            "full_text_rule_result": "not_available",
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
            "rules_version": ADJUDICATION_RULES_VERSION,
            "inclusion_rule_result": inclusion,
            "identity_rule_result": identity,
            "license_rule_result": license_result,
            "full_text_rule_result": full_text,
            "unresolved_ambiguities": tuple(ambiguities),
        }

    return {
        "decision": "accepted",
        "reason_codes": ("ALL_REQUIRED_RULES_PASSED",),
        "rules_version": ADJUDICATION_RULES_VERSION,
        "inclusion_rule_result": inclusion,
        "identity_rule_result": identity,
        "license_rule_result": license_result,
        "full_text_rule_result": full_text,
        "unresolved_ambiguities": (),
    }


def _scientific_scope(title: str, abstract: str | None) -> str:
    normalized_title = " ".join(title.casefold().split())
    if normalized_title.startswith(_NON_PRIMARY_TITLE_PREFIXES):
        return "non_primary_content_title_evidence"

    evidence = title if abstract is None else f"{title} {abstract}"
    normalized = " ".join(evidence.casefold().split())
    has_disease = any(term in normalized for term in _DISEASE_TERMS)
    has_intervention = any(term in normalized for term in _INTERVENTION_TERMS)
    if not (has_disease and has_intervention):
        return "insufficient_title_abstract_evidence"

    has_pediatric_term = any(term in normalized_title for term in _PEDIATRIC_POPULATION_TERMS)
    has_adult_term = any(term in normalized_title for term in _ADULT_INCLUSION_TERMS)
    if has_pediatric_term and not has_adult_term:
        return "pediatric_population_title_evidence"
    return "passed"


def _license_result(reported_license: str | None) -> str:
    if reported_license is None:
        return "incomplete_missing_license"
    normalized = " ".join(reported_license.upper().split())
    return (
        "passed" if _ALLOWED_LICENSE_PATTERN.fullmatch(normalized) else "unsupported_license_basis"
    )


def license_deed_url(license_type: str) -> str:
    """Canonical Creative Commons deed URL for an allowed license string.

    Raises ValueError if `license_type` does not match `_ALLOWED_LICENSE_PATTERN`,
    so callers only ever reuse this single source of truth for what counts as
    an unrestricted license, rather than re-deriving license semantics.
    """

    normalized = " ".join(license_type.upper().split())
    if not _ALLOWED_LICENSE_PATTERN.fullmatch(normalized):
        raise ValueError(f"Unsupported license type: {license_type!r}")
    parts = normalized.split(" ")
    if parts[0] == "CC0":
        version = parts[1] if len(parts) > 1 else "1.0"
        return f"https://creativecommons.org/publicdomain/zero/{version}/"
    version = parts[2] if len(parts) > 2 else "4.0"
    return f"https://creativecommons.org/licenses/by/{version}/"


def _full_text_result(pdf_url: str | None) -> str:
    if pdf_url is None:
        return "incomplete_missing_pdf_url"
    parsed = urlparse(pdf_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != PMC_CLOUD_PDF_HOST
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not parsed.path.lower().endswith(".pdf")
    ):
        return "invalid_approved_pdf_url"
    return "passed"


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CandidateReviewError("Candidate input is missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CandidateReviewError("Candidate input contains malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _authors(payload: dict[str, object]) -> tuple[str, ...]:
    value = payload.get("authors", [])
    if not isinstance(value, list) or not all(
        isinstance(author, str) and author.strip() for author in value
    ):
        raise CandidateReviewError("Candidate input contains malformed author evidence.")
    return tuple(author.strip() for author in value)


def _optional_year(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 9999:
        raise CandidateReviewError("Candidate input contains malformed publication evidence.")
    return value


def _discovery_limit(payload: dict[str, object]) -> int:
    single_page_limit = payload.get("limit")
    batch_limit = payload.get("requested_limit")
    if single_page_limit is not None and batch_limit is not None:
        if single_page_limit != batch_limit:
            raise CandidateReviewError("Candidate input contains conflicting discovery limits.")
        return _required_positive_int(payload, "limit")
    if single_page_limit is not None:
        return _required_positive_int(payload, "limit")
    if batch_limit is not None:
        return _required_positive_int(payload, "requested_limit")
    raise CandidateReviewError("Candidate input is missing a discovery limit.")


def _required_positive_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CandidateReviewError("Candidate input contains malformed discovery metadata.")
    return value


def _required_nonnegative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CandidateReviewError("Candidate input contains malformed discovery metadata.")
    return value
