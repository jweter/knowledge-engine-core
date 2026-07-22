"""Deterministic evidence-extraction services."""

from knowledge_engine.extraction.claims import (
    CLAIM_CANDIDATE_RULES_VERSION,
    ClaimCandidate,
    detect_claim_candidates,
)
from knowledge_engine.extraction.sections import (
    SECTION_DETECTION_RULES_VERSION,
    SECTION_TYPES,
    SectionSpan,
    detect_sections,
)

__all__ = [
    "CLAIM_CANDIDATE_RULES_VERSION",
    "SECTION_DETECTION_RULES_VERSION",
    "SECTION_TYPES",
    "ClaimCandidate",
    "SectionSpan",
    "detect_claim_candidates",
    "detect_sections",
]
