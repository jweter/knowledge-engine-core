"""Deterministic intervention-dose extraction from one claim's own sentence.

Issue #449 ("Research Report v1 support: structured evidence needed for
report-level auditability") names `dose` as a structured field report
consumers need but that no prior extraction module produced. This is the
third slice of that gap (after `confidence_interval.py`/M74 and
`duration.py`/M75), following the identical contract: match a sentence that
states an intervention dose and return that whole sentence's text UNCHANGED
-- never parse the numeric value or unit into a separate structured value.
Like a confidence interval or a duration, a dose is a claim-level fact, not a
paper-level one (a dose-escalation study routinely states several different
doses for the same intervention within one paper), so this extracts per
claim-candidate sentence, not once per paper.

Precision over recall: grepping the three checked-in corpora's
`evidence_records.jsonl` files (~1,900 claim/result sentences across
glp1_weight_loss, mental_health_mdd_antidepressants, and
oncology_nsclc_checkpoint_inhibitors) for a naive "number + dose-shaped unit"
match found it dominated by false positives that would be fabricated/
misleading metadata if labeled `dose`:

- **Lab concentration values, not doses.** "125.0 mg/dL" (triglycerides),
  "0.90 mg/dL" (bilirubin), "31.0 IU/L" (ALT/AST), "4.7 g/dL" (albumin) all
  share a unit prefix (mg/IU/g) with a genuine dose but are measured
  concentrations, distinguished only by the denominator after the slash.
  Every dose unit this module matches is rejected when immediately followed
  by a concentration-per-volume-or-substance denominator ("/dL", "/L",
  "/mmol", "/nmol", "/pmol", "/mol") or a rate denominator ("/min", as in
  "mL/min" creatinine clearance) -- but NOT "/kg" or "/m2"/"/m²" or "/day"/
  "/week", which are themselves standard per-weight/per-body-surface-area/
  per-time dosing units ("0.3 mg/kg", "75 mg/m2 every 3 weeks").
- **The bare gram unit is not supported at all.** Unlike mg/mcg/IU/mL, a
  bare "g" collides with two unrelated corpus shapes that also put a
  single-letter suffix directly after a number with no separating space:
  figure/panel references ("Fig. 2G", "Figures 1G-J", "(Figure 4G)") and,
  separately, effect-size units that are also stated in grams ("mean
  difference was -3.37 g"). Excluding bare "g" entirely -- keeping only
  mg/mcg/ug/IU/mL, none of which collide with a figure-reference or
  effect-size shape in the checked corpora -- was simpler and safer than
  trying to disambiguate a zero-space "<number>G" figure suffix from a
  genuine "<number> g" dose, especially since no real corpus dose statement
  was lost by dropping bare grams (dose amounts in this corpus are stated in
  mg, not g).
- **A number-unit pairing alone, with no intervention-dose context, is not
  enough for `g`-adjacent ambiguity, but mg/mcg/IU/mL did not need an
  additional context-word requirement.** After the concentration-denominator
  exclusion above, every remaining mg/mcg/IU/mL occurrence across all three
  corpora was a genuine dose statement (e.g. "once-weekly semaglutide 2.4
  mg", "liraglutide 1.8 mg", "INBRX-105 dose: 0.3 mg/kg", "the dose was
  increased to 20 mg", "a dose of 14 mg of oral semaglutide") -- unlike
  `duration.py`'s bare number+day/week/month/year, which collided
  extensively with ages and fixed timepoints even after unit selection,
  mg/mcg/IU/mL is not otherwise used in this corpus for anything but an
  intervention dose once lab-concentration and lab-rate denominators are
  excluded, so no further context-word filter was needed to stay precise.

This module intentionally accepts under-matching a dose mention that uses an
unsupported unit (grams, "units" of insulin, drops, tablets) or that states a
dose with no accompanying numeric value ("received the maximum tolerated
dose") over risking a fabricated dose label -- absence is still never guessed
into a placeholder.
"""

from __future__ import annotations

import re

DOSE_EXTRACTION_RULES_VERSION = "m76-dose-v1"

_NUMBER = r"\d+(?:\.\d+)?"
_DOSE_UNIT = r"(?:mg|mcg|µg|μg|ug|IU|mL)"
_CONCENTRATION_OR_RATE_DENOMINATOR = r"(?:dl|l|mmol|nmol|pmol|mol|min)"

_DOSE_PATTERN = re.compile(
    rf"\b{_NUMBER}\s*-?\s*{_DOSE_UNIT}\b(?!\s*/\s*{_CONCENTRATION_OR_RATE_DENOMINATOR}\b)",
    re.IGNORECASE,
)


def extract_dose(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states an intervention dose,
    else `None`.

    Matches a number directly followed by a dose unit (mg/mcg/ug/IU/mL,
    optionally hyphenated, e.g. "2.4 mg", "0.3 mg/kg", "75 mg/m2") that is
    not immediately followed by a lab concentration or rate denominator
    ("/dL", "/L", "/mmol", "/nmol", "/pmol", "/mol", "/min"). A bare gram
    unit is deliberately not supported; see the module docstring.
    """

    if _DOSE_PATTERN.search(sentence_text):
        return sentence_text
    return None


__all__ = [
    "DOSE_EXTRACTION_RULES_VERSION",
    "extract_dose",
]
