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

SECTION_DETECTION_RULES_VERSION = "m16-section-detection-v1"

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

# Every pattern matches a full trimmed line -- optionally preceded by a
# numbered-heading prefix like "3." or "3.1" -- never a sentence that merely
# contains the word. This mirrors parser.py's REFERENCE_HEADING_PATTERN, the
# established precedent for this style in this codebase. Combined headings
# (e.g. "Results and Discussion") deliberately do not match any pattern in
# this v1 ruleset: missing a section is safe, mislabeling one is not.
_NUMBERING_PREFIX = r"(?:\d+(?:\.\d+)*\.?\s+)?"
_SECTION_HEADING_PATTERNS: dict[str, re.Pattern[str]] = {
    "abstract": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}abstract\s*$"),
    "introduction": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}(?:introduction|background)\s*$"),
    "methods": re.compile(
        rf"(?im)^\s*{_NUMBERING_PREFIX}(?:methods|materials and methods|study design)\s*$"
    ),
    "results": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}results\s*$"),
    "discussion": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}discussion\s*$"),
    "limitations": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}limitations\s*$"),
    "conclusion": re.compile(rf"(?im)^\s*{_NUMBERING_PREFIX}conclusions?\s*$"),
    "references": re.compile(
        rf"(?im)^\s*{_NUMBERING_PREFIX}(?:references|bibliography|literature cited)\s*$"
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
