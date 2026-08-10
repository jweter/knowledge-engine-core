"""Automated Evidence Record classification (M52).

M18's `direction.py` deliberately stopped short of `evidence_direction`
because that field is defined *relative to* a `research_question`
(`docs/history/vertical_slice/vs7_manual_evidence_record.md`), and a bare claim candidate has no
research question attached. Every evidence-promotion batch before this one
worked around that by having a human (in practice, the AI assistant driving
this repository, with the project owner's explicit review) read each
paper and supply both fields by hand.

The project owner decided that human-confirmation step was a bottleneck
disproportionate to its accuracy benefit and authorized removing it (see
`docs/roadmap.md`'s M52 entry and `docs/core_interface_contract.md`'s "The
seam" section). This module is the automated replacement:

- `generate_research_question` mechanically restates a draft item's own
  already-extracted PICO fields (M28) into a fixed sentence template. It is
  never a person's actual research question -- just a deterministic
  reflection of the paper's own population/intervention/comparator/outcome
  decomposition. A record is ineligible for automation (returns `None`)
  when any PICO field is missing or exceeds `_MAX_PICO_FIELD_LENGTH`, since
  M28 extracts a full first-matching *sentence* per field, and an
  unusually long one (a meta-analysis summarizing many included studies in
  one sentence, for example) produces an unreadable, run-on question rather
  than a genuine restatement -- this module only ever declines to
  automate, never guesses a shortened version.
- `classify_evidence_direction` extends M18's existing self-referential
  framing cue patterns with additional null-result phrasing cues, and,
  unlike M18, defaults to `supports` when no contrast/hedge/null cue fires.
  M18's docstring specifically warned that such a default would "silently
  assume a research question no one supplied" -- that concern no longer
  applies here, because the research question this module generates is
  itself mechanically derived from the same claim's own PICO fields, not
  an externally supplied one.

Every automated record is honestly labeled: `extraction_method` names this
module's ruleset version (never `manual_human_review`), and `review_notes`
states plainly that no human read or confirmed it.
"""

from __future__ import annotations

import re
from typing import Any

EVIDENCE_CLASSIFICATION_RULES_VERSION = "m52-evidence-classification-v1"

# Mirrors M18's `direction.py` cue vocabulary (contradicts/contextualizes/
# qualifies patterns) rather than importing its private pattern dicts --
# this module owns an independently versioned ruleset, so a future change
# to M18's patterns should not silently change this module's behavior.
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

_QUALIFIES_PATTERNS: dict[str, re.Pattern[str]] = {
    "did not reach significance": re.compile(
        r"(?i)\bdid not reach (?:statistical )?significance\b"
    ),
    "trend toward": re.compile(r"(?i)\btrend(?:ed)? toward\b"),
    "not statistically significant": re.compile(r"(?i)\bnot statistically significant\b"),
}

# M28's PICO fields are full first-matching sentences, not short noun
# phrases. Below this length, most fields read as reasonable template
# inputs (empirically checked against real corpus samples, see the M52
# design doc); above it, a template plugs in a run-on sentence rather than
# a concise clause, so this module declines to automate that record.
_MAX_PICO_FIELD_LENGTH = 300

# Extends M18's `_QUALIFIES_PATTERNS` with explicit null/non-significant
# result phrasing, which M18 never needed (it was classifying framing
# relative to *other work referenced in the sentence*, not the sentence's
# own result). These are exactly the phrasings that should not default to
# "supports": a claim stating no difference was found is not evidence
# supporting an effect existing.
_NULL_RESULT_PATTERNS: dict[str, re.Pattern[str]] = {
    "no significant difference": re.compile(r"(?i)\bno significant difference\b"),
    "not significantly different": re.compile(r"(?i)\bnot significantly different\b"),
    "did not differ": re.compile(r"(?i)\bdid not differ\b"),
    "did not differ significantly": re.compile(r"(?i)\bdid not differ significantly\b"),
    "no significant association": re.compile(r"(?i)\bno significant association\b"),
    "was not associated with": re.compile(r"(?i)\bwas not associated with\b"),
    "no association was observed": re.compile(r"(?i)\bno association was observed\b"),
}

