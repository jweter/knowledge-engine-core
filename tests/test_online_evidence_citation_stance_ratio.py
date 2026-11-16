from knowledge_engine.online_evidence_citation_stance_ratio import citation_stance_support_ratio


def test_citation_stance_support_ratio_example_1() -> None:
    assert citation_stance_support_ratio([]) == 0.0


def test_citation_stance_support_ratio_example_2() -> None:
    assert citation_stance_support_ratio(["supports", "contradicts", "inconclusive"]) == 0.3333


def test_citation_stance_support_ratio_example_3() -> None:
    assert citation_stance_support_ratio(["supports", "supports"]) == 1.0


def test_citation_stance_support_ratio_example_4() -> None:
    assert citation_stance_support_ratio(["Supports"]) == 0.0


def test_citation_stance_support_ratio_example_5() -> None:
    assert citation_stance_support_ratio(["supports", "Supports", "supports"]) == 0.6667


def test_case_sensitive_unknown_and_repeated_entries() -> None:
    assert citation_stance_support_ratio(["SUPPORTS", "supports", "Supports", "unknown"]) == 0.25
