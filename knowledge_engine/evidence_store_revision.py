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


def _validated_evidence_records(path: Path) -> tuple[dict[str, Any], ...]:
    """Use Core's authoritative Evidence Record validator for JSONL revision input."""
    if not path.exists():
        return ()

    # Imported lazily to avoid a module cycle: cli imports promotion commands that
    # consume this helper, while the validator itself remains Core's authority.
    import knowledge_engine.cli as cli

    seen_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        errors: list[str] = []
        cli._validate_evidence_record(
            record, 0, seen_ids, errors, require_review_fields=True
        )
        if not errors:
            records.append(record)
    return tuple(records)


def evidence_store_revision(
    path: Path,
    *,
    valid_records: Callable[[Path], Iterable[dict[str, Any]]] | None = None,
) -> str:
    """Return a deterministic revision for the store's usable evidence.

    Callers may supply their authoritative validator/duplicate filter. When
    omitted, Core's Evidence Record validator is used directly, so malformed
    or duplicate JSONL never becomes cache-visible.
    """
    validator = valid_records or _validated_evidence_records
    return evidence_records_revision(validator(path))
