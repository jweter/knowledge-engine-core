"""Deterministic evidence-extraction services."""

from knowledge_engine.extraction.sections import (
    SECTION_DETECTION_RULES_VERSION,
    SECTION_TYPES,
    SectionSpan,
    detect_sections,
)

__all__ = [
    "SECTION_DETECTION_RULES_VERSION",
    "SECTION_TYPES",
    "SectionSpan",
    "detect_sections",
]
