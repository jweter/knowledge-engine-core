"""Deterministic grounding verification for LLM-proposed extraction fields.

M69's automated evidence-review pipeline (`docs/roadmap/long_term_vision.md`'s
"Decision: automated evidence review at scale") replaces human reading as the
review gate with an LLM-grounded extraction path. The LLM half of that path
can propose plausible-sounding text that is not actually in the source paper
-- this module is the check that catches that before it is ever accepted.
Nothing like it existed in this codebase before M69 (confirmed by a full-repo
survey across `core`, `knowledge-engine-web`, and `knowledge-engine-ai`).

This module never calls an LLM and never reads a database -- it is a pure,
deterministic text-comparison function, the same "skip, don't invent" posture
M18's `classify_claim_framing` and M28's `extract_pico` already use for their
own absence-of-cue cases. A proposed field that does not trace back to the
source text is dropped by the caller, not guessed into a passing grade.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

from knowledge_engine.sentence_split import split_sentences

GROUNDING_RULES_VERSION = "m69-grounding-v1"

_WHITESPACE_RE = re.compile(r"\s+")

DEFAULT_MIN_SIMILARITY = 0.75


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


@dataclass(frozen=True)
class GroundingResult:
    """Whether one proposed field's text actually traces to the source."""

    grounded: bool
    match_type: str
    """One of "exact_substring", "near_match", or "not_grounded"."""
    similarity: float
    """1.0 for an exact substring match; a difflib ratio in [0, 1) otherwise."""
    matched_source_excerpt: str | None
    rules_version: str


def verify_grounding(
    proposed_text: str,
    source_text: str,
    *,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
) -> GroundingResult:
    """Check whether `proposed_text` genuinely appears in `source_text`.

    Two-tier check, cheapest and strongest signal first:

    1. Exact substring (whitespace-collapsed, case-folded) -- the LLM
       reproduced the source text verbatim or near-verbatim.
       `match_type="exact_substring"`, `similarity=1.0`.
    2. Near-match: `source_text` is split into sentences (reusing the same
       `split_sentences` M17's claim-candidate detection already uses), and
       every contiguous run of 1-3 sentences is scored against
       `proposed_text` with word-level `difflib.SequenceMatcher` (stdlib,
       no new dependency) -- word tokens tolerate an LLM's light rewording
       (synonym swaps, minor reordering) far better than a raw character
       comparison would. The best-scoring window passes at
       `similarity >= min_similarity`, without accepting an unrelated or
       fabricated sentence.

    A proposed field with no exact or near match anywhere in the source is
    `grounded=False`, `match_type="not_grounded"` -- the caller must drop
    it, never accept it with a caveat.
    """

    if not proposed_text or not proposed_text.strip():
        return GroundingResult(False, "not_grounded", 0.0, None, GROUNDING_RULES_VERSION)

    normalized_proposed = _normalize(proposed_text)
    normalized_source = _normalize(source_text)

    if not normalized_source:
        return GroundingResult(False, "not_grounded", 0.0, None, GROUNDING_RULES_VERSION)

    if normalized_proposed in normalized_source:
        return GroundingResult(
            True, "exact_substring", 1.0, proposed_text.strip(), GROUNDING_RULES_VERSION
        )

    sentences = split_sentences(source_text)
    if not sentences:
        return GroundingResult(False, "not_grounded", 0.0, None, GROUNDING_RULES_VERSION)

    proposed_words = normalized_proposed.split()
    matcher = difflib.SequenceMatcher(a=proposed_words, autojunk=False)
    best_ratio = 0.0
    best_excerpt: str | None = None
    for window_size in (1, 2, 3):
        for start in range(0, max(1, len(sentences) - window_size + 1)):
            window = " ".join(sentences[start : start + window_size])
            matcher.set_seq2(_normalize(window).split())
            ratio = matcher.ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_excerpt = window

    if best_ratio >= min_similarity:
        return GroundingResult(
            True, "near_match", round(best_ratio, 3), best_excerpt, GROUNDING_RULES_VERSION
        )
    return GroundingResult(
        False, "not_grounded", round(best_ratio, 3), None, GROUNDING_RULES_VERSION
    )
