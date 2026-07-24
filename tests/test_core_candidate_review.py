from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from knowledge_engine.core_candidate_review import (
    CORE_ADJUDICATION_RULES_VERSION,
    CoreCandidateReviewError,
    prepare_core_candidate_review,
)


def _write_candidates(
    path: Path,
    candidates: list[dict[str, object]],
    *,
    query: str = "semaglutide obesity",
    offset: int = 0,
    limit: int = 25,
) -> None:
    path.write_text(
        json.dumps(
            {
                "query": query,
                "offset": offset,
                "next_offset": None,
                "limit": limit,
                "total_hits": len(candidates),
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        ),
        encoding="utf-8",
    )


def _candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "core_id": "12345",
        "doi": "10.1000/example",
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "abstract": None,
        "authors": ["Ada Lovelace"],
        "publication_year": 2024,
        "venue": "Journal of Verified Results",
        "document_type": "research",
        "pdf_url": "https://core.ac.uk/download/12345.pdf",
        "pdf_host": "core.ac.uk",
        "source_fulltext_urls": [],
    }
    base.update(overrides)
    return base


def test_complete_candidate_is_still_held_on_missing_license(tmp_path: Path) -> None:
    """CORE never supplies a license field -- see module docstring. Even a
    candidate that clears every other rule must land in `held`, never
    `accepted`, because there is no license evidence to pass."""

    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_core_candidate_review(candidates)

    assert worksheet.schema_version == 1
    assert worksheet.rules_version == CORE_ADJUDICATION_RULES_VERSION
    assert worksheet.candidate_count == 1
    assert worksheet.source_limit == 25
    item = worksheet.items[0]
    assert item.core_id == "12345"
    assert item.decision == "held"
    assert "LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED" in item.reason_codes
    assert item.inclusion_rule_result == "passed"
    assert item.identity_rule_result == "passed"
    assert item.license_rule_result == "incomplete_missing_license"
    assert item.full_text_rule_result == "passed"
    assert item.duplicate_rule_result == "passed_exact_identifier_uniqueness"
    assert "license" in item.unresolved_ambiguities
    assert datetime.fromisoformat(item.adjudicated_at).tzinfo is not None


def test_candidate_missing_doi_is_held(tmp_path: Path) -> None:
    candidate = _candidate(doi=None)
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_core_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "IDENTITY_EVIDENCE_INCOMPLETE" in item.reason_codes
    assert item.identity_rule_result == "incomplete_missing_doi"
    assert "identity" in item.unresolved_ambiguities


def test_candidate_with_only_third_party_pdf_host_is_held(tmp_path: Path) -> None:
    candidate = _candidate(
        pdf_url="https://example.org/preprint.pdf",
        pdf_host="example.org",
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_core_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "APPROVED_FULL_TEXT_LOCATION_INVALID" in item.reason_codes
    assert item.full_text_rule_result == "held_third_party_host"


def test_candidate_missing_pdf_url_is_held(tmp_path: Path) -> None:
    candidate = _candidate(pdf_url=None, pdf_host=None)
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_core_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.full_text_rule_result == "incomplete_missing_pdf_url"


def test_candidate_with_insufficient_scope_evidence_is_held(tmp_path: Path) -> None:
    candidate = _candidate(title="A survey of unrelated topics in materials science")
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_core_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "SCIENTIFIC_SCOPE_INSUFFICIENT" in item.reason_codes
    assert item.inclusion_rule_result == "insufficient_title_abstract_evidence"


def test_duplicate_core_id_is_rejected_before_adjudication(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate(), _candidate()])

    with pytest.raises(CoreCandidateReviewError, match="duplicate id"):
        prepare_core_candidate_review(candidates)


def test_duplicate_doi_is_rejected_before_adjudication(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(
        candidates,
        [_candidate(core_id="1"), _candidate(core_id="2")],
    )

    with pytest.raises(CoreCandidateReviewError, match="duplicate DOI"):
        prepare_core_candidate_review(candidates)


def test_duplicate_doi_is_detected_despite_casing_and_url_prefix(tmp_path: Path) -> None:
    """Mirrors the Codex finding fixed on PR #158 (Europe PMC, M34): exact-
    string DOI comparison misses real duplicates that differ only by casing
    or a `https://doi.org/` prefix. `normalize_doi` is applied from the
    start here rather than discovered as a bug later."""

    candidates = tmp_path / "candidates.json"
    _write_candidates(
        candidates,
        [
            _candidate(core_id="1", doi="10.1000/ABC"),
            _candidate(core_id="2", doi="https://doi.org/10.1000/abc"),
        ],
    )

    with pytest.raises(CoreCandidateReviewError, match="duplicate DOI"):
        prepare_core_candidate_review(candidates)


def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    candidate = _candidate()
    del candidate["title"]
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    with pytest.raises(CoreCandidateReviewError, match="missing required evidence"):
        prepare_core_candidate_review(candidates)


def test_candidate_input_count_must_reconcile(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            {
                "query": "semaglutide",
                "offset": 0,
                "limit": 25,
                "total_hits": 5,
                "candidate_count": 5,
                "candidates": [_candidate()],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CoreCandidateReviewError, match="count does not reconcile"):
        prepare_core_candidate_review(candidates)


def test_rejects_a_symlinked_input(tmp_path: Path) -> None:
    real_path = tmp_path / "real.json"
    _write_candidates(real_path, [_candidate()])
    symlink_path = tmp_path / "link.json"
    symlink_path.symlink_to(real_path)

    with pytest.raises(CoreCandidateReviewError, match="symbolic link"):
        prepare_core_candidate_review(symlink_path)


def test_worksheet_to_json_round_trips_stable_output(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_core_candidate_review(candidates)
    payload = json.loads(worksheet.to_json())

    assert payload["rules_version"] == CORE_ADJUDICATION_RULES_VERSION
    assert payload["candidate_count"] == 1
    assert payload["items"][0]["decision"] == "held"
