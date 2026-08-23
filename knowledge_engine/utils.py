"""Small utility helpers used across the application."""

import re
from hashlib import sha256
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Return a SHA-256 digest for a file."""

    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_words(text: str) -> int:
    """Count natural-language-ish words in text."""

    return len(re.findall(r"\b[\w'-]+\b", text))


def normalize_whitespace(text: str) -> str:
    """Collapse repeated whitespace while preserving paragraph boundaries lightly."""

    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    compact_lines = [line for line in lines if line]
    return "\n\n".join(compact_lines)


def normalize_doi(doi: str) -> str:
    """Normalize a DOI for deterministic comparison."""

    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def normalize_pmid(pmid: str) -> str:
    """Normalize a PubMed ID for deterministic comparison.

    Provider APIs return PMIDs as plain digit strings, so only whitespace
    trimming is needed today; this exists as its own function (rather than
    comparing raw strings) so a future provider-specific quirk has one place
    to be handled without touching every caller.
    """

    return pmid.strip()


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Normalize an arXiv identifier for deterministic comparison.

    Strips a leading ``arXiv:`` prefix (case-insensitive) and a trailing
    version suffix (``v2``) so the same work is recognized regardless of
    which version a provider happened to report.
    """

    normalized = arxiv_id.strip()
    if normalized.lower().startswith("arxiv:"):
        normalized = normalized[len("arxiv:") :]
    normalized = re.sub(r"v\d+$", "", normalized)
    return normalized.strip().lower()
