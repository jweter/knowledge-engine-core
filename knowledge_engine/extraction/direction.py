"""Deterministic claim framing-cue classification.

Classifies each ClaimCandidate (M17) by how its sentence frames itself
relative to *other work or expectations referenced in its own text* -- not
relative to a research question. This module deliberately does not implement
the evidence-record schema's `evidence_direction` field.

`docs/vs7_manual_evidence_record.md`'s worked example establishes that
`evidence_direction` (supports/contradicts/qualifies/contextualizes) is
defined relative to a specific `research_question`: "This record does not
say that the Knowledge Engine has proven the research question. It says
that this paper provides evidence bearing on the question." A ClaimCandidate
has no `research_question` attached -- that field comes from corpus metadata
this module never sees. Defaulting a candidate to a supports-equivalent
label whenever no contrast/hedge cue fires would silently assume a research
question no one supplied.

What a bare sentence can honestly tell us, with no research question needed,
is how it frames itself relative to prior work the sentence itself
references. That is this module's actual, narrower scope: `contextualizes`,
`contradicts`, `qualifies`, or `unclassified` when no such cue is present --
never a fourth label standing in for "supports".
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_engine.extraction.claims import ClaimCandidate

CLAIM_FRAMING_RULES_VERSION = "m18-claim-framing-v1"

# Contradiction patterns are checked before contextualizes patterns so that
# negated-consistency phrasing (e.g. "not consistent with prior trials") is
# never misclassified as contextualizes.
_CONTRADICTS_PATTERNS: dict[str, re.Pattern[str]] = {
    "not consistent with": re.compile(r"(?i)\bnot\s+(?:entirely\s+)?consistent with\b"),
    "not in line with": re.compile(r"(?i)\bnot\s+in line with\b"),
    "in contrast to": re.compile(r"(?i)\bin contrast to\b"),
    "contrary to": re.compile(r"(?i)\bcontrary to\b"),
    "unlike prior": re.compile(r"(?i)\bunlike (?:previous|prior|earlier)\b"),
    "inconsistent with": re.compile(r"(?i)\binconsistent with\b"),
    "differed from prior": re.compile(r"(?i)\bdiffered from (?:previous|prior|earlier)\b"),
}

_CONTEXTUALIZES_PATTERNS: dict[str, re.Pattern[str]] = {
    "consistent with": re.compile(r"(?i)\bconsistent with\b"),
    "in line with": re.compile(r"(?i)\bin line with\b"),
    "in agreement with": re.compile(r"(?i)\bin agreement with\b"),
    "concordant with": re.compile(r"(?i)\bconcordant with\b"),
    "similar to prior": re.compile(r"(?i)\bsimilar to (?:previous|prior|earlier)\b"),
}

# Deliberately excludes bare discourse connectives ("however", "although"):
# a candidate is only ever one isolated sentence (M17 supplies no
# surrounding context), so a connective's antecedent may lie outside the
# candidate, or may not qualify the result at all. Only self-contained
# qualifying constructions -- the hedge is stated within the same sentence
# as the finding -- count as a local cue.
_QUALIFIES_PATTERNS: dict[str, re.Pattern[str]] = {
    "did not reach significance": re.compile(
        r"(?i)\bdid not reach (?:statistical )?significance\b"
    ),
    "trend toward": re.compile(r"(?i)\btrend(?:ed)? toward\b"),
    "not statistically significant": re.compile(r"(?i)\bnot statistically significant\b"),
}

_FRAMING_PATTERN_GROUPS: tuple[tuple[str, dict[str, re.Pattern[str]]], ...] = (
    ("contradicts", _CONTRADICTS_PATTERNS),
    ("contextualizes", _CONTEXTUALIZES_PATTERNS),
    ("qualifies", _QUALIFIES_PATTERNS),
)


@dataclass(frozen=True)
class ClaimFraming:
    """How one claim candidate frames itself relative to prior work."""

    candidate: ClaimCandidate
    framing: str
    matched_cue: str | None
    rules_version: str


def classify_claim_framing(candidates: Sequence[ClaimCandidate]) -> tuple[ClaimFraming, ...]:
    """Classify each candidate's framing relative to prior work it references.

    A candidate with no contextualizes/contradicts/qualifies cue is
    `unclassified` -- absence is never guessed into a supports-equivalent
    label, since that would require a research question this module never
    sees.
    """

    classifications: list[ClaimFraming] = []
    for candidate in candidates:
        framing, matched_cue = _classify_sentence(candidate.sentence_text)
        classifications.append(
            ClaimFraming(
                candidate=candidate,
                framing=framing,
                matched_cue=matched_cue,
                rules_version=CLAIM_FRAMING_RULES_VERSION,
            )
        )
    return tuple(classifications)


def _classify_sentence(sentence: str) -> tuple[str, str | None]:
    for framing, patterns in _FRAMING_PATTERN_GROUPS:
        for cue_name, pattern in patterns.items():
            if pattern.search(sentence):
                return framing, cue_name
    return "unclassified", None
