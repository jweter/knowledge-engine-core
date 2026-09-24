from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable


def evidence_records_revision(records: Iterable[dict[str, Any]]) -> str:
    """Return the canonical revision used for usable Evidence Records."""
    digest = hashlib.sha256()
    for record in records:
        canonical = json.dumps(
            record, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        digest.update(len(canonical).to_bytes(8, "big"))
        digest.update(canonical)
    return digest.hexdigest()


def evidence_store_revision(
    path: Path,
    *,
    valid_records: Callable[[Path], Iterable[dict[str, Any]]],
) -> str:
    """Return a deterministic revision for the store's usable evidence.

    The caller supplies its authoritative validator/duplicate filter so this
    helper cannot accidentally make malformed or duplicate JSONL cache-visible.
    """
    return evidence_records_revision(valid_records(path))
