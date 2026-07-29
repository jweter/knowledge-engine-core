"""Deterministic structured-section detection for parsed paper text.

This is the structured-section half of the extraction methodology decided in
docs/phase2_design.md: locate methods/results/limitations-style sections by
heading pattern, so a later milestone's rule-based claim extraction can be
scoped to the right section instead of searching the whole document. This
module does not extract claims, does not generate EvidenceRecord rows, and
does not persist anything -- it is a pure function over already-parsed page
text.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_engine.parser import ParsedPage

SECTION_DETECTION_RULES_VERSION = "m16-section-detection-v2"

SECTION_TYPES = (
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "references",
)

# Every pattern matches a heading word at the start of a line -- optionally
# preceded by a numbered-heading prefix like "3." or "3.1" -- never a
# sentence that merely contains the word. This mirrors parser.py's
# REFERENCE_HEADING_PATTERN, the established precedent for this style in
# this codebase. Combined headings (e.g. "Results and Discussion")
# deliberately do not match any pattern in this ruleset: missing a section
# is safe, mislabeling one is not.
#
# v2 (M38 follow-up): a heading is recognized either alone on its own line
# (the original v1 behavior) or immediately followed by a colon and further
# text on the *same* line -- e.g. "Results: SGLT2 inhibitor use was
# associated with...", a structured-abstract/discussion layout M38's
# corpus-scale measurement found real PMC papers actually use, which v1's
# full-line-only match silently missed entirely (the heading's own text
# then fell through into whichever earlier section was open, and any
# quantitative claims in it were invisible to M17's results/conclusion-only
# claim-candidate scan). The colon requirement keeps this narrow: "results"
# appearing mid-sentence, or as part of a combined heading like "Results and
# Discussion", still does not match either alternative.
_NUMBERING_PREFIX = r"(?:\d+(?:\.\d+)*\.?\s+)?"
_INLINE_LABEL_SUFFIX = r"\s*(?:$|:\s*(?=\S))"
_SECTION_HEADING_PATTERNS: dict[str, re.Pattern[str]] = {
    "abstract": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}abstract{_INLINE_LABEL_SUFFIX}"),
    "introduction": re.compile(
        rf"(?im)^\s*{_NUMBERING_PREFIX}(?:introduction|background){_INLINE_LABEL_SUFFIX}"
    ),
    "methods": re.compile(
        rf"(?im)^\s*{_NUMBERING_PREFIX}(?:methods|materials and methods|study design)"
        rf"{_INLINE_LABEL_SUFFIX}"
    ),
    "results": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}results{_INLINE_LABEL_SUFFIX}"),
    "discussion": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}discussion{_INLINE_LABEL_SUFFIX}"),
    "limitations": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}limitations{_INLINE_LABEL_SUFFIX}"),
    "conclusion": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}conclusions?{_INLINE_LABEL_SUFFIX}"),
    "references": re.compile(
        rf"(?im)^\s*{_NUMBERING_PREFIX}(?:references|bibliography|literature cited)"
        rf"{_INLINE_LABEL_SUFFIX}"
    ),
}


@dataclass(frozen=True)
class SectionSpan:
    """One detected section's exact page/offset boundary.

    A section may span multiple pages (a Methods section routinely does), so
    the start and end locations are recorded independently rather than as a
    single page_number. ``start_offset``/``end_offset`` are character offsets
    into ``start_page_number``'s/``end_page_number``'s own ``ParsedPage.text``
    respectively -- the same span identity introduced for evidence-record
    ``source_span`` citations.
    """

    section_type: str
    start_page_number: int
    start_offset: int
    end_page_number: int
    end_offset: int
    heading_text: str
    rules_version: str


def detect_sections(pages: Sequence[ParsedPage]) -> tuple[SectionSpan, ...]:
    """Detect structured sections across a paper's pages.

    Returns spans in document order. A section type with no matching heading
    is simply absent from the result; it is never guessed or defaulted. An
    empty ``pages`` sequence returns an empty result.
    """

    if not pages:
        return ()

    matches: list[tuple[int, int, str, str]] = []
    for page in pages:
        for section_type, pattern in _SECTION_HEADING_PATTERNS.items():
            for match in pattern.finditer(page.text):
                matches.append(
                    (page.page_number, match.start(), section_type, match.group(0).strip())
                )
    matches.sort(key=lambda item: (item[0], item[1]))

    if not matches:
        return ()

    last_page = pages[-1]
    spans: list[SectionSpan] = []
    for index, (page_number, offset, section_type, heading_text) in enumerate(matches):
        if index + 1 < len(matches):
            end_page_number, end_offset, _, _ = matches[index + 1]
        else:
            end_page_number, end_offset = last_page.page_number, len(last_page.text)
        spans.append(
            SectionSpan(
                section_type=section_type,
                start_page_number=page_number,
                start_offset=offset,
                end_page_number=end_page_number,
                end_offset=end_offset,
                heading_text=heading_text,
                rules_version=SECTION_DETECTION_RULES_VERSION,
            )
        )
    return tuple(spans)


def section_text(pages: Sequence[ParsedPage], section: SectionSpan) -> str:
    """Return one section's exact text, concatenated across the pages it spans.

    Shared by every extraction module that needs a section's raw text (M26's
    `study_design`, M28's `pico`) so this span-to-text conversion has exactly
    one implementation -- the same class of copy-paste divergence that let
    `ClassifiedPaperRepository` silently drop page persistence (see
    CHANGELOG.md) is not worth risking here too. Includes the heading itself
    at the start; use `section_content` for the heading-stripped body.
    """

    parts: list[str] = []
    for page in pages:
        if page.page_number < section.start_page_number:
            continue
        if page.page_number > section.end_page_number:
            continue
        start = section.start_offset if page.page_number == section.start_page_number else 0
        end = section.end_offset if page.page_number == section.end_page_number else len(page.text)
        parts.append(page.text[start:end])
    return "\n\n".join(parts)


def section_content(pages: Sequence[ParsedPage], section: SectionSpan) -> str:
    """Return one section's text with its own heading stripped from the start.

    `section.start_offset` can point at whitespace preceding the heading
    (`detect_sections`' heading regex greedily absorbs a preceding blank line
    into the match before `heading_text` is stripped), so a fixed
    `len(heading_text)` slice from the start is not reliable. Locates the
    heading text itself and slices from immediately after it instead. Falls
    back to the full (stripped) section text if the heading cannot be found,
    which should not normally happen.
    """

    text = section_text(pages, section)
    heading_index = text.find(section.heading_text)
    if heading_index == -1:
        return text.strip()
    return text[heading_index + len(section.heading_text) :].strip()
