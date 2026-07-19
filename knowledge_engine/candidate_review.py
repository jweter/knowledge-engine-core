"""Deterministic human-review worksheets for PubMed/PMC candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


class CandidateReviewError(RuntimeError):
    """Sanitized candidate-review preparation failure."""


@dataclass(frozen=True)
class CandidateReviewItem:
    """One candidate awaiting explicit human scientific and legal review."""

    pmid: str
    title: str
    doi: str | None
    pmcid: str | None
    open_access: bool
    reported_license: str | None
    pdf_url: str | None
    discovery_status: str
    decision: str = "pending"
    inclusion_review: str = ""
    license_review: str = ""
    identity_review: str = ""
    reviewer: str = ""
    reviewed_at: str = ""


@dataclass(frozen=True)
class CandidateReviewWorksheet:
    """Stable review worksheet that cannot itself authorize acquisition."""

    schema_version: int
    source_query: str
    source_retstart: int
    source_limit: int
    candidate_count: int
    items: tuple[CandidateReviewItem, ...]

    def to_json(self) -> str:
        """Render deterministic JSON for manual review."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def prepare_candidate_review(candidates_path: Path) -> CandidateReviewWorksheet:
    """Validate discovery output and create pending-only review records."""

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
    limit = _required_positive_int(payload, "limit")
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or payload.get("candidate_count") != len(candidates):
        raise CandidateReviewError("Candidate input count does not reconcile.")

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

        items.append(
            CandidateReviewItem(
                pmid=pmid,
                title=_required_string(candidate, "title"),
                doi=_optional_string(candidate, "doi"),
                pmcid=pmcid,
                open_access=open_access,
                reported_license=_optional_string(candidate, "license"),
                pdf_url=_optional_string(candidate, "pdf_url"),
                discovery_status=status,
            )
        )

    return CandidateReviewWorksheet(
        schema_version=1,
        source_query=query,
        source_retstart=retstart,
        source_limit=limit,
        candidate_count=len(items),
        items=tuple(items),
    )


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


def _required_nonnegative_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CandidateReviewError("Candidate input contains an invalid page offset.")
    return value


def _required_positive_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise CandidateReviewError("Candidate input contains an invalid page limit.")
    return value
