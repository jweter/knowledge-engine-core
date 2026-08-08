from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from knowledge_engine.europepmc_candidate_review import (
    EUROPEPMC_ADJUDICATION_RULES_VERSION,
    EuropePmcCandidateReviewError,
    prepare_europepmc_candidate_review,
)
from knowledge_engine.scientific_scope import ONCOLOGY_NSCLC_CHECKPOINT_SCOPE


def _write_candidates(
    path: Path,
    candidates: list[dict[str, object]],
    *,
    query: str = "semaglutide AND OPEN_ACCESS:Y",
    cursor_mark: str = "*",
    limit: int = 25,
) -> None:
    path.write_text(
        json.dumps(
            {
                "query": query,
                "cursor_mark": cursor_mark,
                "next_cursor_mark": None,
                "limit": limit,
                "candidate_count": len(candidates),
                "candidates": candidates,
            }
        ),
        encoding="utf-8",
    )


def _candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "europepmc_id": "PPR123",
        "source": "PPR",
        "pmid": "111",
        "pmcid": None,
        "doi": "10.1000/example",
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "abstract": None,
        "authors": ["Ada Lovelace"],
        "publication_year": 2024,
        "venue": "Journal of Verified Results",
        "in_pmc": False,
        "open_access": True,
        "license": "CC BY 4.0",
        "pdf_url": "https://europepmc.org/api/fulltextRepo?pprId=PPR123",
        "pdf_host": "europepmc.org",
    }
    base.update(overrides)
    return base


def test_oncology_vocabulary_changes_the_inclusion_outcome(tmp_path: Path) -> None:
    glp1_candidates = tmp_path / "glp1.json"
    _write_candidates(glp1_candidates, [_candidate()])
    oncology_candidates = tmp_path / "oncology.json"
    _write_candidates(
        oncology_candidates,
        [_candidate(title="Pembrolizumab therapy for adults with non-small-cell lung cancer")],
    )

    glp1_under_oncology = prepare_europepmc_candidate_review(
        glp1_candidates, vocabulary=ONCOLOGY_NSCLC_CHECKPOINT_SCOPE
    )
    oncology_under_oncology = prepare_europepmc_candidate_review(
        oncology_candidates, vocabulary=ONCOLOGY_NSCLC_CHECKPOINT_SCOPE
    )

    assert (
        glp1_under_oncology.items[0].inclusion_rule_result == "insufficient_title_abstract_evidence"
    )
    assert oncology_under_oncology.items[0].inclusion_rule_result == "passed"


