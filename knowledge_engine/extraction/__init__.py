"""Deterministic evidence-extraction services."""

from knowledge_engine.extraction.claims import (
    CLAIM_CANDIDATE_RULES_VERSION,
    ClaimCandidate,
    detect_claim_candidates,
)
from knowledge_engine.extraction.direction import (
    CLAIM_FRAMING_RULES_VERSION,
    ClaimFraming,
    classify_claim_framing,
)
from knowledge_engine.extraction.evidence_items import (
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    DraftEvidenceItem,
    PaperMetadata,
    build_draft_evidence_item,
    build_draft_evidence_items,
)
from knowledge_engine.extraction.pico import (
    PICO_EXTRACTION_RULES_VERSION,
    PicoFields,
    extract_pico,
)
from knowledge_engine.extraction.sections import (
    SECTION_DETECTION_RULES_VERSION,
    SECTION_TYPES,
    SectionSpan,
    detect_sections,
    section_content,
    section_text,
)
from knowledge_engine.extraction.study_design import (
    STUDY_DESIGN_RULES_VERSION,
    classify_study_type,
    extract_limitations,
)

__all__ = [
    "CLAIM_CANDIDATE_RULES_VERSION",
    "CLAIM_FRAMING_RULES_VERSION",
    "DRAFT_EVIDENCE_ITEM_RULES_VERSION",
    "PICO_EXTRACTION_RULES_VERSION",
    "SECTION_DETECTION_RULES_VERSION",
    "SECTION_TYPES",
    "STUDY_DESIGN_RULES_VERSION",
    "ClaimCandidate",
    "ClaimFraming",
    "DraftEvidenceItem",
    "PaperMetadata",
    "PicoFields",
    "SectionSpan",
    "build_draft_evidence_item",
    "build_draft_evidence_items",
    "classify_claim_framing",
    "classify_study_type",
    "detect_claim_candidates",
    "detect_sections",
    "extract_limitations",
    "extract_pico",
    "section_content",
    "section_text",
]
