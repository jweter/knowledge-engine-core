"""Deterministic study/intervention/follow-up duration extraction from one
claim's own sentence.

Issue #449 ("Research Report v1 support: structured evidence needed for
report-level auditability") names `duration` as a structured field report
consumers need but that no prior extraction module produced. This module is
the second slice of that gap, following `confidence_interval.py`'s exact
contract: match a sentence that states a duration and return that whole
sentence's text UNCHANGED -- never parse the number or unit into a separate
structured value. Like a confidence interval, a duration is a claim-level
fact, not a paper-level one (a study's overall duration, an individual
intervention's duration, and a follow-up-window duration mentioned in the
same paper are routinely different numbers), so this extracts per claim
candidate sentence, not once per paper.

Precision over recall: a grep of the three checked-in corpora's
`evidence_records.jsonl` files (~1,900 claim/result sentences across
glp1_weight_loss, mental_health_mdd_antidepressants, and
oncology_nsclc_checkpoint_inhibitors) found that a naive "number + day/week/
month/year unit" match is dominated by false positives that would be
fabricated/misleading metadata if labeled `duration`:

- **Ages, not durations.** "The median age was 69 years", "patients aged
  ≥65 years or older", "65-year-old participants" -- bare "N years" is
  overwhelmingly an age statement in this corpus, not a duration. Matching
  demanded an explicit duration-context word adjacent to the number, and a
  dedicated age guard (`age`/`aged` immediately before, or `-old`/`of age`
  immediately after the unit) that unconditionally disqualifies a candidate
  regardless of what other context surrounds it.
- **Survival/response timepoints, not durations.** "2-year OS", "5-year
  PFS rate", "60-month OS rate", "1- and 2-year OS rates" describe a
  standard oncology outcome measured *at* a fixed timepoint, not how long a
  study, intervention, or follow-up lasted. These use the identical
  hyphenated "N-unit" adjectival shape genuine durations do ("8-week
  trial", "24-week treatment period"), so the distinguishing signal has to
  be the noun immediately following, not the shape of the number itself.
  "OS"/"PFS"/"rate"/"survival"/"hazard"/"landmark"/"analysis"/"Cox"/"model"/
  "index"/"cohort" (a `landmark analysis`/`Cox model` at a fixed month/week
  is the same trap as "12-week landmark analysis including 323 patients",
  "12-week HR 1.23", "6-month PFS rate was 52.9%") are excluded from the
  filler words allowed between the number and a genuine duration noun, so
  they cannot be "bridged past" to reach an unrelated context word further
  away in the sentence.
- **Population/cohort descriptors bridging to an unrelated number.**
  "study"/"trial" is only real duration-context when it modifies the
  duration itself ("16-week study", "8-week ... trial"). Corpus text like
  "The median PFS in the study population was 2.5 months" and "The median
  age of the study population was 63 years" showed the opposite: "study"
  describing a population, with an unrelated number stated later in the
  same clause. "population"/"cohort"/"group"/"arm"/"participant(s)"/
  "patient(s)"/"subject(s)"/"sample" are excluded from the filler words for
  the same reason as the timepoint words above.
- **A measurement window anchored to a start event, not a duration.**
  "Mortality within 90 days of treatment start was 3.8%..." states a
  90-day assessment window measured *from* treatment start, not how long
  treatment itself lasted -- the word "treatment" is real duration context
  everywhere else, but not when directly followed by "start"/"onset"/
  "initiation"/"baseline"/"diagnosis"/"randomization", which mark it as an
  anchor point instead.
- **An unrelated word containing a duration word as a substring.** "platinum
  retreatment" contains the literal substring "treatment", which an
  unanchored context-word pattern (no `\\b` immediately before the
  alternation) matched inside "retreatment" itself, producing "The median OS
  for platinum retreatment ... was 27.2 months" as a false positive. Every
  context-word check requires a real word boundary immediately before the
  word, not just after it.
- **An age/eligibility threshold phrased with "over".** "over"/"for"/
  "during" are genuine duration-preposition cues ("for 4 weeks", "over the
  8-week follow-up", "during 52 weeks"), but "patients ... over 60 years"
  is an age threshold, not a duration, and "for the 5-year prediction of
  CVD" is a risk-prediction horizon, not a study/intervention/follow-up
  duration. Bare "year(s)" units (unlike day/week/month) are excluded from
  the standalone preposition-only match entirely -- a year-unit duration
  still matches, but only via the stricter context-word-adjacent checks
  below, which both real corpus false positives failed and every real
  corpus true positive (a "3-year follow-up", a "5-year duration of
  response") passed.
- **A treatment-relative measurement timepoint, not a duration.** "Blood
  pressure was measured 3 months after treatment" and "Symptoms were
  assessed 6 weeks before the intervention" are fixed timepoints stated
  relative to an event -- the same false-positive category as the
  anchor-event bullet above -- but "after"/"before"/"following" as filler
  between the number-unit and a genuine duration noun like "treatment"/
  "intervention" was not itself excluded, so it bridged past the temporal
  filler to reach the context word and matched. "after"/"before"/
  "following" are excluded from the trailing-context filler words for the
  same reason the anchor-event words and the survival/population filler
  words are: they mark the following noun as an anchor point in time, not
  something the number-unit is a duration *of*.

After these exclusions, a manual review of every one of the ~27 sentences
the final pattern matches across all three corpora confirmed each is a
genuine study/intervention/follow-up duration statement (e.g. "over the
8-week follow-up", "a 24-week treatment period", "a median duration of 10
months of treatment", "the median follow-up duration was 18.6 months", "at
both 1- and 3-year follow-up", "for 4 weeks" in an animal-model dosing
sentence). This module intentionally accepts under-matching real duration
mentions that lack one of these context cues (e.g. a bare "9.5 months" with
no adjacent marker) over risking a fabricated duration label -- absence is
still never guessed into a placeholder.
"""

