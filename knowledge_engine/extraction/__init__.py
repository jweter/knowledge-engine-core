"""Deterministic evidence-extraction services."""

from knowledge_engine.extraction.claims import (
    CLAIM_CANDIDATE_RULES_VERSION,
    ClaimCandidate,
    detect_claim_candidates,
)
from knowledge_engine.extraction.confidence_interval import (
    CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION,
    extract_confidence_interval,
)
from knowledge_engine.extraction.direction import (
    CLAIM_FRAMING_RULES_VERSION,
    ClaimFraming,
    classify_claim_framing,
)
from knowledge_engine.extraction.dose import (
    DOSE_EXTRACTION_RULES_VERSION,
    extract_dose,
)
from knowledge_engine.extraction.duration import (
    DURATION_EXTRACTION_RULES_VERSION,
    extract_duration,
)
from knowledge_engine.extraction.evidence_classification import (
    EVIDENCE_CLASSIFICATION_RULES_VERSION,
    build_automated_evidence_record,
    classify_evidence_direction,
    generate_research_question,
)
from knowledge_engine.extraction.evidence_items import (
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    DraftEvidenceItem,
    PaperMetadata,
    build_draft_evidence_item,
    build_draft_evidence_items,
)
from knowledge_engine.extraction.grounding import (
    GROUNDING_RULES_VERSION,
    GroundingResult,
    verify_grounding,
)
from knowledge_engine.extraction.llm_grounded_pico import (
    LLM_GROUNDED_PICO_RULES_VERSION,
    LLM_GROUNDED_PICO_RULES_VERSIONS,
    GroundedField,
    LlmGroundedPico,
    extract_pico_for_candidate,
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
    section_page_ranges,
    section_text,
)
from knowledge_engine.extraction.study_design import (
    STUDY_DESIGN_RULES_VERSION,
    classify_study_type,
    extract_limitations,
)
from knowledge_engine.extraction.table_filter import (
    TABLE_FILTER_RULES_VERSION,
    is_table_derived,
)

__all__ = [
    "CLAIM_CANDIDATE_RULES_VERSION",
    "CLAIM_FRAMING_RULES_VERSION",
    "CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION",
    "DOSE_EXTRACTION_RULES_VERSION",
    "DRAFT_EVIDENCE_ITEM_RULES_VERSION",
    "DURATION_EXTRACTION_RULES_VERSION",
    "EVIDENCE_CLASSIFICATION_RULES_VERSION",
    "GROUNDING_RULES_VERSION",
    "LLM_GROUNDED_PICO_RULES_VERSION",
    "LLM_GROUNDED_PICO_RULES_VERSIONS",
    "PICO_EXTRACTION_RULES_VERSION",
    "SECTION_DETECTION_RULES_VERSION",
    "SECTION_TYPES",
    "STUDY_DESIGN_RULES_VERSION",
    "TABLE_FILTER_RULES_VERSION",
    "ClaimCandidate",
    "ClaimFraming",
    "DraftEvidenceItem",
    "GroundedField",
    "GroundingResult",
    "LlmGroundedPico",
    "PaperMetadata",
    "PicoFields",
    "SectionSpan",
    "build_automated_evidence_record",
    "build_draft_evidence_item",
    "build_draft_evidence_items",
    "classify_claim_framing",
    "classify_evidence_direction",
    "classify_study_type",
    "detect_claim_candidates",
    "detect_sections",
    "extract_confidence_interval",
    "extract_dose",
    "extract_duration",
    "extract_limitations",
    "extract_pico",
    "extract_pico_for_candidate",
    "generate_research_question",
    "is_table_derived",
    "section_content",
    "section_page_ranges",
    "section_text",
    "verify_grounding",
]
