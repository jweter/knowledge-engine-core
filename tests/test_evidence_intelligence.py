from knowledge_engine.evidence_intelligence import (
    EvidenceConsensus,
    EvidenceQuality,
    compute_claim_confidence,
    compute_evidence_consensus,
    compute_evidence_coverage,
    compute_evidence_quality,
    render_synthesis,
)


def _manual_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": "ev-manual-001",
        "study_type": "randomized_controlled_trial",
        "extraction_method": "manual_human_review",
        "review_checklist": {"source_verified": True},
        "limitations": ["A limitation."],
        "uncertainty_notes": ["An uncertainty."],
    }
    record.update(overrides)
    return record


def _automated_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": "ev-auto-001",
        "study_type": "cohort_study",
        "extraction_method": "m52-evidence-classification-v1",
        "review_checklist": {},
        "limitations": None,
        "uncertainty_notes": None,
    }
    record.update(overrides)
    return record


def test_evidence_quality_manual_scores_higher_than_automated() -> None:
    manual = compute_evidence_quality(_manual_record())
    automated = compute_evidence_quality(_automated_record())

    assert manual.manually_reviewed is True
    assert automated.manually_reviewed is False
    assert manual.score > automated.score


def test_evidence_quality_missing_study_type_scores_lower_than_recognized() -> None:
    with_type = compute_evidence_quality(_manual_record())
    without_type = compute_evidence_quality(_manual_record(study_type=None))

    assert without_type.study_type_missing is True
    assert without_type.score < with_type.score


def test_evidence_quality_penalizes_missing_limitations_and_uncertainty() -> None:
    complete = compute_evidence_quality(_manual_record())
    incomplete = compute_evidence_quality(_manual_record(limitations=None, uncertainty_notes=None))

    # -10 raw points scaled by x1.25 is a ~12-13 point drop after rounding,
    # not exactly 10 -- assert the direction and approximate size, not an
    # exact delta that depends on float rounding.
    assert incomplete.score < complete.score
    assert complete.score - incomplete.score in (12, 13)


def test_evidence_quality_score_stays_within_0_100() -> None:
    worst = compute_evidence_quality(
        _automated_record(study_type=None, limitations=None, uncertainty_notes=None)
    )
    best = compute_evidence_quality(_manual_record(study_type="meta_analysis"))

    assert 0 <= worst.score <= 100
    assert 0 <= best.score <= 100
    assert best.score == 100


def test_evidence_consensus_insufficient_below_two_edges() -> None:
    zero_edges = compute_evidence_consensus([])
    one_edge = compute_evidence_consensus(["supports"])

    assert zero_edges.score is None
    assert zero_edges.reliability == "insufficient"
    assert one_edge.score is None
    assert one_edge.reliability == "insufficient"


def test_evidence_consensus_computes_ratio_from_supports_and_contradicts() -> None:
    consensus = compute_evidence_consensus(["supports", "supports", "contradicts"])

    assert consensus.relationship_edge_count == 3
    assert consensus.supports_count == 2
    assert consensus.contradicts_count == 1
    assert consensus.score == 67
    assert consensus.reliability == "moderate"


def test_evidence_consensus_reliability_tiers() -> None:
    assert compute_evidence_consensus(["supports", "supports"]).reliability == "low"
    assert compute_evidence_consensus(["supports"] * 4).reliability == "moderate"
    assert compute_evidence_consensus(["supports"] * 5).reliability == "high"


def test_evidence_consensus_excludes_supersedes_from_eligibility() -> None:
    consensus = compute_evidence_consensus(["supersedes", "supersedes"])

    assert consensus.relationship_edge_count == 0
    assert consensus.reliability == "insufficient"
    assert consensus.score is None


def test_evidence_consensus_qualifies_only_edges_still_insufficient_for_a_ratio() -> None:
    consensus = compute_evidence_consensus(["qualifies", "contextualizes"])

    assert consensus.relationship_edge_count == 2
    assert consensus.reliability == "low"
    assert consensus.score is None


def test_claim_confidence_not_computed_when_consensus_insufficient() -> None:
    quality = compute_evidence_quality(_manual_record())
    consensus = compute_evidence_consensus(["supports"])

    confidence = compute_claim_confidence([quality], consensus)

    assert confidence.score is None
    assert confidence.mean_evidence_quality is None
    assert confidence.reliability == "insufficient"


def test_claim_confidence_multiplies_rather_than_averages() -> None:
    high_quality = EvidenceQuality(
        evidence_record_id="ev-1",
        score=100,
        study_design_tier="meta_analysis",
        study_type_missing=False,
        manually_reviewed=True,
    )
    low_quality = EvidenceQuality(
        evidence_record_id="ev-2",
        score=20,
        study_design_tier="case_report",
        study_type_missing=False,
        manually_reviewed=False,
    )
    high_consensus = EvidenceConsensus(
        relationship_edge_count=10,
        supports_count=10,
        contradicts_count=0,
        score=100,
        reliability="high",
    )

    confidence = compute_claim_confidence([high_quality, low_quality], high_consensus)

    # Mean quality (60) x consensus (100) must not inherit either input's
    # higher value on its own -- this is the concrete case
    # ai_layer_architecture.md names as the reason the three numbers must
    # never collapse into one.
    assert confidence.mean_evidence_quality == 60
    assert confidence.score == 60


def test_evidence_coverage_percentage() -> None:
    coverage = compute_evidence_coverage(total_records=155, records_in_relationship=3)

    assert coverage.percentage == 2
    assert coverage.total_records == 155
    assert coverage.records_in_relationship == 3


def test_evidence_coverage_handles_zero_total_records() -> None:
    coverage = compute_evidence_coverage(total_records=0, records_in_relationship=0)

    assert coverage.percentage == 0


def test_render_synthesis_insufficient_consensus_omits_confidence_number() -> None:
    quality = compute_evidence_quality(_manual_record())
    consensus = compute_evidence_consensus(["supports"])
    confidence = compute_claim_confidence([quality], consensus)
    coverage = compute_evidence_coverage(total_records=155, records_in_relationship=3)

    lines = render_synthesis(
        consensus=consensus, quality=quality, confidence=confidence, coverage=coverage
    )
    joined = "\n".join(lines)

    assert "not yet assessable" in joined
    assert f"Evidence Quality: {quality.score}/100" in joined


def test_render_synthesis_full_consensus_shows_all_four_numbers() -> None:
    quality = compute_evidence_quality(_manual_record())
    consensus = compute_evidence_consensus(["supports", "supports", "supports"])
    confidence = compute_claim_confidence([quality, quality, quality], consensus)
    coverage = compute_evidence_coverage(total_records=155, records_in_relationship=3)

    lines = render_synthesis(
        consensus=consensus, quality=quality, confidence=confidence, coverage=coverage
    )
    joined = "\n".join(lines)

    assert f"Evidence Quality: {quality.score}/100" in joined
    assert f"Evidence Consensus: {consensus.score}/100" in joined
    assert f"Claim Confidence: {confidence.score}/100" in joined
    assert "Evidence coverage: 3 of 155" in joined
