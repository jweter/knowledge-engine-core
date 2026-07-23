from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from knowledge_engine.candidate_review import (
    ADJUDICATION_RULES_VERSION,
    CandidateReviewError,
    license_deed_url,
    prepare_candidate_review,
)


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
                "query": "obesity and metabolic disease therapeutics",
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
        "title": "GLP-1 receptor agonist treatment for obesity and weight loss",
        "abstract": None,
        "doi": "10.1000/example",
        "pmcid": "PMC100",
        "open_access": True,
        "license": "CC BY 4.0",
        "pdf_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC100.1/PMC100.1.pdf",
        "xml_url": None,
        "status": "oa_verified",
    }


def test_complete_oa_candidate_is_accepted(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [_candidate()])

    worksheet = prepare_candidate_review(candidates)

    assert worksheet.schema_version == 2
    assert worksheet.rules_version == ADJUDICATION_RULES_VERSION
    assert worksheet.candidate_count == 1
    assert worksheet.source_limit == 25
    item = worksheet.items[0]
    assert item.pmid == "100"
    assert item.abstract is None
    assert item.reported_license == "CC BY 4.0"
    assert item.decision == "accepted"
    assert item.reason_codes == ("ALL_REQUIRED_RULES_PASSED",)
    assert item.inclusion_rule_result == "passed"
    assert item.identity_rule_result == "passed"
    assert item.license_rule_result == "passed"
    assert item.full_text_rule_result == "passed"
    assert item.duplicate_rule_result == "passed_exact_identifier_uniqueness"
    assert item.unresolved_ambiguities == ()
    assert datetime.fromisoformat(item.adjudicated_at).tzinfo is not None
    assert "approvals" not in worksheet.to_json()


