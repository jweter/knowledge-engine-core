"""Deterministic numeric-fidelity check for a golden evidence map against its own source text.

The project's standing decision on review at scale (`docs/roadmap/long_term_vision.md`'s
"Decision: automated evidence review at scale (M69)") already rejected human reading as
a required gate for an *Evidence Record* -- the same reasoning applies to a golden
evidence map's own review status. The 2026-08-10 record-fidelity checks for the
oncology and mental-health golden maps were real, thorough, and independently
reproducible, but were performed by the same AI system (Claude) that compiled the
maps -- not a genuinely independent check. This module is that independent check:
a pure, deterministic, non-LLM text comparison, the same posture
`knowledge_engine.extraction.grounding.verify_grounding` already established for
per-field extraction.

This module deliberately does **not** reuse `verify_grounding` itself. That function's
sentence-window near-match was built to check a short, near-verbatim LLM-proposed
field (a PICO value) against source text -- tested against a golden map's own
`result_summary`, a multi-sentence, heavily reworded synthesis of several numbers, it
produces near-total false negatives (confirmed empirically: every sentence of a
manually-verified-faithful record scored below the similarity threshold, because the
prose itself was rewritten even though every number in it was correct). The check
that actually matters for a `result_summary`'s fidelity is not "does the prose match"
but "does every number it cites actually appear in the source" -- which is what this
module checks instead, extracting numeric tokens from both texts and comparing sets.

This is a narrower claim than full semantic grounding: it does not (and cannot) verify
that a number is attached to the *correct* claim, only that it is genuinely present in
the source page. That is still a real, tractable, and useful independent check --
exactly the two limitations this check surfaces for the oncology map (Dang's
cross-page-12 figure, Nodbrant's non-machine-readable table) are real, previously
manually-identified gaps, not false signal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GOLDEN_MAP_GROUNDING_RULES_VERSION = "golden-map-numeric-grounding-v1"

_NUMBER_RE = re.compile(r"\d+\.\d+|\d+")


def extract_numbers(text: str | None) -> frozenset[str]:
    """Extract every decimal/integer numeric token from `text`.

    Deliberately does not treat a leading `-` as a negative sign: in this
    project's typed-statistics prose, a hyphen between two numbers almost
    always separates a confidence interval's lower and upper bound (e.g.
    "0.75-0.90"), not a genuine negative value. A sign-aware regex mis-splits
    exactly that common case, turning a correctly-cited CI upper bound into a
    fabricated "missing negative number." This trades away the (rare) ability
    to distinguish a genuinely negative reported value (e.g. a raw HDRS-score
    change) from its unsigned magnitude, in exchange for not mis-flagging
    every confidence-interval range in the corpus as a fidelity miss.
    """

    if not text:
        return frozenset()
    return frozenset(_NUMBER_RE.findall(text))


@dataclass(frozen=True)
class RecordGroundingResult:
    """One Evidence Record's numeric-fidelity result against its own source page text."""

    evidence_record_id: str
    source_page_found: bool
    """False when the source paper/page could not be resolved in the local database --
    a missing-data result, distinct from a found-but-ungrounded result."""
    numbers_checked: int
    missing_numbers: tuple[str, ...]
    """Numbers present in `result_summary` but not found anywhere in the source page
    text, sorted ascending. Empty when every cited number was found."""

    @property
    def fully_grounded(self) -> bool:
        return self.source_page_found and not self.missing_numbers


def check_record_numeric_grounding(
    evidence_record_id: str,
    result_summary: str | None,
    source_page_text: str | None,
) -> RecordGroundingResult:
    """Check whether every number in `result_summary` appears in `source_page_text`.

    `source_page_text` is `None` when the record's `source_span.local_pdf_path`/
    `page_number` could not be resolved to a real page in the local database (paper
    not imported, page text not extracted, or a stale/renamed path) -- reported as
    `source_page_found=False`, never silently treated as a passing or failing
    grounding result.
    """

    if source_page_text is None:
        return RecordGroundingResult(evidence_record_id, False, 0, ())

    result_numbers = extract_numbers(result_summary)
    source_numbers = extract_numbers(source_page_text)
    missing = tuple(sorted(result_numbers - source_numbers, key=float))
    return RecordGroundingResult(evidence_record_id, True, len(result_numbers), missing)
