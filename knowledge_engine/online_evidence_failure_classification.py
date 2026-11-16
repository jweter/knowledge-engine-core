import re


def classify_retrieval_failure(failure_reason: str) -> str:
    """
    Classify the retrieval failure based on the failure reason.

    :param failure_reason: The reason for the retrieval failure.
    :return: The classification of the failure.
    """
    failure_reason = failure_reason.strip().lower()

    if re.search(r"http\s+[0-9]{3}(?![0-9])", failure_reason):
        return "http_error"
    elif "exceeds" in failure_reason and "bytes" in failure_reason:
        return "oversized"
    elif (
        "timed out" in failure_reason
        or "connection" in failure_reason
        or "refused" in failure_reason
    ):
        return "network_error"
    else:
        return "unknown"
