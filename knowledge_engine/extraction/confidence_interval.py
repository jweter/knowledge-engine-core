"""Deterministic confidence-interval extraction from one claim's own sentence.

Issue #449 ("Research Report v1 support: structured evidence needed for
report-level auditability") names "effect size and confidence interval when
extractable" as structured fields report consumers need but that no prior
extraction module produced -- `knowledge_engine.extraction.claims` already
detects that a candidate sentence *mentions* a 95%/99% CI (its
`"confidence_interval"` `matched_signal`), but that detection was only ever
used to pick which claim-candidate sentence to keep, never surfaced as its
own structured `DraftEvidenceItem` field.

Unlike `knowledge_engine.extraction.pico`'s population/intervention/
comparator/outcome, a confidence interval is not a paper-level fact -- two
different results in the same paper (a primary and a secondary endpoint, say)
routinely carry two different intervals. So this extracts per claim-candidate
sentence, not once per paper.

This intentionally does not parse the interval into separate numeric lower/
upper bounds. Real papers state a CI in enough different shapes -- a plain
range, a range paired with an effect measure abbreviation (OR/RR/HR/aOR),
units that vary by outcome -- that splitting it out mechanically would risk
inventing structure the source sentence does not unambiguously state. The
matched sentence itself is the value, the same "quote, never parse or
paraphrase" contract `extract_pico` already established for its own fields.
A sentence with no CI mention is `None`, never an empty/guessed placeholder.
"""

from __future__ import annotations

import re

CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION = "m74-confidence-interval-v1"

_CONFIDENCE_INTERVAL_PATTERN = re.compile(r"(?i)\b(?:95|99)\s*%\s*ci\b")


def extract_confidence_interval(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states an explicit CI, else `None`.

    Matches a bare "95% CI"/"99% CI" mention (case-insensitive, tolerant of
    stray whitespace around the "%"), the same shape
    `knowledge_engine.extraction.claims`'s `confidence_interval` signal and
    `knowledge_engine.extraction.pico`'s statistical-result guard already
    use, so detection stays consistent across every module that reasons
    about CI mentions.
    """

    if _CONFIDENCE_INTERVAL_PATTERN.search(sentence_text):
        return sentence_text
    return None


__all__ = [
    "CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION",
    "extract_confidence_interval",
]
