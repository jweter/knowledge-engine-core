from knowledge_engine.hybrid_search import (
    HybridSearchResult,
    merge_lexical_and_vector_results,
)
from knowledge_engine.search import SearchResult


def _lexical(paper_id: int, score: float) -> SearchResult:
    """A lexical result with an FTS5 bm25 score (lower, i.e. more negative, matches better)."""
    return SearchResult(
        paper_id=paper_id,
        title=f"Paper {paper_id}",
        abstract=None,
        publication_year=None,
        doi=None,
        score=score,
        snippet="",
        matched_query="query",
    )


def test_lexical_only_paper_keeps_its_normalized_lexical_score_as_combined() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(1, -2.0), _lexical(2, -4.0)],
        vector_scores={},
    )
    by_id = {result.paper_id: result for result in results}
    assert by_id[1].vector_score == 0.0
    assert by_id[1].lexical_score == by_id[1].combined_score
    assert by_id[2].lexical_score == 1.0  # the more negative (better) bm25 normalizes to 1.0
    assert by_id[1].lexical_score == 0.0  # the weaker bm25 normalizes to 0.0


def test_vector_only_paper_keeps_its_normalized_vector_score_as_combined() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[],
        vector_scores={10: 0.3, 20: 0.9},
    )
    by_id = {result.paper_id: result for result in results}
    assert by_id[10].lexical_score == 0.0
    assert by_id[10].vector_score == by_id[10].combined_score
    assert by_id[20].vector_score == 1.0
    assert by_id[10].vector_score == 0.0


def test_paper_present_in_both_signals_sums_both_normalized_scores() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(5, -1.0), _lexical(6, -3.0)],
        vector_scores={5: 0.1, 6: 0.5},
    )
    by_id = {result.paper_id: result for result in results}
    assert by_id[5].lexical_score == 0.0
    assert by_id[5].vector_score == 0.0
    assert by_id[5].combined_score == 0.0
    assert by_id[6].lexical_score == 1.0
    assert by_id[6].vector_score == 1.0
    assert by_id[6].combined_score == 2.0


def test_dual_signal_paper_outranks_single_signal_paper_when_its_score_is_higher() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(1, -5.0), _lexical(2, -5.0)],
        vector_scores={2: 5.0, 3: 5.0},
    )
    by_id = {result.paper_id: result for result in results}
    # Paper 2 matches both signals (each normalizes to 1.0 -> combined 2.0);
    # papers 1 and 3 match only one signal each (combined 1.0).
    assert by_id[2].combined_score > by_id[1].combined_score
    assert by_id[2].combined_score > by_id[3].combined_score
    assert results[0].paper_id == 2


def test_no_input_paper_id_is_ever_dropped() -> None:
    lexical_ids = {1, 2, 3}
    vector_ids = {3, 4, 5}
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(pid, -float(pid)) for pid in lexical_ids],
        vector_scores={pid: float(pid) for pid in vector_ids},
    )
    assert {result.paper_id for result in results} == lexical_ids | vector_ids
    assert len(results) == len(lexical_ids | vector_ids)


def test_output_is_deterministic_across_repeated_calls_with_identical_inputs() -> None:
    lexical = [_lexical(1, -2.0), _lexical(2, -4.0), _lexical(3, -1.0)]
    vector_scores = {2: 0.2, 3: 0.9, 4: 0.5}

    first = merge_lexical_and_vector_results(lexical=lexical, vector_scores=vector_scores)
    second = merge_lexical_and_vector_results(lexical=lexical, vector_scores=vector_scores)

    assert first == second


def test_results_are_sorted_by_combined_score_descending() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(1, -1.0), _lexical(2, -2.0), _lexical(3, -3.0)],
        vector_scores={},
    )
    scores = [result.combined_score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_ties_are_broken_by_ascending_paper_id() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(20, -1.0), _lexical(10, -1.0)],
        vector_scores={},
    )
    assert [result.paper_id for result in results] == [10, 20]


def test_constant_signal_normalizes_every_entry_to_one_rather_than_dividing_by_zero() -> None:
    results = merge_lexical_and_vector_results(
        lexical=[_lexical(1, -7.0), _lexical(2, -7.0)],
        vector_scores={},
    )
    assert all(result.lexical_score == 1.0 for result in results)
    assert all(result.combined_score == 1.0 for result in results)


def test_empty_inputs_produce_no_results() -> None:
    assert merge_lexical_and_vector_results(lexical=[], vector_scores={}) == []


def test_hybrid_search_result_fields_match_the_pinned_contract() -> None:
    result = HybridSearchResult(paper_id=1, combined_score=1.5, lexical_score=0.5, vector_score=1.0)
    assert result.paper_id == 1
    assert result.combined_score == 1.5
    assert result.lexical_score == 0.5
    assert result.vector_score == 1.0


def test_the_strongest_bm25_match_gets_the_top_lexical_score() -> None:
    """PR #555 review: bm25 is lower-is-better; normalizing it raw ranked weak matches higher."""
    strong, weak = (
        _lexical(1, -9.5),
        _lexical(2, -1.2),
    )  # SearchService returns these ascending: strong first
    results = merge_lexical_and_vector_results(lexical=[strong, weak], vector_scores={})
    by_id = {result.paper_id: result for result in results}
    assert by_id[1].lexical_score == 1.0 and by_id[2].lexical_score == 0.0
    assert [result.paper_id for result in results] == [1, 2]
