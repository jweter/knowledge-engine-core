"""Deterministic measurement-method extraction from one claim sentence.

Research Report v1 issue #449 requires measurement method when it is explicitly
extractable. This follows the same conservative contract as the adjacent
confidence-interval, duration, dose, and effect-size extractors: return the
claim sentence unchanged when it explicitly links a measurement cue to a
recognized clinical or laboratory method; otherwise return None.
"""

from __future__ import annotations

import re

MEASUREMENT_METHOD_EXTRACTION_RULES_VERSION = "m78-measurement-method-v1"

_MEASUREMENT_CUE = re.compile(
    r"\b(?:measured|assessed|evaluated|determined|quantified|analyzed|analysed)"
    r"\s+(?:by|using|with|via)\s+",
    re.IGNORECASE,
)

_METHOD = re.compile(
    r"\b(?:"
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
    r"RECIST"
    r")\b",
    re.IGNORECASE,
)


def extract_measurement_method(sentence_text: str) -> str | None:
    """Return the unchanged sentence when it explicitly states a method."""
    cue = _MEASUREMENT_CUE.search(sentence_text)
    if cue is None:
        return None
    if _METHOD.search(sentence_text, cue.end()) is None:
        return None
    return sentence_text
