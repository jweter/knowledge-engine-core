"""Deterministic, abbreviation-aware sentence splitting.

Shared by `knowledge_engine.extraction.claims` (M17 claim-candidate
detection, which needs exact source offsets to cite a claim's span) and
`knowledge_engine.candidate_review` (M14 adjudication's disease/intervention
co-occurrence check, which only needs sentence text). Splitting is
deliberately conservative: split only at a terminal `.!?` immediately
followed by whitespace and an uppercase letter, and never immediately after
a known abbreviation. A missed sentence boundary is safe (at worst two
sentences are treated as one, and the combined text either does or doesn't
match whatever signal is being checked); a corrupted mid-sentence split is
not, since it could sever a signal from the claim or scope evidence it
belongs to.
"""

from __future__ import annotations

import re

ABBREVIATIONS = frozenset(
    {
        "vs",
        "e.g",
        "i.e",
        "fig",
        "figs",
        "et al",
        "al",
        "approx",
        "no",
        "dr",
        "mr",
        "mrs",
        "ms",
        "prof",
        "cf",
        "etc",
        "vol",
        "eq",
        "ref",
    }
)
_SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?]+(?=\s+[A-Z])")
_TRAILING_WORD_PATTERN = re.compile(r"([A-Za-z]+(?:\.[A-Za-z]+)?)\s*$")
_TRAILING_TWO_WORDS_PATTERN = re.compile(r"([A-Za-z]+\s+[A-Za-z]+)\s*$")
# No entry in ABBREVIATIONS (or its two-word combinations, e.g. "et al") comes
# close to this length, so bounding the search window to it cannot change which
# boundaries match -- it only stops each check from re-scanning the entire
# preceding document text on every sentence boundary (see
# _ends_with_abbreviation).
_ABBREVIATION_CHECK_WINDOW = 40


def split_sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) offsets of trimmed sentences within text."""

    boundaries: list[int] = []
    for match in _SENTENCE_BOUNDARY_PATTERN.finditer(text):
        preceding = text[: match.start()]
        if _ends_with_abbreviation(preceding):
            continue
        boundaries.append(match.end())

    spans: list[tuple[int, int]] = []
    cursor = 0
    for boundary in [*boundaries, len(text)]:
        raw = text[cursor:boundary]
        stripped = raw.strip()
        if stripped:
            local_start = raw.index(stripped)
            spans.append((cursor + local_start, cursor + local_start + len(stripped)))
        cursor = boundary
    return spans


def split_sentences(text: str) -> list[str]:
    """Return trimmed sentence texts within text, discarding their offsets."""

    return [text[start:end] for start, end in split_sentence_spans(text)]


def _ends_with_abbreviation(preceding: str) -> bool:
    """Check whether `preceding` ends with a known abbreviation.

    `preceding` is `text[:match.start()]` for each sentence-boundary
    candidate, so it grows with every match found later in a document --
    searching it in full made this function, and the paper-scale M40
    extraction-review batch that first exercised long real documents
    through it, quadratic in document length (one real paper's ~180K
    characters took 30+ seconds). Only the last few characters can ever
    matter for a trailing-word/trailing-two-word match, so bounding the
    search window makes each check O(1) regardless of document length.
    """

    window = preceding[-_ABBREVIATION_CHECK_WINDOW:]
    word_match = _TRAILING_WORD_PATTERN.search(window)
    if word_match and word_match.group(1).lower().rstrip(".") in ABBREVIATIONS:
        return True
    two_word_match = _TRAILING_TWO_WORDS_PATTERN.search(window)
    return bool(two_word_match and two_word_match.group(1).lower() in ABBREVIATIONS)
