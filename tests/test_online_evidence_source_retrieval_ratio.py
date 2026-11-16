from knowledge_engine.online_evidence_source_retrieval_ratio import source_retrieval_success_ratio


def test_source_retrieval_success_ratio_example_1() -> None:
    assert source_retrieval_success_ratio([]) == 0.0


def test_source_retrieval_success_ratio_example_2() -> None:
    assert source_retrieval_success_ratio(["retrieved", "failed", "unavailable"]) == 0.3333


def test_source_retrieval_success_ratio_example_3() -> None:
    assert source_retrieval_success_ratio(["retrieved", "retrieved"]) == 1.0


def test_source_retrieval_success_ratio_example_4() -> None:
    assert source_retrieval_success_ratio(["Retrieved"]) == 0.0


def test_source_retrieval_success_ratio_example_5() -> None:
    assert (
        source_retrieval_success_ratio(["retrieved", "retrieved", "retrieved", "retrieved"]) == 1.0
    )
