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
- **mg/mcg/IU needed no additional context-word requirement.** After the
  concentration-denominator exclusion above, every remaining mg/mcg/IU
  occurrence across all three corpora was a genuine dose statement (e.g.
  "once-weekly semaglutide 2.4 mg", "liraglutide 1.8 mg", "INBRX-105 dose:
  0.3 mg/kg", "the dose was increased to 20 mg") -- unlike `duration.py`'s
  bare number+day/week/month/year, which collided extensively with ages and
  fixed timepoints even after unit selection, mg/mcg/IU is not otherwise
  used in this corpus for anything but an intervention dose once
  lab-concentration and lab-rate denominators are excluded.
- **mL is different: it is a genuinely ambiguous unit even after the same
  exclusion, so it needs its own context requirement.** A post-merge review
  finding (chatgpt-codex-connector, PR #481) pointed out that mL is commonly
  used in scientific/clinical writing for quantities that are not an
  intervention dose at all -- surgical blood loss, urine output, and
  specimen/sample volume ("Mean blood loss was 500 mL compared with 300 mL
  in controls") -- none of which happened to appear in the three checked-in
  corpora, but all of which are common enough in the broader medical
  literature this module must also handle correctly, per this project's
  "prefer missing data over invented metadata" standard (`AGENTS.md`). So,
  unlike mg/mcg/IU, a bare "<number> mL" is matched only when a dosing/
  administration-context word (dose/dosed/dosing, administer(ed), inject(ed)
  /injection, infuse(d)/infusion, receive(d)/receiving, oral(ly), suspension,
  solution, syrup, drops, or a dosing-frequency word like daily/once-daily/
  once-weekly/twice-daily/BID/QD/TID/QID) appears within the same short
  window before or after it -- e.g. "The oral suspension was dosed at 10 mL
  twice daily" matches, but "Mean blood loss was 500 mL" does not.

This module intentionally accepts under-matching a dose mention that uses an
unsupported unit (grams, "units" of insulin, drops, tablets), an mL dose with
no nearby administration-context word, or a dose stated with no accompanying
numeric value ("received the maximum tolerated dose") over risking a
fabricated dose label -- absence is still never guessed into a placeholder.
"""

from __future__ import annotations

import re

DOSE_EXTRACTION_RULES_VERSION = "m76-dose-v2"

_NUMBER = r"\d+(?:\.\d+)?"
_DOSE_UNIT = r"(?:mg|mcg|µg|μg|ug|IU|mL)"
_CONCENTRATION_OR_RATE_DENOMINATOR = r"(?:dl|l|mmol|nmol|pmol|mol|min)"

_DOSE_OCCURRENCE_PATTERN = re.compile(
    rf"\b{_NUMBER}\s*-?\s*{_DOSE_UNIT}\b(?!\s*/\s*{_CONCENTRATION_OR_RATE_DENOMINATOR}\b)",
    re.IGNORECASE,
)

_ADMINISTRATION_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:dos(?:e|es|ed|ing)|administ(?:er|ered|ering)|inject(?:ed|ion)?|"
    r"infus(?:ed|ion)|receiv(?:ed|ing)|oral(?:ly)?|suspension|solution|syrup|"
    r"drops|daily|once-daily|once-weekly|twice-daily|three-times-daily|"
    r"bid|qd|tid|qid)\b"
)
_CONTEXT_WINDOW_CHARS = 40


def _is_unsupported_ambiguous_volume(
    sentence_text: str, unit_text: str, start: int, end: int
) -> bool:
    """True when `unit_text` is an mL occurrence with no nearby dosing/
    administration-context word -- see the module docstring's mL bullet.

    Only mL needs this extra check: mg/mcg/IU were confirmed unambiguous
    (once lab-concentration/rate denominators are excluded) by manually
    reviewing every real-corpus occurrence, but mL has common non-dose
    scientific uses (blood loss, urine output, specimen volume) that never
    happened to appear in the checked corpora.
    """

    if not unit_text.strip().lower().endswith("ml"):
        return False

    before = sentence_text[max(0, start - _CONTEXT_WINDOW_CHARS) : start]
    after = sentence_text[end : end + _CONTEXT_WINDOW_CHARS]
    return not (
        _ADMINISTRATION_CONTEXT_PATTERN.search(before)
        or _ADMINISTRATION_CONTEXT_PATTERN.search(after)
    )


def extract_dose(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states an intervention dose,
    else `None`.

    Matches a number directly followed by a dose unit (mg/mcg/ug/IU/mL,
    optionally hyphenated, e.g. "2.4 mg", "0.3 mg/kg", "75 mg/m2") that is
    not immediately followed by a lab concentration or rate denominator
    ("/dL", "/L", "/mmol", "/nmol", "/pmol", "/mol", "/min"). An mL
    occurrence additionally requires a dosing/administration-context word
    within `_CONTEXT_WINDOW_CHARS` before or after it, since mL alone is
    ambiguous with non-dose volumes (blood loss, urine output, specimen
    volume); mg/mcg/IU need no such extra check. A bare gram unit is
    deliberately not supported at all; see the module docstring.
    """

    for match in _DOSE_OCCURRENCE_PATTERN.finditer(sentence_text):
        if _is_unsupported_ambiguous_volume(
            sentence_text, match.group(0), match.start(), match.end()
        ):
            continue
        return sentence_text
    return None


__all__ = [
    "DOSE_EXTRACTION_RULES_VERSION",
    "extract_dose",
]
