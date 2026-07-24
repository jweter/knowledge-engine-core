"""Deterministic study-type classification and limitations extraction.

Both are paper-intrinsic facts a paper states about itself -- usually in
predictable places (an explicit study-design phrase in the Abstract or
Methods, an explicit "Limitations" heading) -- not judgment relative to a
research question. Per docs/roadmap/long_term_vision.md's Minimizing
Human-Typed Fields section, these should become deterministic extraction
targets rather than permanent human-typed review fields, extending
M16's structured-section detection the same conservative way M17/M18
extend it for claims: a missing signal produces `None`, never a guess.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from knowledge_engine.extraction.sections import SectionSpan, section_content, section_text
from knowledge_engine.parser import ParsedPage

STUDY_DESIGN_RULES_VERSION = "m26-study-design-v1"

_STUDY_TYPE_SECTION_TYPES = ("abstract", "methods")

# Checked most-specific first: meta-analyses and systematic reviews often
# summarize randomized trials in their own text, so those two must win over
# the RCT pattern below when both could match the same abstract.
_STUDY_TYPE_PATTERNS: dict[str, re.Pattern[str]] = {
    "meta_analysis": re.compile(r"(?i)\bmeta-analysis\b"),
    "systematic_review": re.compile(r"(?i)\bsystematic review\b"),
    "randomized_controlled_trial": re.compile(
        r"(?i)\brandomi[sz]ed(?:,|\s)+(?:double-blind(?:,|\s)+)?"
        r"(?:placebo-controlled(?:,|\s)+)?(?:clinical\s+)?(?:controlled\s+)?trial\b"
    ),
    "cohort_study": re.compile(r"(?i)\b(?:prospective|retrospective)?\s*cohort study\b"),
    "case_control_study": re.compile(r"(?i)\bcase-control study\b"),
    "cross_sectional_study": re.compile(r"(?i)\bcross-sectional study\b"),
    "pilot_study": re.compile(r"(?i)\bpilot study\b"),
    "observational_study": re.compile(r"(?i)\bobservational study\b"),
}


def classify_study_type(pages: Sequence[ParsedPage], sections: Sequence[SectionSpan]) -> str | None:
    """Classify a paper's study design from explicit cues in its own text.

    Only searches the Abstract and Methods sections -- a study-design phrase
    appearing only in the Introduction or Discussion is more likely to
    describe *prior* work the paper references, not the paper's own design.
    Neither section present, or no cue found, returns `None`.
    """

    combined = "\n\n".join(
        section_text(pages, section)
        for section in sections
        if section.section_type in _STUDY_TYPE_SECTION_TYPES
    )
    if not combined:
        return None
    for study_type, pattern in _STUDY_TYPE_PATTERNS.items():
        if pattern.search(combined):
            return study_type
    return None


def extract_limitations(
    pages: Sequence[ParsedPage], sections: Sequence[SectionSpan]
) -> list[str] | None:
    """Extract a paper's own stated limitations from an explicit heading.

    Returns the limitations section's text (heading excluded) as a
    single-item list, or `None` when no "limitations" section was detected
    or its content is empty after the heading.
    """

    section = next((s for s in sections if s.section_type == "limitations"), None)
    if section is None:
        return None
    content = section_content(pages, section)
    if not content:
        return None
    return [content]