from __future__ import annotations

import re

DURATION_EXTRACTION_RULES_VERSION = "m75-duration-v1"

_NUMBER = r"\d+(?:\.\d+)?"
_UNIT = r"(?:day|week|month|year)s?"
_PREPOSITION_ONLY_UNIT = r"(?:day|week|month)s?"  # "year" excluded: see module docstring
_UNIT_OCCURRENCE_PATTERN = re.compile(rf"(?i)\b{_NUMBER}\s*-?\s*{_UNIT}\b")
_PREPOSITION_UNIT_PATTERN = re.compile(rf"(?i)\A{_NUMBER}\s*-?\s*{_PREPOSITION_ONLY_UNIT}\Z")

_DURATION_CONTEXT_WORD = (
    r"(?:trial|study|period|treatment|follow-?up|intervention|"
    r"regimen|course|phase|pilot|program|protocol|duration)"
)
_NON_DURATION_FILLER_WORD = (
    r"(?:landmark|analysis|hazard|survival|response|endpoint|time\s?point|"
    r"visit|cox|model|index|cohort|population|group|arm|participant|patient|"
    r"subject|sample|hr|pfs|os|rate|after|before|following)"
)
_ANCHOR_EVENT_WORD = r"(?:start|onset|initiation|baseline|diagnosis|randomi[sz]ation)"

_FILLER_COMMA_TOLERANT = rf"(?:(?!{_NON_DURATION_FILLER_WORD}\b)[A-Za-z][\w/-]*[\s,]+){{0,4}}"
_FILLER_SAME_CLAUSE = rf"(?:(?!{_NON_DURATION_FILLER_WORD}\b)[A-Za-z][\w/-]*\s+){{0,3}}"

# A lead-in preposition immediately before the unit: "for 4 weeks", "over the
# 8-week follow-up", "during 52 weeks". Comma-tolerant filler is deliberately
# not allowed here, keeping this direction to what real corpus text uses.
_PREPOSITION_BEFORE_PATTERN = re.compile(
    r"(?i)\b(?:over|for|during|lasted|administered\s+for|continued\s+for)\s*"
    r"(?:a|an|the|mean|median)?\s*\Z"
)

# A duration noun following a hyphenated adjectival unit, comma-tolerant so a
# list of intervening adjectives is still matched: "8-week, multicentre,
# double-blind, randomized, controlled trial".
_TRAILING_CONTEXT_AFTER_HYPHENATED_UNIT = re.compile(
    rf"(?i)\A\s*,?\s*{_FILLER_COMMA_TOLERANT}"
    rf"\b{_DURATION_CONTEXT_WORD}\b(?!\s+{_ANCHOR_EVENT_WORD}\b)"
)

