"""Deterministic adjudication worksheets for CORE candidates.

Mirrors `candidate_review.py` (M14) and `europepmc_candidate_review.py`
(M34)'s accept/reject/hold-with-reason-codes shape, but is a third,
independently versioned engine rather than a retrofit of either: CORE's
evidence shape is genuinely different, not just a relabeling.

Most consequentially, CORE's API never returns a license field (confirmed
empirically -- see `core_discovery.py`'s module docstring). There is
therefore no license evidence this engine could ever pass: every CORE
candidate's `license_rule_result` is `"incomplete_missing_license"`, which
means **no CORE candidate can ever auto-accept**. A candidate that clears
every other rule still lands in `held`, pending a human visiting the
original source to confirm reuse terms. This is a deliberate, honest
consequence of CORE's real API contract, not a bug to work around.

This engine also does not attempt PMC-overlap detection (the equivalent of
`europepmc_candidate_review.py`'s `DUPLICATE_OF_PMC_PIPELINE_SCOPE` rule):
CORE's response never includes a PMCID, and checking overlap would require
an extra network round-trip per candidate against a different service. This
is a known, deliberate limitation for this milestone -- human reviewers
should sanity-check obviously-duplicate DOIs during working-version
acceptance review, per the project's existing corpus-review process.

Scientific-scope and license rules ARE shared -- see
`scientific_scope.py`/`license_rules.py` -- since those criteria are the
same regardless of which discovery source found a candidate.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlparse

from knowledge_engine.core_discovery import CORE_PDF_HOST
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.scientific_scope import (
    GLP1_METABOLIC_SCOPE,
    ScopeVocabulary,
    evaluate_scientific_scope,
)
from knowledge_engine.utils import normalize_doi

CORE_ADJUDICATION_RULES_VERSION = "m35-core-candidate-adjudication-v1"


class CoreCandidateReviewError(RuntimeError):
    """Sanitized candidate-adjudication preparation failure."""


@dataclass(frozen=True)
class CoreCandidateReviewItem:
    """One candidate with an explicit deterministic adjudication result."""

    core_id: str
    doi: str | None
    title: str
    abstract: str | None
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    document_type: str | None
    pdf_url: str | None
    pdf_host: str | None
    source_fulltext_urls: tuple[str, ...]
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
class CoreCandidateReviewWorksheet:
    """Stable adjudication worksheet that cannot itself authorize acquisition."""

    schema_version: int
    source_query: str
    source_offset: int
    source_limit: int
    candidate_count: int
    rules_version: str
    items: tuple[CoreCandidateReviewItem, ...]

    def to_json(self) -> str:
        """Render stable, auditable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def prepare_core_candidate_review(
    candidates_path: Path,
    *,
    vocabulary: ScopeVocabulary = GLP1_METABOLIC_SCOPE,
) -> CoreCandidateReviewWorksheet:
    """Validate discovery output and create explicit adjudication records.

    `vocabulary` defaults to the original GLP-1/metabolic-disease scope
    terms -- pass a different `ScopeVocabulary` (see
    `knowledge_engine.scientific_scope`) to adjudicate a different corpus.
    """

    if candidates_path.is_symlink():
        raise CoreCandidateReviewError("Candidate input must not be a symbolic link.")
    try:
        payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CoreCandidateReviewError("Candidate input is not valid discovery JSON.") from exc
    if not isinstance(payload, dict):
        raise CoreCandidateReviewError("Candidate input is not valid discovery JSON.")

    query = _required_string(payload, "query")
    offset = _required_non_negative_int(payload, "offset")
    limit = _required_positive_int(payload, "limit")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or payload.get("candidate_count") != len(candidates):
        raise CoreCandidateReviewError("Candidate input count does not reconcile.")

    adjudicated_at = datetime.now(UTC).isoformat()
    items: list[CoreCandidateReviewItem] = []
    seen_ids: set[str] = set()
    seen_dois: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise CoreCandidateReviewError("Candidate input contains a malformed item.")
        core_id = _required_string(candidate, "core_id")
        if core_id in seen_ids:
            raise CoreCandidateReviewError("Candidate input contains a duplicate id.")
        seen_ids.add(core_id)

        doi = _optional_string(candidate, "doi")
        duplicate_rule_result = "passed_exact_identifier_uniqueness"
        if doi is not None:
            normalized_doi = normalize_doi(doi)
            if normalized_doi in seen_dois:
                raise CoreCandidateReviewError("Candidate input contains a duplicate DOI.")
            seen_dois.add(normalized_doi)

        title = _required_string(candidate, "title")
        abstract = _optional_string(candidate, "abstract")
        pdf_url = _optional_string(candidate, "pdf_url")
        pdf_host = _optional_string(candidate, "pdf_host")
        decision = _adjudicate(
            title=title,
            abstract=abstract,
            doi=doi,
            pdf_url=pdf_url,
            pdf_host=pdf_host,
            vocabulary=vocabulary,
        )
        items.append(
            CoreCandidateReviewItem(
                core_id=core_id,
                doi=doi,
                title=title,
                abstract=abstract,
                authors=_authors(candidate),
                publication_year=_optional_year(candidate, "publication_year"),
                venue=_optional_string(candidate, "venue"),
                document_type=_optional_string(candidate, "document_type"),
                pdf_url=pdf_url,
                pdf_host=pdf_host,
                source_fulltext_urls=_string_list(candidate, "source_fulltext_urls"),
                adjudicated_at=adjudicated_at,
                duplicate_rule_result=duplicate_rule_result,
                evidence_provenance=("core_search",),
                **decision,
            )
        )

    return CoreCandidateReviewWorksheet(
        schema_version=1,
        source_query=query,
        source_offset=offset,
        source_limit=limit,
        candidate_count=len(items),
        rules_version=CORE_ADJUDICATION_RULES_VERSION,
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
    doi: str | None,
    pdf_url: str | None,
    pdf_host: str | None,
    vocabulary: ScopeVocabulary = GLP1_METABOLIC_SCOPE,
) -> _AdjudicationDecision:
    inclusion = evaluate_scientific_scope(title, abstract, vocabulary=vocabulary)
    identity = "passed" if doi is not None else "incomplete_missing_doi"
    license_result = evaluate_license(None)
    full_text = _full_text_result(pdf_url, pdf_host)

    ambiguities: list[str] = []
    reasons: list[str] = []
    if inclusion != "passed":
        ambiguities.append("scientific_relevance")
        reasons.append("SCIENTIFIC_SCOPE_INSUFFICIENT")
    if identity != "passed":
        ambiguities.append("identity")
        reasons.append("IDENTITY_EVIDENCE_INCOMPLETE")
    ambiguities.append("license")
    reasons.append("LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED")
    if full_text != "passed":
        ambiguities.append("full_text")
        reasons.append("APPROVED_FULL_TEXT_LOCATION_INVALID")

    return {
        "decision": "held",
        "reason_codes": tuple(reasons),
        "rules_version": CORE_ADJUDICATION_RULES_VERSION,
        "inclusion_rule_result": inclusion,
        "identity_rule_result": identity,
        "license_rule_result": license_result,
        "full_text_rule_result": full_text,
        "unresolved_ambiguities": tuple(ambiguities),
    }


