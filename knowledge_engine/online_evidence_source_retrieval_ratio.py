def source_retrieval_success_ratio(source_statuses: list[str]) -> float:
    """
    Calculate the fraction of entries in source_statuses equal to the exact string 'retrieved'.

    Args:
        source_statuses (list[str]): A list of source statuses.

    Returns:
        float: The fraction of 'retrieved' statuses, rounded to four decimal places.
    """
    if not source_statuses:
        return 0.0

    retrieved_count = source_statuses.count("retrieved")
    total_count = len(source_statuses)

    return round(retrieved_count / total_count, 4)
