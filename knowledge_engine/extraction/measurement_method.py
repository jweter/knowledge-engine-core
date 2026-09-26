"""Deterministic measurement-method extraction from one claim sentence.

Research Report v1 issue #449 requires measurement method when it is explicitly
extractable. This follows the same conservative contract as the adjacent
confidence-interval, duration, dose, and effect-size extractors: return the
claim sentence unchanged when it explicitly links a measurement cue to a
recognized clinical or laboratory method; otherwise return None.

v2 paired a measurement cue ("measured by", "assessed by", ...) with a method
keyword found *anywhere later in the sentence* via an unbounded
`re.search(sentence_text, cue.end())`. Grepping the three checked-in corpora's
`evidence_records.jsonl` files (~3,600 claim/result sentences) for that exact
v2 pattern found it dominated by a bridging false positive: a cue attached to
an unrelated statistical-test name ("p values were measured by one-way ANOVA
with Tukey's multiple comparison test") reaches past that test name, the rest
of that sentence, and often an unrelated following sentence, to a genuine
method keyword mentioned much later for a completely different purpose (e.g.
"... underwent Positron Emission [Tomography]/Computed Tomography", "...
across the three simulated transcriptomic platforms (... RT-qPCR)") -- the
same "bridge past an unrelated clause" mistake `duration.py`/`dose.py` already
guard against for their own context words. Of the seven distinct real-corpus
sentences the v2 pattern matched, five were this bridging shape; the two
genuine matches ("... PD-L1 positivity was assessed by IHC using the SP263
antibody", "... analyzed using HPLC") both have the method keyword directly
adjacent to the cue, with no intervening clause.

v3 requires the method keyword to appear within the same clause as the cue:
the search window stops at the first clause/sentence boundary
(`.`/`;`/`:`/`!`/`?`/a parenthesis/a bracket) after the cue, or a generous
character cap, whichever comes first, and every intervening word up to that
boundary must be a plain word token (never itself crossing a boundary). A
first version of this fix capped the intervening words at a fixed count of
two, which correctly excluded every bridging false positive below but also
rejected genuine same-clause qualifier chains longer than two words (e.g.
"measured using a commercially available ELISA kit" -- a real Codex review
finding on this PR, verified against that exact sentence). Bounding by
clause instead of word count admits an arbitrarily long qualifier chain
while still excluding every corpus bridging shape, because each one crosses
either a sentence boundary (a period) or into an unrelated parenthetical
before reaching its unrelated method keyword -- never within the same
comma-only clause the cue itself is in. Checks every cue occurrence in the
sentence, not only the first, so a sentence with a bare cue-without-method
("evaluated by H-Score") followed later by a genuine cue-with-method
("assessed by IHC") still matches on its own second cue.
"""

from __future__ import annotations

import re

MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION = "m78-measurement-method-v4"

_MEASUREMENT_CUE = re.compile(
    r"\b(?:measured|assessed|evaluated|determined|quantified|analyzed|analysed)"
    r"\s+(?:by|using|with|via)\s+",
    re.IGNORECASE,
)

_METHOD_ALTERNATION = (
    r"immunohistochemistry|IHC|"
    r"qRT-PCR|RT-qPCR|quantitative reverse transcription PCR|"
    r"ELISA|enzyme-linked immunosorbent assay|"
    r"flow cytometry|"
    r"high-performance liquid chromatography|HPLC|"
    r"mass spectrometry|"
    r"magnetic resonance imaging|MRI|"
    r"computed tomography|CT|"
    r"HbA1c|hemoglobin A1c|"
    r"HAM-D|Hamilton Depression Rating Scale|"
    r"RECIST|"
    r"sphygmomanometer|"
    r"automated oscillometric(?: device| monitor)?|"
    r"oscillometric(?: device| monitor| measurement)?|"
    r"ambulatory blood pressure monitoring|ABPM|"
    r"home blood pressure monitoring|HBPM"
)

# A method keyword must be reached from the cue without crossing a
# clause/sentence boundary -- not merely present somewhere later in the
# sentence. `_SKIP_WORD` deliberately excludes sentence-ending punctuation
# (it must be immediately followed by whitespace, never a period or comma)
# so a skipped word can never itself cross a boundary; `_CLAUSE_BOUNDARY`
# additionally truncates the search window at the first boundary character
# after the cue, so an unrelated method keyword past that boundary is never
# reached regardless of word count. The character cap is a generous,
# independent safety net for a degenerate boundary-free run, not the
# primary guard -- see module docstring.
_CLAUSE_BOUNDARY = re.compile(r"[.;:!?()\[\]]")
_METHOD_WINDOW_CHARS = 100
_SKIP_WORD = r"[A-Za-z0-9][\w-]*,?\s+"
_METHOD_ANCHORED = re.compile(
    rf"^(?:{_SKIP_WORD})*(?:{_METHOD_ALTERNATION})\b",
    re.IGNORECASE,
)


def extract_measurement_method(sentence_text: str) -> str | None:
    """Return the unchanged sentence when it explicitly states a method."""
    for cue in _MEASUREMENT_CUE.finditer(sentence_text):
        char_cap = cue.end() + _METHOD_WINDOW_CHARS
        boundary = _CLAUSE_BOUNDARY.search(sentence_text, cue.end())
        window_end = min(char_cap, boundary.start()) if boundary else char_cap
        window = sentence_text[cue.end() : window_end]
        if _METHOD_ANCHORED.match(window):
            return sentence_text
    return None


__all__ = [
    "MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION",
    "extract_measurement_method",
]
