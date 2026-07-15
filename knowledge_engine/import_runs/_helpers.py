"""Internal helpers shared by import-run services."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def new_uuid() -> str:
    """Return a new UUID4 string."""

    return str(uuid4())


def utc_now() -> str:
    """Return the current UTC timestamp in persisted import-run format."""

    return datetime.now(UTC).isoformat(timespec="seconds")
