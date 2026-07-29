import pytest

from knowledge_engine.search_fusion import DEFAULT_RRF_K, FusedResult, fuse_rankings


def test_paper_in_both_rankings_outranks_a_single_ranking_match() -> None:
    results = fuse_rankings(lexical_paper_ids=[1, 2], semantic_paper_ids=[2, 3])

    by_id = {result.paper_id: result for result in results}
    assert by_id[2].fused_score > by_id[1].fused_score
    assert by_id[2].fused_score > by_id[3].fused_score


def test_records_rank_in_each_input_ranking() -> None:
    results = fuse_rankings(lexical_paper_ids=[10, 20], semantic_paper_ids=[20, 30])

    by_id = {result.paper_id: result for result in results}
    assert by_id[10].lexical_rank == 1
    assert by_id[10].semantic_rank is None
    assert by_id[20].lexical_rank == 2
    assert by_id[20].semantic_rank == 1
    assert by_id[30].lexical_rank is None
    assert by_id[30].semantic_rank == 2


def test_a_top_lexical_rank_alone_can_still_outscore_a_low_semantic_rank_alone() -> None:
    results = fuse_rankings(lexical_paper_ids=[1], semantic_paper_ids=[99, 98, 97, 2])

    by_id = {result.paper_id: result for result in results}
    assert by_id[1].fused_score > by_id[2].fused_score


def test_results_are_sorted_by_fused_score_descending() -> None:
    results = fuse_rankings(lexical_paper_ids=[3, 1, 2], semantic_paper_ids=[1, 2, 3])

    scores = [result.fused_score for result in results]
    assert scores == sorted(scores, reverse=True)


def test_single_entry_ranking_has_the_expected_rrf_score() -> None:
    results = fuse_rankings(lexical_paper_ids=[5], semantic_paper_ids=[])

    assert results == (
        FusedResult(
            paper_id=5,
            fused_score=1.0 / (DEFAULT_RRF_K + 1),
            lexical_rank=1,
            semantic_rank=None,
        ),
    )


def test_ties_are_broken_by_ascending_paper_id() -> None:
    results = fuse_rankings(lexical_paper_ids=[20, 10], semantic_paper_ids=[10, 20])

    assert [result.paper_id for result in results] == [10, 20]


def test_empty_rankings_produce_no_results() -> None:
    assert fuse_rankings(lexical_paper_ids=[], semantic_paper_ids=[]) == ()


def test_lexical_only_ranking_is_still_scored() -> None:
    results = fuse_rankings(lexical_paper_ids=[7, 8], semantic_paper_ids=[])

    assert [result.paper_id for result in results] == [7, 8]
    assert all(result.semantic_rank is None for result in results)


def test_custom_k_changes_the_fused_score() -> None:
    default_results = fuse_rankings(lexical_paper_ids=[1], semantic_paper_ids=[])
    custom_results = fuse_rankings(lexical_paper_ids=[1], semantic_paper_ids=[], k=1)

    assert custom_results[0].fused_score != default_results[0].fused_score
    assert custom_results[0].fused_score == pytest.approx(1.0 / (1 + 1))


def test_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        fuse_rankings(lexical_paper_ids=[1], semantic_paper_ids=[], k=0)
