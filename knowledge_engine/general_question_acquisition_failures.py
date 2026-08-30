"""Durable per-batch failure records for General Question acquisition routes.

CORE-GQR-4 requires that a resolver/download/parsing failure on any of the
four acquisition routes (PMC, Europe PMC, CORE, Unpaywall) leave an auditable,
retryable trace rather than only stderr/console output. This module gives all
four command implementations one shared, sanitized failure-record shape and a
single derived location to write and read it from.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from knowledge_engine.import_runs._helpers import utc_now

FAILURE_RECORD_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class GeneralQuestionAcquisitionFailureRecord:
    """Sanitized, durable trace of one failed acquisition batch.

    ``reason`` is always a message from one of this project's own sanitized
    acquisition error classes (never a raw exception/traceback), matching the
    same sanitization boundary already used for successful receipts.
    """

    schema_version: int
    search_run_id: str
    research_question_id: str
    acquisition_route: str
    stage: str
    reason: str
    candidate_ids: tuple[str, ...]
    occurred_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def failure_record_path(receipt_path: Path) -> Path:
    """Return the durable failure-record path derived from a receipt path.

    Kept alongside, never inside, the persistence receipt path so a prior
    failure trace and a successful receipt can never be confused for one
    another.
    """

    return receipt_path.with_name(receipt_path.name + ".failure.json")


def write_acquisition_failure_record(
    receipt_path: Path,
    *,
    search_run_id: str,
    research_question_id: str,
    acquisition_route: str,
    stage: str,
    reason: str,
    candidate_ids: tuple[str, ...],
) -> Path:
    """Persist a sanitized failure record next to ``receipt_path``.

    Written via a temporary file plus an atomic ``os.replace`` so a reader
    never observes a truncated record, and so a pre-existing symbolic link at
    the failure-record path is replaced outright rather than followed and
    written through (``os.replace``/``rename`` retargets the directory entry
    itself; it does not dereference a destination symlink).

    Best-effort: an ``OSError`` while writing the failure record itself is
    swallowed so it never masks or replaces the original error the caller is
    already raising.
    """

    record = GeneralQuestionAcquisitionFailureRecord(
        schema_version=FAILURE_RECORD_SCHEMA_VERSION,
        search_run_id=search_run_id,
        research_question_id=research_question_id,
        acquisition_route=acquisition_route,
        stage=stage,
        reason=reason,
        candidate_ids=candidate_ids,
        occurred_at=utc_now(),
    )
    path = failure_record_path(receipt_path)
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(record.to_json())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except OSError:
            with contextlib.suppress(OSError):
                os.unlink(temp_name)
            raise
    return path


def clear_acquisition_failure_record(receipt_path: Path) -> None:
    """Remove a stale failure record left by an earlier failed attempt.

    Called after a batch succeeds so a retried run at the same receipt path
    does not leave a failure trace next to its own successful receipt.
    """

    with contextlib.suppress(OSError):
        failure_record_path(receipt_path).unlink(missing_ok=True)


__all__ = [
    "FAILURE_RECORD_SCHEMA_VERSION",
    "GeneralQuestionAcquisitionFailureRecord",
    "clear_acquisition_failure_record",
    "failure_record_path",
    "write_acquisition_failure_record",
]
