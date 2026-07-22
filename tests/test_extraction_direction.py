from knowledge_engine.extraction import (
    CLAIM_FRAMING_RULES_VERSION,
    ClaimCandidate,
    classify_claim_framing,
)


def _candidate(sentence_text: str) -> ClaimCandidate:
    return ClaimCandidate(
        sentence_text=sentence_text,
        section_type="results",
        page_number=1,
        start_offset=0,
        end_offset=len(sentence_text),
        matched_signal="percentage",
        rules_version="test",
    )


def test_contextualizes_cue_is_detected() -> None:
    text = "This finding is consistent with prior trials showing weight loss with GLP-1 agonists."
    classifications = classify_claim_framing([_candidate(text)])

    assert len(classifications) == 1
    assert classifications[0].framing == "contextualizes"
    assert classifications[0].matched_cue == "consistent with"
    assert classifications[0].rules_version == CLAIM_FRAMING_RULES_VERSION


def test_contradicts_cue_is_detected() -> None:
    text = "This result is in contrast to earlier reports of minimal effect."
    classifications = classify_claim_framing([_candidate(text)])

    assert len(classifications) == 1
    assert classifications[0].framing == "contradicts"
    assert classifications[0].matched_cue == "in contrast to"


def test_qualifies_cue_is_detected() -> None:
    text = "The improvement showed a trend toward significance among the treatment group."
    classifications = classify_claim_framing([_candidate(text)])

    assert len(classifications) == 1
    assert classifications[0].framing == "qualifies"
    assert classifications[0].matched_cue == "trend toward"


def test_did_not_reach_significance_is_qualifies() -> None:
    text = "The difference did not reach statistical significance."
    classifications = classify_claim_framing([_candidate(text)])

    assert classifications[0].framing == "qualifies"
    assert classifications[0].matched_cue == "did not reach significance"


def test_negated_consistency_classifies_as_contradicts_not_contextualizes() -> None:
    text = "This finding is not consistent with prior smaller trials."
    classifications = classify_claim_framing([_candidate(text)])

    assert classifications[0].framing == "contradicts"
    assert classifications[0].matched_cue == "not consistent with"


def test_strong_claim_without_framing_cue_is_unclassified() -> None:
    text = "Semaglutide produced significantly greater weight loss than placebo, p < 0.001."
    classifications = classify_claim_framing([_candidate(text)])

    assert len(classifications) == 1
    assert classifications[0].framing == "unclassified"
    assert classifications[0].matched_cue is None


def test_plain_percentage_claim_is_unclassified() -> None:
    text = "Body weight decreased by 12.4% from baseline."
    classifications = classify_claim_framing([_candidate(text)])

    assert classifications[0].framing == "unclassified"
    assert classifications[0].matched_cue is None


def test_multiple_candidates_classified_independently_in_order() -> None:
    candidates = [
        _candidate("Body weight decreased by 12.4% from baseline."),
        _candidate("This is consistent with prior trials."),
        _candidate("The result did not reach statistical significance."),
    ]

    classifications = classify_claim_framing(candidates)

    assert [c.framing for c in classifications] == [
        "unclassified",
        "contextualizes",
        "qualifies",
    ]
    assert [c.candidate.sentence_text for c in classifications] == [
        candidate.sentence_text for candidate in candidates
    ]


def test_no_candidates_produces_no_classifications() -> None:
    assert classify_claim_framing([]) == ()


def test_classification_preserves_source_candidate() -> None:
    candidate = _candidate("The trend did not reach statistical significance.")

    classifications = classify_claim_framing([candidate])

    assert classifications[0].candidate is candidate


def test_bare_discourse_connective_is_not_qualifies() -> None:
    """A candidate is only ever one isolated sentence (per M17): 'however' may
    contrast with something outside the candidate, or not qualify the result
    at all, so it must not be treated as a local qualifying cue."""

    text = "However, 87% of participants completed follow-up."
    classifications = classify_claim_framing([_candidate(text)])

    assert classifications[0].framing == "unclassified"
    assert classifications[0].matched_cue is None


def test_bare_although_is_not_qualifies() -> None:
    text = "Although the study enrolled 87% of the target population, results were promising."
    classifications = classify_claim_framing([_candidate(text)])

    assert classifications[0].framing == "unclassified"
    assert classifications[0].matched_cue is None
