"""Deterministic effect-size extraction from one claim's own sentence.

Issue #449 ("Research Report v1 support: structured evidence needed for
report-level auditability") names "effect size and confidence interval when
extractable" as structured fields report consumers need. `confidence_interval.py`
(M74) covered the interval; this module is the fourth slice of that same gap
(after `confidence_interval.py`/M74, `duration.py`/M75, and `dose.py`/M76),
following the identical contract: match a sentence that states an effect size
and return that whole sentence's text UNCHANGED -- never parse the numeric
value into a separate structured value. An effect size is a claim-level fact,
not a paper-level one (a paper routinely reports a primary endpoint's hazard
ratio and a secondary endpoint's odds ratio as two different numbers), so this
extracts per claim-candidate sentence, not once per paper.

Unlike a confidence interval, an effect size is stated in several
incompatible shapes with different units (an odds/hazard/risk ratio or
relative risk is a unitless multiplicative factor; a mean difference is in
the outcome's own units and can be negative) -- the "quote, never parse"
contract sidesteps that heterogeneity entirely: this module never normalizes
or compares values across shapes, it only detects that *one of the known
shapes* is present.

Precision over recall: grepping the three checked-in corpora's
`evidence_records.jsonl` files (~1,900 claim/result sentences across
glp1_weight_loss, mental_health_mdd_antidepressants, and
oncology_nsclc_checkpoint_inhibitors) for the abbreviations and full phrases
below found two dominant false-positive shapes that would be fabricated/
misleading metadata if labeled `effect_size`:

- **The bare word "or" is not the odds-ratio abbreviation.** A
  case-insensitive match on "OR" hits the ordinary English conjunction
  throughout the corpus ("accuracy ... or reaction time"). Every abbreviation
  (OR/RR/HR/SMD/WMD/IRR) is matched case-sensitively -- real papers do not
  write the conjunction in all caps, and every abbreviation occurrence
  actually meaning an effect measure in the checked corpora was capitalized.
- **A confidence-interval percentage is not the effect-size value.** A column
  header or inline parenthetical like "HR (95% CI)" states which two
  quantities a table reports, not a value; naive "abbreviation followed by a
  number" matching picks up the "95" from "95% CI" as if it were the HR
  itself. Any candidate number immediately followed by "%" is rejected.
- **A statistic that happens to follow the phrase by way of an unrelated
  noun is not the effect-size value.** "Forest plot of relative risk for
  grade 3/4 TRAE in patients ..." has no risk-ratio value in the sentence at
  all; the "3" in "grade 3/4" is not it. The full-phrase pattern only
  accepts a small, explicit set of connectors directly before the number
  (a parenthetical abbreviation, "was"/"were"/"of", ":"/"="/",", or direct
  adjacency) -- an arbitrary intervening clause like "for grade" is not
  bridged past, matching `duration.py`'s established filler-word discipline.

After these exclusions, a manual review of a random sample of the sentences
matched across all three corpora confirmed each states a genuine effect size
(e.g. "hazard ratio [HR] = 0.29", "odds ratio 2.36, 95% CI [1.0, 5.6]",
"pooled RR = 1.86, 95% CI: 1.50-...", "the pooled mean difference was -4.36
cm"). This module intentionally accepts under-matching a real effect-size
mention with no adjacent connector it recognizes (e.g. "hazard ratio (HR) for
death was 0.51", where "for death" sits between the abbreviation and "was")
over risking a fabricated effect-size label -- absence is still never guessed
into a placeholder.
"""

from __future__ import annotations

import re

EFFECT_SIZE_EXTRACTION_RULES_VERSION = "m-effect-size-v1"

_SIGNED_NUMBER = r"[-−]?\d+(?:\.\d+)?"

# Case-sensitive: real papers do not capitalize the English conjunction "or",
# so an all-caps abbreviation match does not collide with it. See module
# docstring.
_RATIO_ABBREVIATION_PATTERN = re.compile(r"\b(?:OR|RR|HR|SMD|WMD|IRR)\b")
_ABBREVIATION_CONNECTOR_PATTERN = re.compile(
    r"^\s*(?:adj(?:usted)?\s+)?(?:[:=,]\s*|of\s+)?[\[(]?"
    rf"({_SIGNED_NUMBER})"
)

_RATIO_PHRASE_PATTERN = re.compile(
    r"(?:hazard ratio|odds ratio|risk ratio|relative risk|"
    r"standardized mean difference|weighted mean difference|mean difference)",
    re.IGNORECASE,
)
_PHRASE_CONNECTOR_PATTERN = re.compile(
    r"^\s*(?:[\[(](?:HR|OR|RR|MD|SMD|WMD)[\])]\s*)?"
    r"(?:(?:was|were|of)\s+|[:=,]\s*)?"
    rf"({_SIGNED_NUMBER})"
)

_CONNECTOR_WINDOW_CHARS = 25


def _is_confidence_interval_percentage(window: str, number_end: int) -> bool:
    """True when the number just matched at `window[:number_end]` is actually
    a confidence-interval percentage (e.g. the "95" in "HR (95% CI)"), not
    the effect-size value itself.

    Checked as a plain string lookup after the match, not a regex negative
    lookahead: a lookahead placed right after a greedy `\\d+` lets the engine
    backtrack to a shorter digit run that dodges the lookahead (matching "9"
    instead of "95" so the "%" no longer immediately follows), silently
    accepting the exact shape this guards against.
    """

    return window[number_end : number_end + 2].lstrip().startswith("%")


def _has_abbreviation_effect_size(sentence_text: str) -> bool:
    for match in _RATIO_ABBREVIATION_PATTERN.finditer(sentence_text):
        window = sentence_text[match.end() : match.end() + _CONNECTOR_WINDOW_CHARS]
        connector_match = _ABBREVIATION_CONNECTOR_PATTERN.match(window)
        if connector_match and not _is_confidence_interval_percentage(
            window, connector_match.end(1)
        ):
            return True
    return False


def _has_phrase_effect_size(sentence_text: str) -> bool:
    for match in _RATIO_PHRASE_PATTERN.finditer(sentence_text):
        window = sentence_text[match.end() : match.end() + _CONNECTOR_WINDOW_CHARS]
        connector_match = _PHRASE_CONNECTOR_PATTERN.match(window)
        if connector_match and not _is_confidence_interval_percentage(
            window, connector_match.end(1)
        ):
            return True
    return False


def extract_effect_size(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states an effect size, else `None`.

    Matches either a case-sensitive ratio abbreviation (OR/RR/HR/SMD/WMD/IRR,
    optionally qualified by "adj"/"adjusted") or a full effect-measure phrase
    ("hazard ratio", "odds ratio", "risk ratio", "relative risk", "mean
    difference" and its standardized/weighted variants, optionally followed
    by a parenthetical abbreviation), each immediately followed -- allowing
    only a small set of real-corpus connectors ("=", ":", ",", "of", "was",
    "were", or direct adjacency) -- by a signed number that is not itself a
    confidence-interval percentage. See the module docstring for the
    false-positive shapes this excludes.
    """

    if _has_abbreviation_effect_size(sentence_text):
        return sentence_text
    if _has_phrase_effect_size(sentence_text):
        return sentence_text
    return None


__all__ = [
    "EFFECT_SIZE_EXTRACTION_RULES_VERSION",
    "extract_effect_size",
]
