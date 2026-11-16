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


def test_http_status_matches_prefixed_punctuated_and_tab_separated_messages() -> None:
    assert classify_retrieval_failure("HTTP 503.") == "http_error"
    assert (
        classify_retrieval_failure("Request failed: HTTP 503 from provider.")
        == "http_error"
    )
    assert classify_retrieval_failure("HTTP\t503 from provider") == "http_error"


def test_http_status_requires_exact_three_digits() -> None:
    assert classify_retrieval_failure("HTTP 50 from provider.") == "unknown"
    assert classify_retrieval_failure("HTTP 5000 from provider.") == "unknown"


def test_http_error_precedes_other_failure_classes() -> None:
    assert (
        classify_retrieval_failure("connection refused; HTTP 503; exceeds 10 bytes")
        == "http_error"
    )
