"""Split the working SQLite corpus database into git-committable chunks.

`data/*.sqlite3` is gitignored: it is large, environment-specific, and has
historically been treated as regenerable from `ke corpus-import` plus the
M14 discovery/acquisition pipeline. In practice a full local ingestion pass
(download PDFs, extract, fill the database) takes real time and real
provider traffic to reproduce, and two artifacts it holds -- the full-text
search index and any computed embeddings -- are not captured by the lighter
`ke corpus-library-export` snapshot (see `knowledge_engine/corpus_library.py`,
which deliberately persists only paper-intrinsic content) or by the
already-git-tracked `evidence_records.jsonl`/`relationship_records.jsonl`
files. This tool commits the database itself, split into parts small enough
to stay well under GitHub's 100MB single-file push limit.

This utility never mutates the source database. It always backs it up first
through SQLite's online backup API (`knowledge_engine.sqlite_backup`), the
same verified-snapshot mechanism the Google Drive backup pilot uses, so a
concurrently open connection or WAL state can never produce a corrupt or
torn chunk set.

Output layout, written to `--output-dir` (default `data/db_parts`):

    manifest.json                          -- see below
    knowledge_engine.sqlite3.part0000
    knowledge_engine.sqlite3.part0001
    ...

`manifest.json` records the whole-file SHA-256 and byte count, each part's
filename/byte count/SHA-256, and the same integrity evidence
`create_sqlite_backup` already produces (SQLite `PRAGMA integrity_check`,
schema version, and row counts for `papers`/`sources`/`import_runs`), so
`reassemble_corpus_database.py` can verify a full round trip without ever
trusting file size alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from knowledge_engine.sqlite_backup import SQLiteBackupManifest, create_sqlite_backup

DEFAULT_PART_SIZE_BYTES = 90_000_000
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_FILENAME = "manifest.json"


class SplitError(RuntimeError):
    """One sanitized database-split failure."""


@dataclass(frozen=True)
class PartRecord:
    filename: str
    byte_count: int
    sha256: str


@dataclass(frozen=True)
class SplitManifest:
    schema_version: int
    source_filename: str
    total_byte_count: int
    total_sha256: str
    part_size_bytes: int
    part_count: int
    parts: tuple[PartRecord, ...]
    backup: SQLiteBackupManifest

    def to_json_bytes(self) -> bytes:
        payload = {
            "schema_version": self.schema_version,
            "source_filename": self.source_filename,
            "total_byte_count": self.total_byte_count,
            "total_sha256": self.total_sha256,
            "part_size_bytes": self.part_size_bytes,
            "part_count": self.part_count,
            "parts": [asdict(part) for part in self.parts],
            "backup": asdict(self.backup),
        }
        return (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()


def _part_filename(source_filename: str, index: int) -> str:
    return f"{source_filename}.part{index:04d}"


def _chunk(payload: bytes, part_size_bytes: int) -> list[bytes]:
    """Split payload into fixed-size chunks, always returning at least one."""

    if not payload:
        return [b""]
    return [
        payload[offset : offset + part_size_bytes]
        for offset in range(0, len(payload), part_size_bytes)
    ]


def split_database(
    *,
    database: Path,
    output_dir: Path,
    production_commit: str,
    part_size_bytes: int = DEFAULT_PART_SIZE_BYTES,
) -> SplitManifest:
    if part_size_bytes < 1:
        raise SplitError("part_size_bytes must be positive.")
    if not database.is_file():
        raise SplitError(f"Database not found: {database}")

    with tempfile.TemporaryDirectory(prefix="split-corpus-database-") as raw_temp_dir:
        temp_dir = Path(raw_temp_dir)
        snapshot_path = temp_dir / database.name
        backup = create_sqlite_backup(
            source_path=database,
            snapshot_path=snapshot_path,
            production_commit=production_commit,
        )

        payload = snapshot_path.read_bytes()
        total_sha256 = hashlib.sha256(payload).hexdigest()
        if total_sha256 != backup.sha256 or len(payload) != backup.byte_count:
            raise SplitError("Snapshot bytes changed between backup and split.")

        chunks = _chunk(payload, part_size_bytes)
        parts = [
            PartRecord(
                filename=_part_filename(database.name, index),
                byte_count=len(chunk),
                sha256=hashlib.sha256(chunk).hexdigest(),
            )
            for index, chunk in enumerate(chunks)
        ]

        manifest = SplitManifest(
            schema_version=MANIFEST_SCHEMA_VERSION,
            source_filename=database.name,
            total_byte_count=len(payload),
            total_sha256=total_sha256,
            part_size_bytes=part_size_bytes,
            part_count=len(parts),
            parts=tuple(parts),
            backup=backup,
        )

        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True)
        try:
            for part, chunk in zip(parts, chunks, strict=True):
                (output_dir / part.filename).write_bytes(chunk)
            (output_dir / MANIFEST_FILENAME).write_bytes(manifest.to_json_bytes())
        except OSError:
            shutil.rmtree(output_dir, ignore_errors=True)
            raise

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/db_parts"))
    parser.add_argument(
        "--production-commit",
        required=True,
        help=(
            "Git commit SHA (or another exact non-empty label) recording "
            "what state produced this split."
        ),
    )
    parser.add_argument("--part-size-bytes", type=int, default=DEFAULT_PART_SIZE_BYTES)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = split_database(
        database=args.database,
        output_dir=args.output_dir,
        production_commit=args.production_commit,
        part_size_bytes=args.part_size_bytes,
    )
    print(
        json.dumps(
            {
                "output_dir": args.output_dir.as_posix(),
                "part_count": manifest.part_count,
                "total_byte_count": manifest.total_byte_count,
                "total_sha256": manifest.total_sha256,
                "created_at": manifest.backup.created_at,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"\nWrote {manifest.part_count} part(s) to {args.output_dir}. "
        f"Next: git add {args.output_dir}/* && git commit && git push."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