_DIRECTION_PATTERN_GROUPS: tuple[tuple[str, dict[str, re.Pattern[str]]], ...] = (
    ("contradicts", _CONTRADICTS_PATTERNS),
    ("contextualizes", _CONTEXTUALIZES_PATTERNS),
    ("qualifies", {**_QUALIFIES_PATTERNS, **_NULL_RESULT_PATTERNS}),
)


def generate_research_question(
    population: str | None,
    intervention: str | None,
    comparator: str | None,
    outcome: str | None,
) -> str | None:
    """Template a research question from already-extracted PICO fields.

    Requires all four fields, each no longer than `_MAX_PICO_FIELD_LENGTH`;
    returns `None` (never a partial or guessed question) if that is not
    met.
    """

    fields = (population, intervention, comparator, outcome)
    if any(not isinstance(field, str) or not field.strip() for field in fields):
        return None
    if any(len(field) > _MAX_PICO_FIELD_LENGTH for field in fields if isinstance(field, str)):
        return None
    assert isinstance(population, str)
    assert isinstance(intervention, str)
    assert isinstance(comparator, str)
    assert isinstance(outcome, str)

    return (
        f"In the following population, does the intervention affect the outcome, "
        f"compared with the comparator? "
        f"Population: {population.strip()} "
        f"Intervention: {intervention.strip()} "
        f"Comparator: {comparator.strip()} "
        f"Outcome: {outcome.strip()}"
    )


def classify_evidence_direction(claim_text: str) -> tuple[str, str | None]:
    """Classify `claim_text` into supports/contradicts/qualifies/contextualizes.

    Defaults to `supports` when no contrast/hedge/null cue fires -- see
    this module's docstring for why that default is safe here but was not
    in M18's `direction.py`.
    """

    for direction, patterns in _DIRECTION_PATTERN_GROUPS:
        for cue_name, pattern in patterns.items():
            if pattern.search(claim_text):
                return direction, cue_name
    return "supports", None


def build_automated_evidence_record(
    draft_item: dict[str, Any], *, created_for_milestone: str = "M52"
) -> dict[str, Any] | None:
    """Build a promotable Evidence Record dict from one draft item, or `None`.

    Returns `None` (never a partially filled record) when the draft item
    is missing `claim_text`/`result_summary`, or when
    `generate_research_question` declines to automate it. The returned
    dict is shaped for `ke extraction-review-promote`, which performs the
    actual schema validation -- this function does not duplicate that
    check, only fills the fields that otherwise stay empty (no human
    completion required).
    """

    claim_text = draft_item.get("claim_text")
    result_summary = draft_item.get("result_summary")
    if not isinstance(claim_text, str) or not claim_text.strip():
        return None
    if not isinstance(result_summary, str) or not result_summary.strip():
        return None

    research_question = generate_research_question(
        draft_item.get("population"),
        draft_item.get("intervention"),
        draft_item.get("comparator"),
        draft_item.get("outcome"),
    )
    if research_question is None:
        return None

    evidence_direction, matched_cue = classify_evidence_direction(claim_text)

    record = dict(draft_item)
    record["research_question"] = research_question
    record["evidence_direction"] = evidence_direction
    record["created_for_milestone"] = created_for_milestone
    record["extraction_method"] = EVIDENCE_CLASSIFICATION_RULES_VERSION
    record["review_status"] = "draft"
    record["review_checklist"] = {
        "automated_classification": True,
        "human_reviewed": False,
    }
    record["review_notes"] = (
        "Automatically classified by ke extraction-review-autoclassify (M52); "
        "no human read or confirmed research_question/evidence_direction for "
        f"this record. evidence_direction cue: {matched_cue or 'none (defaulted to supports)'}."
    )
    if not record.get("uncertainty_notes"):
        record["uncertainty_notes"] = (
            "research_question is a mechanical restatement of this record's own "
            "PICO fields, not a person's actual question. evidence_direction is a "
            "deterministic cue-pattern classification, defaulting to 'supports' "
            "when no contrast/hedge/null-result cue is present in claim_text."
        )
    if not record.get("confidence_note"):
        record["confidence_note"] = (
            "No confidence rating; this is an automated classification, not a "
            "human judgment of the source's methodological strength."
        )
    if not record.get("provenance"):
        record["provenance"] = {
            "created_by": f"Automated: {EVIDENCE_CLASSIFICATION_RULES_VERSION}",
            "review_notes": record["review_notes"],
        }
    return record
