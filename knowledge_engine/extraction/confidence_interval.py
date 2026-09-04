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

v2 (post-review): v1's pattern only matched a literal "95%"/"99%" immediately
followed by "CI", the same narrow shape
`knowledge_engine.extraction.claims`'s `confidence_interval` signal and
`knowledge_engine.extraction.pico`'s statistical-result guard use for their
own, different purposes (picking which candidate sentence to keep;
excluding a statistical-result sentence from a PICO field). Checking the
checked-in corpora's own `evidence_records.jsonl` files found real claim
sentences this missed entirely: other confidence levels ("80% CI", "90%
CI" -- not just 95/99), the plural "CIs", the spelled-out "confidence
interval"/"confidence intervals", and the reversed "CI 95%" order. The
pattern now accepts any of these, still requiring a percentage number
directly adjacent to the CI marker (either order) so an unrelated "CI"
usage elsewhere in a long sentence, or a methods-only mention with no
stated interval, is not mistaken for one -- absence is still never guessed
into a placeholder.
"""

from __future__ import annotations

import re

CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION = "m74-confidence-interval-v2"

_PERCENT_THEN_CI_PATTERN = re.compile(
    r"(?i)\d{1,3}(?:\.\d+)?\s*%\s*,?\s*(?:CIs?\b|confidence intervals?\b)"
)
_CI_THEN_PERCENT_PATTERN = re.compile(r"(?i)\bCIs?\s*,?\s*\d{1,3}(?:\.\d+)?\s*%")


def extract_confidence_interval(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states an explicit CI, else `None`.

    Matches a percentage (any value, e.g. "80%"/"90%"/"95%"/"99%", not just
    95/99) directly adjacent to a "CI"/"CIs"/"confidence interval(s)"
    marker, in either order ("95% CI" or "CI 95%") and tolerant of stray
    whitespace, a newline, or a comma between them. A percentage and a CI
    marker that are not directly adjacent -- e.g. two unrelated numbers
    elsewhere in a long sentence -- are not matched, keeping detection
    conservative.
    """

    if _PERCENT_THEN_CI_PATTERN.search(sentence_text) or _CI_THEN_PERCENT_PATTERN.search(
        sentence_text
    ):
        return sentence_text
    return None


__all__ = [
    "CONFIDENCE_INTERVAL_EXTRACTION_RULES_VERSION",
    "extract_confidence_interval",
]
