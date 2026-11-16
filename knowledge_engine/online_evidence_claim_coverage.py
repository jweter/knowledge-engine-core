def claim_coverage_ratio(claim_statuses: list[str]) -> float:
    if not claim_statuses:
        return 0.0
    total = len(claim_statuses)
    insufficient = sum(1 for status in claim_statuses if status == "insufficient_evidence")
    covered = total - insufficient
    return round(covered / total, 4)
