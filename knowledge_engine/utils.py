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
