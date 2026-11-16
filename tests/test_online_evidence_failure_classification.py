from knowledge_engine.online_evidence_failure_classification import classify_retrieval_failure


def test_classify_retrieval_failure_example_1() -> None:
    assert classify_retrieval_failure("HTTP 500 from source.example.org") == "http_error"


def test_classify_retrieval_failure_example_2() -> None:
    assert classify_retrieval_failure("Response exceeds 100000 bytes") == "oversized"


def test_classify_retrieval_failure_example_3() -> None:
    assert classify_retrieval_failure("") == "unknown"


def test_classify_retrieval_failure_example_4() -> None:
    assert classify_retrieval_failure("Connection refused by host") == "network_error"


def test_classify_retrieval_failure_example_5() -> None:
    assert classify_retrieval_failure("HTTP 500 response exceeds 100000 bytes") == "http_error"