def _full_text_result(pdf_url: str | None, pdf_host: str | None) -> str:
    if pdf_url is None or pdf_host is None:
        return "incomplete_missing_pdf_url"
    if pdf_host != CORE_PDF_HOST:
        return "held_third_party_host"
    parsed = urlparse(pdf_url)
    try:
        port = parsed.port
    except ValueError:
        return "invalid_approved_pdf_url"
    if (
        parsed.scheme != "https"
        or parsed.hostname != CORE_PDF_HOST
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return "invalid_approved_pdf_url"
    return "passed"


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CoreCandidateReviewError("Candidate input is missing required evidence.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise CoreCandidateReviewError("Candidate input contains malformed evidence.")
    normalized = value.strip()
    return normalized or None


def _string_list(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise CoreCandidateReviewError("Candidate input contains malformed evidence.")
    return tuple(item.strip() for item in value)


def _authors(payload: dict[str, object]) -> tuple[str, ...]:
    value = payload.get("authors", [])
    if not isinstance(value, list) or not all(
        isinstance(author, str) and author.strip() for author in value
    ):
        raise CoreCandidateReviewError("Candidate input contains malformed author evidence.")
    return tuple(author.strip() for author in value)


def _optional_year(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1000 <= value <= 9999:
        raise CoreCandidateReviewError("Candidate input contains malformed publication evidence.")
    return value


def _required_positive_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CoreCandidateReviewError("Candidate input contains malformed discovery metadata.")
    return value


def _required_non_negative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CoreCandidateReviewError("Candidate input contains malformed discovery metadata.")
    return value
