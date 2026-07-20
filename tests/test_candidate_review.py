from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_engine.candidate_review import CandidateReviewError, prepare_candidate_review


def _write_candidates(
    path: Path,
    candidates: list[dict[str, object]],
    *,
    limit_key: str = "limit",
    limit: int = 25,
) -> None:
    path.write_text(
        json.dumps(
            {
                "query": "GLP-1 obesity",
                "retstart": 0,
                limit_key: limit,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        ),
        encoding="utf-8",
    )


def _candidate() -> dict[str, object]:
    return {
        "pmid": "100",
        "title": "Trial title",
        "doi": "10.1000/example",
        "pmcid": "PMC100",
        "open_access": True,
        "license": "CC BY",
        "pdf_url": "https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_pdf/example.pdf",
        "xml_url": None,
        "status": "oa_verified",
    }


def test_prepare_candidate_review_is_pending_only(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_candidate_review(candidates)

    assert worksheet.schema_version == 1
    assert worksheet.candidate_count == 1
    assert worksheet.source_limit == 25
    item = worksheet.items[0]
    assert item.pmid == "100"
    assert item.reported_license == "CC BY"
    assert item.decision == "pending"
    assert item.inclusion_review == ""
    assert item.license_review == ""
    assert item.identity_review == ""
    assert "approvals" not in worksheet.to_json()


def test_prepare_candidate_review_accepts_batch_discovery_limit(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(
        candidates,
        [_candidate()],
        limit_key="requested_limit",
        limit=500,
    )

    worksheet = prepare_candidate_review(candidates)

    assert worksheet.source_limit == 500
    assert worksheet.candidate_count == 1
    assert worksheet.items[0].decision == "pending"


def test_conflicting_discovery_limits_are_rejected(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    payload = {
        "query": "GLP-1 obesity",
        "retstart": 0,
        "limit": 25,
        "requested_limit": 500,
        "candidate_count": 1,
        "candidates": [_candidate()],
    }
    candidates.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CandidateReviewError, match="conflicting discovery limits"):
        prepare_candidate_review(candidates)


def test_duplicate_pmid_is_rejected(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate(), _candidate()])

    with pytest.raises(CandidateReviewError, match="duplicate PMID"):
        prepare_candidate_review(candidates)


def test_inconsistent_oa_status_is_rejected(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["open_access"] = False
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    with pytest.raises(CandidateReviewError, match="does not reconcile"):
        prepare_candidate_review(candidates)