def test_non_glp1_metabolic_therapy_candidate_is_accepted(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["title"] = "Metformin therapy for type 2 diabetes in adults"
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    assert worksheet.items[0].decision == "accepted"
    assert worksheet.items[0].inclusion_rule_result == "passed"


def test_abstract_can_supply_complete_scientific_scope_evidence(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["title"] = "Cardiovascular outcomes in a randomized clinical trial"
    candidate["abstract"] = (
        "Adults with obesity received semaglutide therapy or placebo for 68 weeks."
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.abstract == candidate["abstract"]
    assert item.decision == "accepted"
    assert item.inclusion_rule_result == "passed"


def test_metadata_only_candidate_is_explicitly_rejected(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate.update(
        {
            "pmcid": None,
            "open_access": False,
            "license": None,
            "pdf_url": None,
            "status": "metadata_only",
        }
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "rejected"
    assert item.reason_codes == ("NO_VERIFIED_REUSABLE_FULL_TEXT",)
    assert item.unresolved_ambiguities == ()


def test_oa_candidate_with_insufficient_scope_evidence_is_held(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["title"] = "Cardiovascular outcomes in a randomized clinical trial"
    candidate["abstract"] = "Participants were followed for cardiovascular events."
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.inclusion_rule_result == "insufficient_title_abstract_evidence"
    assert item.reason_codes == ("SCIENTIFIC_SCOPE_INSUFFICIENT",)
    assert item.unresolved_ambiguities == ("scientific_relevance",)


def test_pediatric_titled_candidate_is_held_not_accepted(tmp_path: Path) -> None:
    """v7 regression: a title matching disease+intervention terms used to be
    accepted even when it announced a pediatric-only population, because no
    rule checked population scope at all -- exclusion_criteria.md requires
    excluding sources "limited to pediatric populations"."""

    candidate = _candidate()
    candidate["title"] = "Children's gut microbiota predicts the efficacy of obesity treatment"
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.inclusion_rule_result == "pediatric_population_title_evidence"
    assert item.reason_codes == ("SCIENTIFIC_SCOPE_INSUFFICIENT",)


def test_mixed_age_title_with_adult_term_is_not_held_as_pediatric(tmp_path: Path) -> None:
    """`exclusion_criteria.md` excludes sources "limited to" pediatric
    populations, not merely mentioning one -- a title naming an adult
    population too is mixed-age evidence, not pediatric-only, so the
    pediatric-population check must not hold it."""

    candidate = _candidate()
    candidate["title"] = "Semaglutide treatment for obesity in adolescents and adults"
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "accepted"
    assert item.inclusion_rule_result == "passed"


def test_pediatric_term_only_in_abstract_does_not_block_acceptance(tmp_path: Path) -> None:
    """The pediatric-population check only reads the title -- an adult study
    whose abstract mentions pediatric research as background context is not
    itself a pediatric-population source."""

    candidate = _candidate()
    candidate["title"] = "Semaglutide treatment for obesity in adults: a randomized trial"
    candidate["abstract"] = (
        "Building on prior pediatric obesity research, this trial enrolled adults "
        "with obesity to receive semaglutide or placebo."
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "accepted"
    assert item.inclusion_rule_result == "passed"


@pytest.mark.parametrize(
    "prefix",
    [
        "Correction: ",
        "Corrigendum: ",
        "Erratum: ",
        "Retraction: ",
        "Publisher Correction: ",
        "Author Correction: ",
    ],
)
def test_correction_notice_title_is_held_not_accepted(tmp_path: Path, prefix: str) -> None:
    """v8 regression: a correction/erratum notice for an original article is
    not itself a scientific paper -- it typically only amends a figure,
    table, or author list -- but used to be accepted whenever its title
    (inherited from the original article) happened to match disease and
    intervention terms."""

    candidate = _candidate()
    candidate["title"] = (
        f"{prefix}SGLT2 inhibitor use and disparities in all-cause mortality "
        "in type 2 diabetes: insights from a multi-ethnic population"
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.inclusion_rule_result == "non_primary_content_title_evidence"
    assert item.reason_codes == ("SCIENTIFIC_SCOPE_INSUFFICIENT",)


def test_disease_and_intervention_evidence_from_separate_sentences_still_passes(
    tmp_path: Path,
) -> None:
    """v9: a same-sentence disease/intervention co-occurrence requirement
    (v8) was tried and reverted. It correctly held one real false positive
    Codex flagged (a case report whose abstract listed a disease only as an
    incidental patient comorbidity, unrelated to the paper's actual topic),
    but re-adjudicating a real 250-candidate discovery batch under it
    dropped 33 of 74 previously accepted records (44%) -- almost all
    legitimately on-topic papers whose structured or narrative abstracts
    simply name the disease in one sentence and describe treatment in
    another, which is routine scientific writing style, not evidence the
    paper is off-topic. The net effect was far worse than the single false
    positive it fixed, so v9 reverts to evidence anywhere in the combined
    title/abstract text, accepting that rare incidental-comorbidity false
    positives (like the hiccups case) can occasionally still pass -- this
    is judged a materially smaller cost than losing large amounts of
    legitimate corpus content, in a system that lacks a subtler
    (deterministic, non-ML) way to tell the two cases apart."""

    candidate = _candidate()
    candidate["title"] = (
        "The impact of automated insulin delivery on glucose management in "
        "people with diabetes and advanced chronic kidney disease"
    )
    candidate["abstract"] = (
        "AIMS: Chronic kidney disease complicates insulin dosing and increases "
        "glycaemic instability in diabetes. METHODS: We conducted a randomised "
        "crossover trial. Adults with type 2 diabetes and advanced chronic "
        "kidney disease were eligible. RESULTS: Automated insulin delivery "
        "improved time in range. CONCLUSION: This treatment approach was safe "
        "and effective."
    )
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "accepted"
    assert item.inclusion_rule_result == "passed"


def test_oa_candidate_with_unsupported_license_is_held(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["license"] = "Publisher free access"
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.license_rule_result == "unsupported_license_basis"
    assert "LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED" in item.reason_codes
    assert "license" in item.unresolved_ambiguities


@pytest.mark.parametrize(
    "restricted_license",
    ["CC BY-NC", "CC BY-NC-ND", "CC BY-NC-SA", "CC BY-SA", "CC BY-ND"],
)
def test_oa_candidate_with_restricted_cc_variant_is_held(
    tmp_path: Path, restricted_license: str
) -> None:
    """CC BY-NC/-ND/-SA restrict commercial use and/or derivative works and must
    not be accepted merely because they share the "CC BY" text prefix."""

    candidate = _candidate()
    candidate["license"] = restricted_license
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.license_rule_result == "unsupported_license_basis"
    assert "LICENSE_EVIDENCE_INCOMPLETE_OR_UNSUPPORTED" in item.reason_codes


@pytest.mark.parametrize(
    "allowed_license",
    ["CC BY", "CC BY 1.0", "CC BY 2.0", "CC BY 2.5", "CC BY 3.0", "CC BY 4.0", "CC0", "CC0 1.0"],
)
def test_oa_candidate_with_unrestricted_cc_variant_passes(
    tmp_path: Path, allowed_license: str
) -> None:
    candidate = _candidate()
    candidate["license"] = allowed_license
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.license_rule_result == "passed"


@pytest.mark.parametrize(
    "malformed_license",
    ["CC0 2.0", "CC BY 4..0", "CC BY 4.0.", "CC BY 99.0", "CC BY 5.0"],
)
def test_oa_candidate_with_malformed_cc_version_is_held(
    tmp_path: Path, malformed_license: str
) -> None:
    """A version string that shares the shared regex's character class but
    names a Creative Commons version that was never published (e.g. CC0 2.0,
    which doesn't exist) must not pass merely because it is digits and dots -
    passing would produce a license_url with no real deed behind it."""

    candidate = _candidate()
    candidate["license"] = malformed_license
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.license_rule_result == "unsupported_license_basis"


def test_oa_candidate_with_unapproved_pdf_host_is_held(tmp_path: Path) -> None:
    candidate = _candidate()
    candidate["pdf_url"] = "https://publisher.example/article.pdf"
    candidates = tmp_path / "candidates.json"
    _write_candidates(candidates, [candidate])

    worksheet = prepare_candidate_review(candidates)

    item = worksheet.items[0]
    assert item.decision == "held"
    assert item.full_text_rule_result == "invalid_approved_pdf_url"
    assert "APPROVED_FULL_TEXT_LOCATION_INVALID" in item.reason_codes


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
    assert worksheet.items[0].decision == "accepted"


def test_conflicting_discovery_limits_are_rejected(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.json"
    payload = {
        "query": "obesity and metabolic disease therapeutics",
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


@pytest.mark.parametrize(
    ("license_type", "expected_url"),
    [
        ("CC BY", "https://creativecommons.org/licenses/by/4.0/"),
        ("CC BY 1.0", "https://creativecommons.org/licenses/by/1.0/"),
        ("CC BY 2.0", "https://creativecommons.org/licenses/by/2.0/"),
        ("CC BY 2.5", "https://creativecommons.org/licenses/by/2.5/"),
        ("CC BY 3.0", "https://creativecommons.org/licenses/by/3.0/"),
        ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
        ("CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
        ("cc by", "https://creativecommons.org/licenses/by/4.0/"),
    ],
)
def test_license_deed_url_maps_allowed_licenses(license_type: str, expected_url: str) -> None:
    assert license_deed_url(license_type) == expected_url


@pytest.mark.parametrize(
    "license_type",
    ["CC BY-NC", "CC0 2.0", "CC BY 4..0", "CC BY 5.0", "Publisher free access"],
)
def test_license_deed_url_rejects_unsupported_licenses(license_type: str) -> None:
    with pytest.raises(ValueError, match="Unsupported license type"):
        license_deed_url(license_type)
