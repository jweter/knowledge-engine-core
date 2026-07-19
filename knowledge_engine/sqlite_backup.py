"""Consistent SQLite snapshot and deterministic integrity manifest production."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

COUNTED_TABLES = ("papers", "sources", "import_runs")


class SQLiteBackupError(RuntimeError):
    """Sanitized SQLite backup failure."""


@dataclass(frozen=True)
class SQLiteBackupManifest:
    """Evidence describing one verified SQLite snapshot."""

    schema_version: int
    created_at: str
    production_commit: str
    filename: str
    byte_count: int
    sha256: str
    integrity_check: str
    table_counts: Mapping[str, int]

    def to_json_bytes(self) -> bytes:
        """Return stable UTF-8 JSON suitable for separate integrity storage."""

        return (json.dumps(asdict(self), sort_keys=True, indent=2) + "\n").encode()


def create_sqlite_backup(
    *,
    source_path: Path,
    snapshot_path: Path,
    production_commit: str,
    created_at: datetime | None = None,
) -> SQLiteBackupManifest:
    """Create an online SQLite snapshot and verify its durable contents."""

    if not source_path.is_file():
        raise SQLiteBackupError("SQLite source database does not exist.")
    if snapshot_path.exists() or snapshot_path == source_path:
        raise SQLiteBackupError("SQLite snapshot destination must be new and distinct.")
    if not production_commit or production_commit != production_commit.strip():
        raise SQLiteBackupError("Production commit must be an exact non-empty value.")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with sqlite3.connect(f"file:{source_path}?mode=ro", uri=True) as source:
            with sqlite3.connect(snapshot_path) as target:
                source.backup(target)
        manifest = inspect_sqlite_snapshot(
            snapshot_path=snapshot_path,
            production_commit=production_commit,
            created_at=created_at,
        )
    except (OSError, sqlite3.Error) as exc:
        snapshot_path.unlink(missing_ok=True)
        raise SQLiteBackupError("SQLite snapshot creation or verification failed.") from exc
    return manifest


def inspect_sqlite_snapshot(
    *,
    snapshot_path: Path,
    production_commit: str,
    created_at: datetime | None = None,
) -> SQLiteBackupManifest:
    """Verify a snapshot and derive its reproducible integrity evidence."""

    if not snapshot_path.is_file():
        raise SQLiteBackupError("SQLite snapshot does not exist.")
    try:
        payload = snapshot_path.read_bytes()
        with sqlite3.connect(f"file:{snapshot_path}?mode=ro", uri=True) as database:
            integrity_rows = database.execute("PRAGMA integrity_check").fetchall()
            integrity = "; ".join(str(row[0]) for row in integrity_rows)
            if integrity != "ok":
                raise SQLiteBackupError("SQLite snapshot failed integrity verification.")
            schema_version = int(database.execute("PRAGMA user_version").fetchone()[0])
            known_tables = {
                str(row[0])
                for row in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            counts = {
                table: int(database.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
                for table in COUNTED_TABLES
                if table in known_tables
            }
    except (OSError, sqlite3.Error) as exc:
        raise SQLiteBackupError("SQLite snapshot inspection failed.") from exc

    timestamp = created_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise SQLiteBackupError("Backup timestamp must be timezone-aware.")
    return SQLiteBackupManifest(
        schema_version=schema_version,
        created_at=timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        production_commit=production_commit,
        filename=snapshot_path.name,
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        integrity_check=integrity,
        table_counts=counts,
    )


def verify_restored_snapshot(*, snapshot_path: Path, manifest: SQLiteBackupManifest) -> None:
    """Reconcile a downloaded/restored snapshot against its recorded manifest."""

    observed = inspect_sqlite_snapshot(
        snapshot_path=snapshot_path,
        production_commit=manifest.production_commit,
        created_at=datetime.fromisoformat(manifest.created_at.replace("Z", "+00:00")),
    )
    if observed != manifest:
        raise SQLiteBackupError("Restored SQLite snapshot does not match its manifest.")
