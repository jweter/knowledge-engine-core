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

v3 requires the method keyword to appear within a short, bounded window
immediately after the cue -- allowing at most two short intervening words
(e.g. "using 24-hour ambulatory blood pressure monitoring", "with a
validated sphygmomanometer") rather than an arbitrary later clause -- and
checks every cue occurrence in the sentence rather than only the first, so a
sentence with a bare cue-without-method ("evaluated by H-Score") followed
later by a genuine cue-with-method ("assessed by IHC") still matches on its
own second cue, without falling back to the unbounded bridge the first cue
would otherwise need. A skipped word may not itself run past a sentence
boundary (it must be immediately followed by whitespace, not a period, so
"test." never counts as one of the two skippable words), which is why every
bridging shape found above -- each separated from its method keyword by a
full clause or sentence -- stays excluded.
"""

from __future__ import annotations

import re

MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION = "m78-measurement-method-v3"

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

# A method keyword must be one of the next two words after the cue, not
# merely present somewhere later in the sentence -- see module docstring.
# `_SKIP_WORD` deliberately excludes sentence-ending punctuation (it must be
# immediately followed by whitespace, never a period) so a skipped word can
# never carry the match across a clause/sentence boundary. The window is
# also bounded in characters (not an unbounded re.search) as a second,
# independent guard against bridging past an unrelated clause.
_METHOD_WINDOW_CHARS = 70
_SKIP_WORD = r"[A-Za-z0-9][\w-]*,?\s+"
_METHOD_ANCHORED = re.compile(
    rf"^(?:{_SKIP_WORD}){{0,2}}(?:{_METHOD_ALTERNATION})\b",
    re.IGNORECASE,
)


def extract_measurement_method(sentence_text: str) -> str | None:
    """Return the unchanged sentence when it explicitly states a method."""
    for cue in _MEASUREMENT_CUE.finditer(sentence_text):
        window = sentence_text[cue.end() : cue.end() + _METHOD_WINDOW_CHARS]
        if _METHOD_ANCHORED.match(window):
            return sentence_text
    return None


__all__ = [
    "MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION",
    "extract_measurement_method",
]
