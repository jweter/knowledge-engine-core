def citation_stance_support_ratio(stances: list[str]) -> float:
    """
    Calculate the fraction of entries in stances equal to the exact string 'supports'.

    Args:
        stances (list[str]): A list of stance strings.

    Returns:
        float: The fraction of 'supports' stances, rounded to four decimal places.
    """
    if not stances:
        return 0.0

    supports_count = sum(1 for stance in stances if stance == "supports")
    total_count = len(stances)

    return round(supports_count / total_count, 4)
