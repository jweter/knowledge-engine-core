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
from knowledge_engine.sentence_split import split_sentence_spans

STUDY_DESIGN_RULES_VERSION = "m26-study-design-v3"

_STUDY_TYPE_SECTION_TYPES = ("abstract", "methods")

# Checked most-specific first, and in a deliberate order since the first
# pattern to match wins:
#   - meta-analyses and systematic reviews often summarize randomized trials
#     in their own text, so those two must win over the RCT pattern below
#     when both could match the same abstract.
#   - narrative_review is checked before randomized_controlled_trial for the
#     same reason: a narrative review discussing "randomized controlled
#     trials" in prior literature is not itself one.
#   - cross_over_trial is checked before randomized_controlled_trial because
#     a crossover trial's own abstract routinely also says "randomized" (e.g.
#     "a randomized, double-blind, crossover trial") -- the more specific
#     crossover-trial phrase should win.
#   - retrospective_study is checked after cohort_study so a "retrospective
#     cohort study" -- already matched by cohort_study's own optional
#     "retrospective|prospective" prefix -- is not double-counted as the
#     more generic retrospective_study.
#   - case_series and case_report are checked after case_control_study so
#     "case-control study" is never miscounted as either.
# v2 (M38 follow-up): M38's corpus-scale measurement found 59.4% of the real
# corpus classified as "none" under v1's 8-pattern closed vocabulary --
# largely narrative reviews, crossover trials, case series/reports, and
# retrospective analyses not phrased as "cohort study", none of which v1
# recognized at all. This adds those five design types; it does not change
# any v1 pattern's matching behavior.
#
# v3 (Phase 2 coverage follow-up): re-measured "none" papers that do have an
# Abstract or Methods section (still 56.7% of the corpus) and read a real
# sample. Four concrete, real phrasing gaps, each widened narrowly:
#   - randomized_controlled_trial's fixed-order optional-group pattern
#     ("randomized, double-blind, placebo-controlled ... trial") missed real
#     phrasings that interleave other descriptor words in a different order,
#     e.g. "an open-label randomized and decentralized clinical trial"
#     (paper 918). Replaced with a bounded "randomized ... trial" window (up
#     to 6 intervening words) that tolerates arbitrary descriptor ordering
#     while still requiring both words to co-occur in roughly one clause --
#     not a blanket "randomized...trial anywhere in the abstract" match.
#     Still requires singular "trial" (word-boundary after "trial" does not
#     match "trials"), preserving the same protection this module's
#     docstring already documents: a paper discussing "several randomized
#     controlled trials" from prior literature, plural, still does not match.
#   - cohort_study missed "cohort analysis" (paper 465: "a single-center
#     cohort analysis of prospectively collected data").
#   - cross_sectional_study missed "cross-sectional survey"/"cross-sectional
#     design" (paper 591: "a cross-sectional online survey was conducted").
#   - case_report missed the canonical case-report opening phrase itself
#     ("we report/describe/present a case", papers 67/629), not just the
#     literal words "case report".
# None of these loosen an earlier-checked pattern in the dict, and ordering
# is unchanged, so the same precedence guarantees (narrative_review before
# randomized_controlled_trial, cohort_study before case_report, etc.) still
# hold.
_STUDY_TYPE_PATTERNS: dict[str, re.Pattern[str]] = {
    "meta_analysis": re.compile(r"(?i)\bmeta-analysis\b"),
    "systematic_review": re.compile(r"(?i)\bsystematic review\b"),
    "narrative_review": re.compile(r"(?i)\bnarrative review\b"),
    "cross_over_trial": re.compile(r"(?i)\bcross-?over trial\b"),
    "randomized_controlled_trial": re.compile(
        r"(?i)\brandomi[sz]ed\b(?:[,\s]+[\w-]+){0,6}[,\s]+trial\b"
    ),
    "cohort_study": re.compile(
        r"(?i)\b(?:prospective|retrospective)?\s*cohort (?:study|analysis)\b"
    ),
    "retrospective_study": re.compile(r"(?i)\bretrospective (?:study|analysis|review)\b"),
    "case_control_study": re.compile(r"(?i)\bcase-control study\b"),
    "case_series": re.compile(r"(?i)\bcase series\b"),
    "case_report": re.compile(r"(?i)\bcase reports?\b|\bwe (?:report|describe|present) a case\b"),
    "cross_sectional_study": re.compile(
        r"(?i)\bcross-sectional\b(?:\s+\w+){0,2}?\s+(?:study|survey|design)\b"
    ),
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


_LIMITATIONS_FALLBACK_SECTION_TYPES = ("discussion",)
_LIMITATIONS_CUE_PATTERN = re.compile(r"(?i)\blimitations?\b")


def extract_limitations(
    pages: Sequence[ParsedPage], sections: Sequence[SectionSpan]
) -> list[str] | None:
    """Extract a paper's own stated limitations.

    Prefers an explicit "Limitations" heading when one was detected: returns
    that section's text (heading excluded) as a single-item list, unchanged
    from the original behavior. When no such heading exists, falls back to
    scanning the Discussion section for sentences that explicitly name a
    limitation ("Several limitations of this study...", "Another limitation
    is..."), the same sentence-level cue-matching M28's PICO extraction and
    M17's claim-candidate detection already use for signals that don't
    reliably appear under their own heading. A real 200-paper sample of
    papers with no "Limitations" heading but a Discussion section found 161
    (80.5%) had at least one such cue sentence in Discussion -- the heading
    requirement, not an absence of stated limitations, was the coverage
    bottleneck.

    Returns every cue-matching sentence found, in document order, since a
    paper often states several limitations across separate sentences and
    this module never judges which one is "the real" limitation versus a
    meta-announcement sentence ("This study has several limitations.") --
    both are returned as-is, matching every other extraction rule's
    discipline of returning matched text verbatim rather than a summary or
    a filtered subset. A sentence that uses "limitation" to explicitly deny
    something is one (e.g. "should not be viewed as a limitation") is still
    returned; this is an accepted, honest false-positive class of a
    word-cue match, the same tradeoff `detect_claim_candidates` already
    documents for its own signal patterns, not something this module tries
    to resolve with sentence-level negation detection.

    Returns `None` when neither an explicit heading nor any Discussion
    cue sentence is found -- absence is never guessed into a low-confidence
    value.
    """

    section = next((s for s in sections if s.section_type == "limitations"), None)
    if section is not None:
        content = section_content(pages, section)
        return [content] if content else None

    matches: list[str] = []
    for fallback_section in sections:
        if fallback_section.section_type not in _LIMITATIONS_FALLBACK_SECTION_TYPES:
            continue
        text = section_content(pages, fallback_section)
        for start, end in split_sentence_spans(text):
            sentence = text[start:end].strip()
            if _LIMITATIONS_CUE_PATTERN.search(sentence):
                matches.append(sentence)
    return matches or None
