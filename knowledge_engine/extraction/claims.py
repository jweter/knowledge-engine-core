"""Deterministic claim-candidate sentence detection.

Locates candidate claim sentences -- sentences reporting a quantitative or
comparative finding -- within a paper's results/conclusion sections, using
the SectionSpan boundaries M16's detect_sections produces. This module does
not extract PICO fields, does not classify evidence direction, and does not
generate EvidenceRecord rows -- those need corpus metadata (source_doi,
source_title, research_question) this module never sees, and are separate,
harder problems left for a later milestone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_engine.extraction.sections import SectionSpan
from knowledge_engine.parser import ParsedPage
from knowledge_engine.sentence_split import split_sentence_spans

CLAIM_CANDIDATE_RULES_VERSION = "m17-claim-candidate-v1"

_CANDIDATE_SECTION_TYPES = frozenset({"results", "conclusion"})

# Each pattern is a deterministic, auditable signal that a sentence reports a
# quantitative or comparative finding rather than background/methods prose.
# Order matters only for which signal name is reported when several match;
# detection itself does not depend on order.
_SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    # Checked most-specific first: "95% CI" and a bare percentage both contain
    # a "%", and a p-value can appear alongside either, so the more specific
    # signal name should win when a sentence matches more than one pattern.
    "confidence_interval": re.compile(r"(?i)\b95%\s*CI\b"),
    "p_value": re.compile(r"(?i)\bp\s*[<>=]\s*0?\.\d+"),
    "comparative_phrase": re.compile(
        r"(?i)\b(?:significantly (?:greater|lower|higher|less) than"
        r"|compared (?:with|to)|versus|vs\.)"
    ),
    "percentage": re.compile(r"\d+(?:\.\d+)?\s*%"),
}


@dataclass(frozen=True)
class ClaimCandidate:
    """One candidate claim sentence with its exact source span."""

    sentence_text: str
    section_type: str
    page_number: int
    start_offset: int
    end_offset: int
    matched_signal: str
    rules_version: str


def detect_claim_candidates(
    pages: Sequence[ParsedPage], sections: Sequence[SectionSpan]
) -> tuple[ClaimCandidate, ...]:
    """Detect candidate claim sentences within results/conclusion sections.

    A section type outside results/conclusion is ignored. A sentence with no
    quantitative or comparative signal is not a candidate -- absence is
    never guessed into a low-confidence candidate.
    """

    candidates: list[ClaimCandidate] = []
    for section in sections:
        if section.section_type not in _CANDIDATE_SECTION_TYPES:
            continue
        for page_number, local_start, local_end in _section_page_ranges(section, pages):
            page_text = _page_text(pages, page_number)
            region = page_text[local_start:local_end]
            for sentence_start, sentence_end in split_sentence_spans(region):
                sentence = region[sentence_start:sentence_end]
                matched_signal = _first_matching_signal(sentence)
                if matched_signal is None:
                    continue
                candidates.append(
                    ClaimCandidate(
                        sentence_text=sentence,
                        section_type=section.section_type,
                        page_number=page_number,
                        start_offset=local_start + sentence_start,
                        end_offset=local_start + sentence_end,
                        matched_signal=matched_signal,
                        rules_version=CLAIM_CANDIDATE_RULES_VERSION,
                    )
                )
    return tuple(candidates)


def _section_page_ranges(
    section: SectionSpan, pages: Sequence[ParsedPage]
) -> list[tuple[int, int, int]]:
    """Return (page_number, local_start, local_end) for each page a section covers."""

    ranges: list[tuple[int, int, int]] = []
    for page in pages:
        if page.page_number < section.start_page_number:
            continue
        if page.page_number > section.end_page_number:
            continue
        local_start = section.start_offset if page.page_number == section.start_page_number else 0
        local_end = (
            section.end_offset if page.page_number == section.end_page_number else len(page.text)
        )
        ranges.append((page.page_number, local_start, local_end))
    return ranges


def _page_text(pages: Sequence[ParsedPage], page_number: int) -> str:
    for page in pages:
        if page.page_number == page_number:
            return page.text
    return ""


def _first_matching_signal(sentence: str) -> str | None:
    for signal_name, pattern in _SIGNAL_PATTERNS.items():
        if pattern.search(sentence):
            return signal_name
    return None
