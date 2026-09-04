"""Deterministic medication-dose extraction from one claim's own sentence.

Issue #449 requires a structured dose field for Research Report v1 auditability.
This module follows the existing confidence-interval and duration contract:
when a claim sentence explicitly states a medication/intervention dose, return
that sentence unchanged. Never parse a numeric dose into a new value and never
guess a dose from context.

Precision is intentionally favored over recall. The detector recognizes common
mass-dose units only when the sentence also carries administration/treatment
context, comparator context, or an adjacent dosing frequency. Laboratory
concentrations such as mg/dL or mg/L are explicitly excluded.
"""

from __future__ import annotations

import re

DOSE_EXTRACTION_RULES_VERSION = "m76-dose-v1"

_AMOUNT = r"\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?"
_UNIT = r"(?:ng|mcg|ug|µg|μg|mg|g)(?:\s*/\s*(?:kg|day|week))?"
_EXPLICIT_CONTEXT = re.compile(
    rf"""(?ix)
    \b(?:dose(?:d|s|ing)?|administered|received|treated\s+with|
       randomized\s+to|randomised\s+to|assigned\s+to|
       intervention|regimen|therapy|treatment)
    \b[^.;:]{{0,80}}?
    {_AMOUNT}\s*{_UNIT}\b
    """
)
_ADJACENT_DRUG_WITH_DOSE_SIGNAL = re.compile(
    rf"""(?ix)
    \b[A-Za-z][A-Za-z0-9-]{{2,}}\s+
    {_AMOUNT}\s*{_UNIT}\b
    [^.;:]{{0,48}}?
    (?:\bonce\b|\bdaily\b|\bweekly\b|\bevery\b|
       \bper\s+day\b|\bper\s+week\b|
       \bor\s+placebo\b|\bvs\.?\s+placebo\b|\bversus\s+placebo\b)
    """
)
_LAB_CONCENTRATION = re.compile(
    rf"""(?ix)
    {_AMOUNT}\s*(?:ng|mcg|ug|µg|μg|mg|g)
    \s*(?:/|per\s+)(?:dL|L|mL)\b
    """
)


def extract_dose(sentence_text: str) -> str | None:
    """Return the unchanged sentence when it conservatively states a dose."""

    if _LAB_CONCENTRATION.search(sentence_text):
        return None
    if _EXPLICIT_CONTEXT.search(sentence_text) or _ADJACENT_DRUG_WITH_DOSE_SIGNAL.search(
        sentence_text
    ):
        return sentence_text
    return None


__all__ = ["DOSE_EXTRACTION_RULES_VERSION", "extract_dose"]
