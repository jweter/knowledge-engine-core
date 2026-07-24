"""Deterministic reusable-license evidence check, shared across discovery sources.

Originally part of `knowledge_engine.candidate_review` (M14's PubMed/PMC
adjudication engine). Extracted so a second discovery pipeline -- Europe PMC
(M34), and any future source -- applies the identical license-acceptance
criteria rather than a copy that can drift out of sync; getting a
license-restriction rule wrong is a real correctness/compliance risk, not
just style duplication.
"""

from __future__ import annotations

import re

ALLOWED_LICENSE_PATTERN = re.compile(r"^(?:CC BY(?: (?:1\.0|2\.0|2\.5|3\.0|4\.0))?|CC0(?: 1\.0)?)$")
"""Matches only unrestricted licenses: exactly "CC BY" or "CC0", optionally
followed by one of their real published version numbers (CC BY: 1.0, 2.0, 2.5,
3.0, or 4.0; CC0: only 1.0 exists). Deliberately does not match "CC BY-NC",
"CC BY-NC-ND", "CC BY-NC-SA", or "CC BY-SA" - those restrict commercial use
and/or derivative works, which conflicts with this project's extraction and
redistribution of derived evidence records (Phase 2). The version allowlist
(rather than a loose `[0-9.]*` pattern) also ensures a version that passes
here always has a real Creative Commons deed URL - see `license_deed_url`."""


def evaluate_license(reported_license: str | None) -> str:
    """Return a license-evidence result: "passed", "incomplete_missing_license",
    or "unsupported_license_basis"."""

    if reported_license is None:
        return "incomplete_missing_license"
    normalized = " ".join(reported_license.upper().split())
    if ALLOWED_LICENSE_PATTERN.fullmatch(normalized):
        return "passed"
    return "unsupported_license_basis"


def license_deed_url(license_type: str) -> str:
    """Canonical Creative Commons deed URL for an allowed license string.

    Raises ValueError if `license_type` does not match `ALLOWED_LICENSE_PATTERN`,
    so callers only ever reuse this single source of truth for what counts as
    an unrestricted license, rather than re-deriving license semantics.
    """

    normalized = " ".join(license_type.upper().split())
    if not ALLOWED_LICENSE_PATTERN.fullmatch(normalized):
        raise ValueError(f"Unsupported license type: {license_type!r}")
    parts = normalized.split(" ")
    if parts[0] == "CC0":
        version = parts[1] if len(parts) > 1 else "1.0"
        return f"https://creativecommons.org/publicdomain/zero/{version}/"
    version = parts[2] if len(parts) > 2 else "4.0"
    return f"https://creativecommons.org/licenses/by/{version}/"
