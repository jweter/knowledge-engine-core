"""Validate if an evidence record dictionary contains all required fields and if their values are of the correct type."""

from typing import Dict, Any


def validate_evidence_record(record: Dict[str, Any]) -> bool:
    """Validate if an evidence record dictionary contains all required fields and if their values are of the correct type."""
    required_fields = {"title": str, "author": str, "year": int, "source": str}

    if not isinstance(record, dict):
        return False

    for field, expected_type in required_fields.items():
        if field not in record or not isinstance(record[field], expected_type):
            return False

    return True
