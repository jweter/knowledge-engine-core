"""LLM-grounded, per-claim-candidate PICO extraction (M69).

`docs/roadmap/long_term_vision.md`'s "Decision: automated evidence review
at scale" names the bug this module fixes: `extract_pico` (M28) runs once
per *paper*, then `build_draft_evidence_items` broadcasts that single
paper-level `population`/`intervention`/`comparator`/`outcome` extraction
onto every claim candidate in the paper, regardless of which
sentence/subgroup/section a given claim actually came from. M68's manual
review found this in the wild: a claim about one subgroup's secondary
endpoint got the paper's overall enrolled-population sentence glued onto
it, and vice versa.

This module's fix is narrow and specific: extract PICO fields **per
candidate**, scoped to bounded local context (the claim page plus page 1
when they differ), not the whole paper. The page-1 addition is an M69
follow-up for terse result sentences whose study framing lives in the
title/abstract. It does not replace
`knowledge_engine.extraction.pico.extract_pico` (still used by the
deterministic M17-M28 draft-generation pipeline); it is a separate,
additive extraction path for M69's automated-review pipeline, used to
re-derive PICO fields for records the deterministic per-paper extraction
got wrong.

Every field the LLM proposes is checked with
`knowledge_engine.extraction.grounding.verify_grounding` against that same
local context before being accepted -- a proposed field that does not
trace back to the source text is dropped, never guessed. This module never
judges what a claim *means* (`core`'s "never decide truth" seam is
unchanged); it only asks the local model to locate PICO-relevant spans
inside a page it has already been given, the same paper-intrinsic
extraction M28 already does, with an LLM as a better pattern-matcher and a
deterministic grounding check as the safety net. The v1 provenance label
remains recognized for records produced before the bounded page-1 follow-up;
newly accepted records use v2.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from knowledge_engine.extraction.claims import ClaimCandidate
from knowledge_engine.extraction.grounding import (
    DEFAULT_MIN_SIMILARITY,
    GroundingResult,
    verify_grounding,
)
from knowledge_engine.llm import LocalLLM, LocalLLMError

LLM_GROUNDED_PICO_RULES_VERSION = "m69-llm-grounded-pico-v2"
LLM_GROUNDED_PICO_RULES_VERSIONS = frozenset(
    {"m69-llm-grounded-pico-v1", LLM_GROUNDED_PICO_RULES_VERSION}
)

_FIELD_NAMES = ("population", "intervention", "comparator", "outcome")

_PROMPT_TEMPLATE = """You are extracting facts from bounded source context \
from one clinical research paper. You will be shown one specific finding \
(the "claim sentence"), the full page it came from, and sometimes page 1 \
of the same paper for title/abstract study framing.

Your task: find the sentence(s) in the provided source context, if any, that \
state the paper's Population, Intervention, Comparator, and Outcome \
relevant to that claim.

Rules:
- Quote the provided source pages' own wording as closely as possible. Do not \
paraphrase, summarize, or invent.
- If a field is not stated anywhere in the provided source context, use an \
empty string "" \
for it. Never guess.
- Respond with ONLY a JSON object, no other text, in exactly this shape:
{{"population": "...", "intervention": "...", "comparator": "...", "outcome": "..."}}

Claim sentence: {claim_sentence}

Claim page text:
{claim_page_text}

{first_page_context}

JSON:"""


@dataclass(frozen=True)
class GroundedField:
    """One PICO field's LLM-proposed value, after a grounding check.

    `value` is `None` whenever the LLM proposed nothing, or proposed
    something that failed grounding -- callers must never fall back to an
    ungrounded proposal.
    """

    value: str | None
    grounding: GroundingResult | None


@dataclass(frozen=True)
class LlmGroundedPico:
    """One claim candidate's per-candidate, grounding-verified PICO fields."""

    candidate: ClaimCandidate
    population: GroundedField
    intervention: GroundedField
    comparator: GroundedField
    outcome: GroundedField
    rules_version: str


def extract_pico_for_candidate(
    llm: LocalLLM,
    candidate: ClaimCandidate,
    page_text: str,
    *,
    paper_first_page_text: str | None = None,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    max_tokens: int = 600,
) -> LlmGroundedPico:
    """Extract PICO fields from the claim page and, when supplied, page 1.

    Never raises on a malformed or empty LLM response, or on the LLM being
    unreachable -- every field simply comes back ungrounded
    (`value=None`), the same "skip, don't invent" outcome as a field the
    LLM never proposed. Callers decide what to do with an all-ungrounded
    result (typically: leave the existing record's field alone rather than
    overwrite it with nothing).
    """

    additional_first_page = (
        paper_first_page_text
        if paper_first_page_text is not None and paper_first_page_text.strip()
        else None
    )
    first_page_context = (
        f"Paper page 1 text:\n{additional_first_page}"
        if additional_first_page is not None
        else "No additional page 1 context was provided."
    )
    prompt = _PROMPT_TEMPLATE.format(
        claim_sentence=candidate.sentence_text,
        claim_page_text=page_text,
        first_page_context=first_page_context,
    )
    grounding_context = (
        f"{page_text}\n\n{additional_first_page}"
        if additional_first_page is not None
        else page_text
    )
    try:
        raw_response = llm.generate(prompt, max_tokens=max_tokens)
    except LocalLLMError:
        raw_response = ""

    proposed = _parse_proposed_fields(raw_response)

    grounded_fields: dict[str, GroundedField] = {}
    for field_name in _FIELD_NAMES:
        proposed_text = proposed.get(field_name)
        if not proposed_text or not proposed_text.strip():
            grounded_fields[field_name] = GroundedField(value=None, grounding=None)
            continue
        result = verify_grounding(proposed_text, grounding_context, min_similarity=min_similarity)
        grounded_fields[field_name] = GroundedField(
            value=proposed_text.strip() if result.grounded else None,
            grounding=result,
        )

    return LlmGroundedPico(
        candidate=candidate,
        population=grounded_fields["population"],
        intervention=grounded_fields["intervention"],
        comparator=grounded_fields["comparator"],
        outcome=grounded_fields["outcome"],
        rules_version=LLM_GROUNDED_PICO_RULES_VERSION,
    )


_JSON_OBJECT_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _parse_proposed_fields(raw_response: str) -> dict[str, str]:
    """Best-effort extraction of the JSON object from a raw LLM response.

    A small local model does not always follow the "JSON only" instruction
    perfectly -- this tolerates surrounding prose by locating the first
    flat, non-nested `{...}` span (the expected shape is always a single
    object with four string keys, never nested), but never tolerates
    malformed JSON itself: a parse failure returns an empty dict, so every
    field ends up ungrounded rather than guessed from a corrupted parse.
    """

    match = _JSON_OBJECT_RE.search(raw_response)
    if match is None:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        field_name: value
        for field_name, value in parsed.items()
        if field_name in _FIELD_NAMES and isinstance(value, str)
    }
