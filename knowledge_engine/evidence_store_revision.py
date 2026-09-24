from __future__ import annotations

import hashlib
from pathlib import Path


def evidence_store_revision(path: Path) -> str:
    """Return a deterministic content revision for an evidence JSONL store.

    Issue #433 requires a corpus/evidence-store revision suitable for cache
    invalidation. The identifier is content-derived rather than timestamp-
    derived so unchanged evidence remains reusable across copies/restarts.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
