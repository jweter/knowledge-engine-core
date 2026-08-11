"""M72: automated Relationship classification -- LLM-proposed, grounding-verified.

Every earlier review-gate milestone in this project (M52's evidence
classification, M69's LLM-grounded PICO extraction, the golden-map
grounding verifier) replaced a step that used to require someone to read
source text with a deterministic check on an LLM's proposal. The
Relationship Layer (`supports`/`contradicts`/`qualifies`/`contextualizes`/
`supersedes`) was the one place that never happened --
`relationship_candidate_ranking.py`, `cli.py`'s `relationship-validate`,
and multiple `entrypoint.py` report builders all stated that deciding
whether a relationship exists "remains entirely a human judgment call."
This module is the fix: the same architecture M69 already established,
applied to the one milestone it never covered.

An LLM proposes a `relationship_type`, a short `quoted_evidence` phrase,
and a `rationale` for a ranked candidate pair
(`relationship_candidate_ranking.RankedCandidate`). The proposal is
accepted only when `relationship_type` is one of the five schema-valid
values *and* `quoted_evidence` -- not the free-text `rationale` -- passes
`knowledge_engine.extraction.grounding.verify_grounding` against the two
claims' own `claim_text`/`result_summary`/`outcome` text. Grounding a
short, near-verbatim phrase rather than an entire explanatory sentence
mirrors M69's own PICO-field grounding exactly (`extract_pico_for_candidate`
grounds one short field value at a time, never a whole paragraph) --
`verify_grounding`'s near-match check compares one proposed string
against 1-3-sentence source windows, so grounding a short quote gives it
a real shot at matching; grounding a full paraphrased rationale, which
necessarily adds connective and interpretive language a source sentence
never contains, would fail almost every genuine relationship a model
could correctly identify. A proposal that fails either check is dropped,
never accepted with a caveat -- the same "skip, don't invent" posture
every prior automated-review milestone in this project has held to.

**What grounding verification does not check, found during live
verification against the real GLP-1 corpus:** `quoted_evidence` passing
`verify_grounding` proves the quote is real text from one of the two
claims; it does not prove `relationship_type` is the correct label for
what that quote shows. A live run surfaced multiple accepted
classifications whose own `rationale` used language like "directly
contradicts" while `relationship_type` was `"supersedes"` -- the model's
reasoning and its structured label disagreed, and grounding alone cannot
catch that, since the quote itself was genuinely real. This is a
real, named limitation, not silently corrected: a keyword
cross-check (does `rationale` contain language suggesting a different
type than the one chosen?) would encode brittle heuristics of its own
and was not attempted here. Every accepted record's full `rationale` is
persisted in the `RelationshipRecord`, so this class of error is visible
and correctable via `ke relationship-validate`'s own review path, not
hidden by the automated one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from knowledge_engine.extraction.grounding import DEFAULT_MIN_SIMILARITY, verify_grounding
from knowledge_engine.llm import LocalLLM, LocalLLMError

RELATIONSHIP_CLASSIFICATION_RULES_VERSION = "m72-relationship-classification-v1"

ALLOWED_RELATIONSHIP_TYPES = (
    "supports",
    "contradicts",
    "qualifies",
    "contextualizes",
    "supersedes",
)

_FIELD_NAMES = ("claim_text", "result_summary", "outcome")


@dataclass(frozen=True)
class RelationshipClassificationResult:
    """One candidate pair's outcome from a single automated-classification pass.

    `accepted` is `True` only when the model proposed a schema-valid
    `relationship_type` and its `quoted_evidence` passed grounding against
    at least one claim's own text -- a pair the model could not
    confidently classify stays unclassified (`accepted=False`), not
    silently downgraded into a guessed relationship.
    """

    source_evidence_record_id: str
    target_evidence_record_id: str
    accepted: bool
    relationship_type: str | None
    rationale: str | None
    skipped_reason: str | None


def classify_relationship(
    llm: LocalLLM,
    claim_a: dict[str, Any],
    claim_b: dict[str, Any],
    *,
    min_similarity: float = DEFAULT_MIN_SIMILARITY,
    max_tokens: int = 300,
) -> RelationshipClassificationResult:
    """Propose and grounding-verify a relationship between two Evidence Records.

    `claim_a`/`claim_b` are full `EvidenceRecord` dicts (not `GraphClaim`
    rows) -- the caller looks them up by `evidence_record_id`, the same
    `evidence_records_by_id` pattern `relationship_candidate_ranking.py`
    and `_build_relationship_review_worksheet` already use. Never raises
    on a proposal that fails to parse or ground -- reports it, the same
    "record what happened, do not crash" discipline every prior
    automated-review pipeline in this project follows.
    """

    source_id = str(claim_a.get("evidence_record_id", ""))
    target_id = str(claim_b.get("evidence_record_id", ""))

    prompt = _build_prompt(claim_a, claim_b)
    try:
        raw_output = llm.generate(prompt, max_tokens=max_tokens)
    except LocalLLMError as exc:
        return RelationshipClassificationResult(
            source_id, target_id, False, None, None, f"model call failed: {exc}"
        )

    parsed = _parse_response(raw_output)
    if parsed is None:
        return RelationshipClassificationResult(
            source_id, target_id, False, None, None, "model output not parseable"
        )

    relationship_type, quoted_evidence, rationale = parsed
    if relationship_type not in ALLOWED_RELATIONSHIP_TYPES:
        return RelationshipClassificationResult(
            source_id,
            target_id,
            False,
            None,
            None,
            f"unrecognized relationship_type: {relationship_type!r}",
        )

    if not quoted_evidence.strip() or not rationale.strip():
        return RelationshipClassificationResult(
            source_id, target_id, False, None, None, "empty quoted_evidence or rationale"
        )

    combined_source_text = " ".join(
        str(claim.get(field_name) or "")
        for claim in (claim_a, claim_b)
        for field_name in _FIELD_NAMES
    )
    grounding = verify_grounding(
        quoted_evidence, combined_source_text, min_similarity=min_similarity
    )
    if not grounding.grounded:
        return RelationshipClassificationResult(
            source_id,
            target_id,
            False,
            None,
            None,
            "quoted_evidence not grounded in either claim's own claim_text/result_summary/outcome",
        )

    return RelationshipClassificationResult(
        source_id, target_id, True, relationship_type, rationale.strip(), None
    )


def _build_prompt(claim_a: dict[str, Any], claim_b: dict[str, Any]) -> str:
    allowed = ", ".join(ALLOWED_RELATIONSHIP_TYPES)
    return (
        "You are classifying the relationship between two scientific claims "
        "already extracted from published papers. Decide whether, and how, "
        "they relate.\n\n"
        f"Claim A (id={claim_a.get('evidence_record_id')}):\n"
        f"  claim_text: {claim_a.get('claim_text') or '(none)'}\n"
        f"  outcome: {claim_a.get('outcome') or '(none)'}\n"
        f"  result_summary: {claim_a.get('result_summary') or '(none)'}\n\n"
        f"Claim B (id={claim_b.get('evidence_record_id')}):\n"
        f"  claim_text: {claim_b.get('claim_text') or '(none)'}\n"
        f"  outcome: {claim_b.get('outcome') or '(none)'}\n"
        f"  result_summary: {claim_b.get('result_summary') or '(none)'}\n\n"
        f'Respond with EXACTLY ONE JSON object: {{"relationship_type": "<one of {allowed}>", '
        '"quoted_evidence": "<a short phrase, quoted or closely paraphrased VERBATIM from '
        "one of Claim A/B's claim_text, outcome, or result_summary above -- this must be "
        'text that actually appears above, not a summary of it>", '
        '"rationale": "<one or two sentences explaining why quoted_evidence supports this '
        'relationship_type>"}. No prose before or after it, no markdown code fence.\n\n'
        "JSON:"
    )


def _parse_response(raw_output: str) -> tuple[str, str, str] | None:
    """Extract `(relationship_type, quoted_evidence, rationale)` from a brace-balanced JSON object.

    Same fence-tolerant, brace-balanced scan `plan_from_question` uses in
    the sibling `ai` repo for the same "model sometimes wraps its JSON
    in markdown or adds a stray sentence" problem.
    """

    start = raw_output.find("{")
    if start == -1:
        return None
    depth = 0
    end = None
    for index in range(start, len(raw_output)):
        character = raw_output[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                end = index
                break
    if end is None:
        return None

    try:
        payload = json.loads(raw_output[start : end + 1])
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    relationship_type = payload.get("relationship_type")
    quoted_evidence = payload.get("quoted_evidence")
    rationale = payload.get("rationale")
    if (
        not isinstance(relationship_type, str)
        or not isinstance(quoted_evidence, str)
        or not isinstance(rationale, str)
    ):
        return None

    return relationship_type, quoted_evidence, rationale