# A duration noun following a bare (non-hyphenated) unit -- kept to the same
# clause (no comma tolerance) so "aged ≥60 years, treatment with ..." (an
# unrelated clause after an age mention) is not bridged into a false match.
_TRAILING_CONTEXT_AFTER_BARE_UNIT = re.compile(
    rf"(?i)\A\s+{_FILLER_SAME_CLAUSE}"
    rf"\b{_DURATION_CONTEXT_WORD}\b(?!\s+{_ANCHOR_EVENT_WORD}\b)"
)

# A duration noun/word (including the literal word "duration" itself)
# preceding the unit: "follow-up duration was >=6 months", "a median
# duration of 10 months of treatment", "the median follow-up was 50 months".
_LEADING_CONTEXT_BEFORE_UNIT_PATTERN = re.compile(
    rf"(?i)\b{_DURATION_CONTEXT_WORD}\b[\s,]*"
    rf"{_FILLER_COMMA_TOLERANT}"
    rf"(?:of\s+|was\s+|is\s+|were\s+)*(?:>=|<=|≥|≤)?\s*\Z"
)

_AGE_BEFORE_PATTERN = re.compile(r"(?i)\bage[ds]?\s*(?:of)?\s*[:=≥≤<>]*\s*\Z")
_AGE_AFTER_PATTERN = re.compile(r"(?i)\A\s*(?:-\s*old\b|\bold\b|of\s+age\b)")

_CONTEXT_WINDOW_CHARS = 40


def _is_age_mention(sentence_text: str, start: int, end: int) -> bool:
    """True when the unit occurrence at [start, end) is an age, not a duration.

    Guards both "aged 65 years"/"age of 65 years" (context before the unit)
    and "65-year-old"/"65 years of age" (context after it), regardless of
    which duration pattern the occurrence would otherwise satisfy.
    """

    before = sentence_text[max(0, start - _CONTEXT_WINDOW_CHARS) : start]
    after = sentence_text[end : end + _CONTEXT_WINDOW_CHARS]
    return bool(_AGE_BEFORE_PATTERN.search(before) or _AGE_AFTER_PATTERN.match(after))


def extract_duration(sentence_text: str) -> str | None:
    """Return `sentence_text` unchanged when it states a duration, else `None`.

    Scans every "number + day/week/month/year" occurrence in the sentence
    and accepts the sentence as soon as one occurrence is confirmed to be a
    genuine study/intervention/follow-up duration mention by one of three
    checks, in order: (1) an immediately preceding lead-in preposition
    ("for 4 weeks", "during 52 weeks"; bare "year" units are excluded here,
    see module docstring), (2) a duration noun immediately following
    ("24-week treatment period", "16-week study"), or (3) a duration noun
    (including the literal word "duration") immediately preceding
    ("follow-up duration was 18.6 months"). An occurrence recognized as an
    age mention by `_is_age_mention` is always skipped, regardless of
    which of the three checks would otherwise have matched it.
    """

    for match in _UNIT_OCCURRENCE_PATTERN.finditer(sentence_text):
        start, end = match.start(), match.end()
        if _is_age_mention(sentence_text, start, end):
            continue

        unit_text = match.group(0)
        before_text = sentence_text[:start]
        after_text = sentence_text[end:]

        if _PREPOSITION_UNIT_PATTERN.match(unit_text) and _PREPOSITION_BEFORE_PATTERN.search(
            before_text
        ):
            return sentence_text

        if "-" in unit_text:
            if _TRAILING_CONTEXT_AFTER_HYPHENATED_UNIT.match(after_text):
                return sentence_text
        elif _TRAILING_CONTEXT_AFTER_BARE_UNIT.match(after_text):
            return sentence_text

        if _LEADING_CONTEXT_BEFORE_UNIT_PATTERN.search(before_text):
            return sentence_text

    return None


__all__ = [
    "DURATION_EXTRACTION_RULES_VERSION",
    "extract_duration",
]