def test_complete_oa_candidate_is_accepted(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_europepmc_candidate_review(candidates)

    assert worksheet.schema_version == 1
    assert worksheet.rules_version == EUROPEPMC_ADJUDICATION_RULES_VERSION
    assert worksheet.candidate_count == 1
    assert worksheet.source_limit == 25
    item = worksheet.items[0]
    assert item.europepmc_id == "PPR123"
    assert item.decision == "accepted"
    assert item.reason_codes == ("ALL_REQUIRED_RULES_PASSED",)
    assert item.inclusion_rule_result == "passed"
    assert item.identity_rule_result == "passed"
    assert item.license_rule_result == "passed"
    assert item.full_text_rule_result == "passed"
    assert item.pmc_overlap_rule_result == "passed"
    assert item.duplicate_rule_result == "passed_exact_identifier_uniqueness"
    assert item.unresolved_ambiguities == ()
    assert datetime.fromisoformat(item.adjudicated_at).tzinfo is not None


def test_non_open_access_candidate_is_rejected(tmp_path: Path) -> None:
    candidate = _candidate(open_access=False)
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "rejected"
    assert item.reason_codes == ("NO_VERIFIED_REUSABLE_FULL_TEXT",)
    assert item.full_text_rule_result == "not_available"


def test_candidate_already_in_pmc_is_rejected_as_out_of_scope(tmp_path: Path) -> None:
    candidate = _candidate(in_pmc=True, pmcid="PMC999")
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "rejected"
    assert item.reason_codes == ("DUPLICATE_OF_PMC_PIPELINE_SCOPE",)
    assert item.pmc_overlap_rule_result == "out_of_scope_already_in_pmc"


def test_candidate_missing_doi_is_held(tmp_path: Path) -> None:
    candidate = _candidate(doi=None)
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "IDENTITY_EVIDENCE_INCOMPLETE" in item.reason_codes
    assert item.identity_rule_result == "incomplete_missing_doi"
    assert "identity" in item.unresolved_ambiguities


def test_candidate_with_restrictive_license_is_held(tmp_path: Path) -> None:
    candidate = _candidate(license="CC BY-NC-ND 4.0")
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED" in item.reason_codes
    assert item.license_rule_result == "unsupported_license_basis"


def test_candidate_with_only_third_party_pdf_host_is_held(tmp_path: Path) -> None:
    candidate = _candidate(
        pdf_url="https://example.org/preprint.pdf",
        pdf_host="example.org",
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "APPROVED_FULL_TEXT_LOCATION_INVALID" in item.reason_codes
    assert item.full_text_rule_result == "held_third_party_host"


def test_candidate_missing_pdf_url_is_held(tmp_path: Path) -> None:
    candidate = _candidate(pdf_url=None, pdf_host=None)
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.full_text_rule_result == "incomplete_missing_pdf_url"


def test_candidate_with_insufficient_scope_evidence_is_held(tmp_path: Path) -> None:
    candidate = _candidate(title="A survey of unrelated topics in materials science")
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_europepmc_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert "SCIENTIFIC_SCOPE_INSUFFICIENT" in item.reason_codes
    assert item.inclusion_rule_result == "insufficient_title_abstract_evidence"


def test_duplicate_europepmc_id_is_rejected_before_adjudication(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate(), _candidate()])

    with pytest.raises(EuropePmcCandidateReviewError, match="duplicate id"):
        prepare_europepmc_candidate_review(candidates)


def test_duplicate_doi_is_rejected_before_adjudication(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(
        candidates,
        [_candidate(europepmc_id="PPR1"), _candidate(europepmc_id="PPR2")],
    )

    with pytest.raises(EuropePmcCandidateReviewError, match="duplicate DOI"):
        prepare_europepmc_candidate_review(candidates)


def test_duplicate_doi_is_detected_despite_casing_and_url_prefix(tmp_path: Path) -> None:
    """Codex finding on PR #158: exact-string DOI comparison missed real duplicates.

    DOIs are case-insensitive and may appear with or without the
    `https://doi.org/` prefix; `normalize_doi` (already used elsewhere in
    this project for the same reason) must be applied before comparison.
    """

    candidates = tmp_path / "candidates.json"
    _write_candidates(
        candidates,
        [
            _candidate(europepmc_id="PPR1", doi="10.1000/ABC"),
            _candidate(europepmc_id="PPR2", doi="https://doi.org/10.1000/abc"),
        ],
    )

    with pytest.raises(EuropePmcCandidateReviewError, match="duplicate DOI"):
        prepare_europepmc_candidate_review(candidates)


def test_missing_required_field_is_rejected(tmp_path: Path) -> None:
    candidate = _candidate()
    del candidate["title"]
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    with pytest.raises(EuropePmcCandidateReviewError, match="missing required evidence"):
        prepare_europepmc_candidate_review(candidates)


def test_candidate_input_count_must_reconcile(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    candidates.write_text(
        json.dumps(
            {
                "query": "semaglutide",
                "cursor_mark": "*",
                "limit": 25,
                "candidate_count": 5,
                "candidates": [_candidate()],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(EuropePmcCandidateReviewError, match="count does not reconcile"):
        prepare_europepmc_candidate_review(candidates)


def test_rejects_a_symlinked_input(tmp_path: Path) -> None:
    real_path = tmp_path / "real.json"
    _write_candidates(real_path, [_candidate()])
    symlink_path = tmp_path / "link.json"
    symlink_path.symlink_to(real_path)

    with pytest.raises(EuropePmcCandidateReviewError, match="symbolic link"):
        prepare_europepmc_candidate_review(symlink_path)


def test_worksheet_to_json_round_trips_stable_output(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_europepmc_candidate_review(candidates)
    payload = json.loads(worksheet.to_json())

    assert payload["rules_version"] == EUROPEPMC_ADJUDICATION_RULES_VERSION
    assert payload["candidate_count"] == 1
    assert payload["items"][0]["decision"] == "accepted"
