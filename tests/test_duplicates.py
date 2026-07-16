from knowledge_engine.duplicates import DuplicateCandidate, decide_duplicate


def test_no_duplicate_signal_is_importable() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/example",
    )

    assert decision.item_status == "importable"
    assert decision.duplicate_outcome == "none"
    assert decision.matched_paper_id is None
    assert decision.matched_import_item_id is None
    assert decision.reason_code == "no_duplicate_signal"


def test_exact_hash_match_is_authoritative_safe_skip() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/new",
        exact_hash_match=DuplicateCandidate(
            paper_id=7,
            content_hash="a" * 64,
            normalized_doi="10.1000/existing",
        ),
        doi_match=DuplicateCandidate(paper_id=9, content_hash="b" * 64),
        title_year_match=DuplicateCandidate(paper_id=11),
    )

    assert decision.item_status == "skipped"
    assert decision.duplicate_outcome == "exact_hash_duplicate"
    assert decision.matched_paper_id == 7
    assert decision.reason_code == "matching_content_hash"


def test_same_run_exact_hash_match_preserves_import_item_identity() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi=None,
        exact_hash_match=DuplicateCandidate(
            import_item_id="item-previous",
            content_hash="a" * 64,
        ),
    )

    assert decision.item_status == "skipped"
    assert decision.matched_paper_id is None
    assert decision.matched_import_item_id == "item-previous"


def test_doi_match_with_equal_hash_is_safe_skip() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/example",
        doi_match=DuplicateCandidate(
            paper_id=7,
            content_hash="a" * 64,
            normalized_doi="10.1000/example",
        ),
    )

    assert decision.item_status == "skipped"
    assert decision.duplicate_outcome == "doi_duplicate"
    assert decision.matched_paper_id == 7
    assert decision.reason_code == "matching_doi_and_content_hash"


def test_doi_match_with_different_hash_requires_review() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/example",
        doi_match=DuplicateCandidate(
            paper_id=7,
            content_hash="b" * 64,
            normalized_doi="10.1000/example",
        ),
    )

    assert decision.item_status == "needs_review"
    assert decision.duplicate_outcome == "doi_hash_conflict"
    assert decision.reason_code == "matching_doi_conflicting_content_hash"


def test_doi_match_without_candidate_hash_requires_review() -> None:
    decision = decide_duplicate(
        candidate_content_hash=None,
        candidate_normalized_doi="10.1000/example",
        doi_match=DuplicateCandidate(
            paper_id=7,
            content_hash="b" * 64,
            normalized_doi="10.1000/example",
        ),
    )

    assert decision.item_status == "needs_review"
    assert decision.duplicate_outcome == "doi_hash_conflict"
    assert decision.reason_code == "matching_doi_without_reconcilable_content_hash"


def test_doi_match_without_matched_hash_requires_review() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/example",
        doi_match=DuplicateCandidate(
            paper_id=7,
            content_hash=None,
            normalized_doi="10.1000/example",
        ),
    )

    assert decision.item_status == "needs_review"
    assert decision.duplicate_outcome == "doi_hash_conflict"
    assert decision.reason_code == "matching_doi_without_reconcilable_content_hash"


def test_title_year_match_is_review_only() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi=None,
        title_year_match=DuplicateCandidate(
            paper_id=7,
            normalized_title="a study",
            publication_year=2024,
        ),
    )

    assert decision.item_status == "needs_review"
    assert decision.duplicate_outcome == "possible_title_year_duplicate"
    assert decision.matched_paper_id == 7
    assert decision.reason_code == "matching_normalized_title_and_publication_year"


def test_doi_signal_overrides_weaker_title_year_signal() -> None:
    decision = decide_duplicate(
        candidate_content_hash="a" * 64,
        candidate_normalized_doi="10.1000/example",
        doi_match=DuplicateCandidate(paper_id=7, content_hash="b" * 64),
        title_year_match=DuplicateCandidate(paper_id=9),
    )

    assert decision.item_status == "needs_review"
    assert decision.duplicate_outcome == "doi_hash_conflict"
    assert decision.matched_paper_id == 7
