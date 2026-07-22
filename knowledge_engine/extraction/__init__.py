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
from knowledge_engine.extraction.sections import (
    SECTION_DETECTION_RULES_VERSION,
    SECTION_TYPES,
    SectionSpan,
    detect_sections,
)

__all__ = [
    "CLAIM_CANDIDATE_RULES_VERSION",
    "CLAIM_FRAMING_RULES_VERSION",
    "DRAFT_EVIDENCE_ITEM_RULES_VERSION",
    "SECTION_DETECTION_RULES_VERSION",
    "SECTION_TYPES",
    "ClaimCandidate",
    "ClaimFraming",
    "DraftEvidenceItem",
    "PaperMetadata",
    "SectionSpan",
    "build_draft_evidence_item",
    "build_draft_evidence_items",
    "classify_claim_framing",
    "detect_claim_candidates",
    "detect_sections",
]
