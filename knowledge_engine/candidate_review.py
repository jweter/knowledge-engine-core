"""Deterministic adjudication worksheets for PubMed/PMC candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ADJUDICATION_RULES_VERSION = "m14-candidate-adjudication-v1"
_ALLOWED_LICENSE_PREFIXES = ("CC BY", "CC0")
_GLP1_TERMS = ("glp-1", "glp1", "glucagon-like peptide-1")
_WEIGHT_TERMS = ("obesity", "obese", "weight loss", "body weight", "adiposity")


class CandidateReviewError(RuntimeError):
    """Sanitized candidate-adjudication preparation failure."""


@dataclass(frozen=True)
class CandidateReviewItem:
    """One candidate with an explicit deterministic adjudication result."""

    pmid: str
    title: str
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

    adjudicated_at = datetime.now(timezone.utc).isoformat()
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
        reported_license = _optional_string(candidate, "license")
        pdf_url = _optional_string(candidate, "pdf_url")
        decision = _adjudicate(
            title=title,
            pmcid=pmcid,
            status=status,
            reported_license=reported_license,
            pdf_url=pdf_url,
        )
        items.append(
            CandidateReviewItem(
                pmid=pmid,
                title=title,
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
                evidence_provenance=("pubmed_metadata", "pmc_oa_service"),
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


def _adjudicate(
    *,
    title: str,
    pmcid: str | None,
    status: str,
    reported_license: str | None,
    pdf_url: str | None,
) -> dict[str, object]:
    inclusion = _scientific_scope(title)
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


def _scientific_scope(title: str) -> str:
    normalized = title.casefold()
    has_glp1 = any(term in normalized for term in _GLP1_TERMS)
    has_weight = any(term in normalized for term in _WEIGHT_TERMS)
    return "passed" if has_glp1 and has_weight else "insufficient_title_evidence"


def _license_result(reported_license: str | None) -> str:
    if reported_license is None:
        return "incomplete_missing_license"
    normalized = " ".join(reported_license.upper().split())
    return (
        "passed"
        if normalized.startswith(_ALLOWED_LICENSE_PREFIXES)
        else "unsupported_license_basis"
    )


def _full_text_result(pdf_url: str | None) -> str:
    if pdf_url is None:
        return "incomplete_missing_pdf_url"
    parsed = urlparse(pdf_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "ftp.ncbi.nlm.nih.gov"
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
    raise CandidateReviewError("Candidate input is missing required discovery limits.")


def _required_nonnegative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CandidateReviewError("Candidate input contains an invalid page offset.")
    return value


def _required_positive_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CandidateReviewError("Candidate input contains an invalid discovery limit.")
    return value
