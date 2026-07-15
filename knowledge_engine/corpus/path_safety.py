"""Stable path-safety helpers shared by corpus validation and ingestion."""

from __future__ import annotations

import re
from pathlib import Path

WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def has_traversal(path: Path) -> bool:
    """Return whether the path contains parent-directory traversal."""

    return any(part == ".." for part in path.parts)


def looks_absolute(path: Path) -> bool:
    """Return whether the path should be treated as absolute."""

    raw = str(path)
    return path.is_absolute() or raw.startswith(("/", "\\")) or bool(WINDOWS_DRIVE_RE.match(raw))


def resolve_under(base: Path, path: Path) -> Path:
    """Resolve a child path while tolerating missing final targets."""

    candidate = base / path
    try:
        return candidate.resolve(strict=True)
    except FileNotFoundError:
        return candidate.resolve(strict=False)


def is_relative_to(path: Path, base: Path) -> bool:
    """Return whether path stays within the given base path."""

    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


__all__ = ["has_traversal", "is_relative_to", "looks_absolute", "resolve_under"]
