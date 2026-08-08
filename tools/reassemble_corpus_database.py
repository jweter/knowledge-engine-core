"""Reassemble a chunked SQLite corpus database from `split_corpus_database.py` output.

Reads `manifest.json` from `--parts-dir`, concatenates the referenced part
files in order, verifies the result against every piece of evidence the
manifest records (each part's byte count and SHA-256, the whole file's byte
count and SHA-256, and the source database's own SQLite integrity check via
`knowledge_engine.sqlite_backup.verify_restored_snapshot`), and only then
commits the reassembled bytes to `--output`. A mismatch at any step leaves
`--output` untouched and exits non-zero -- this tool never writes a database
it cannot fully verify.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from knowledge_engine.sqlite_backup import SQLiteBackupManifest, verify_restored_snapshot

MANIFEST_FILENAME = "manifest.json"


class ReassembleError(RuntimeError):
    """One sanitized database-reassembly failure."""


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


def _load_manifest(parts_dir: Path) -> SplitManifest:
    manifest_path = parts_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ReassembleError(f"Manifest not found: {manifest_path}")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReassembleError("Manifest is not valid JSON.") from exc

    try:
        parts = tuple(
            PartRecord(
                filename=str(part["filename"]),
                byte_count=int(part["byte_count"]),
                sha256=str(part["sha256"]),
            )
            for part in raw["parts"]
        )
        backup = SQLiteBackupManifest(
            schema_version=int(raw["backup"]["schema_version"]),
            created_at=str(raw["backup"]["created_at"]),
            production_commit=str(raw["backup"]["production_commit"]),
            filename=str(raw["backup"]["filename"]),
            byte_count=int(raw["backup"]["byte_count"]),
            sha256=str(raw["backup"]["sha256"]),
            integrity_check=str(raw["backup"]["integrity_check"]),
            table_counts=dict(raw["backup"]["table_counts"]),
        )
        return SplitManifest(
            schema_version=int(raw["schema_version"]),
            source_filename=str(raw["source_filename"]),
            total_byte_count=int(raw["total_byte_count"]),
            total_sha256=str(raw["total_sha256"]),
            part_size_bytes=int(raw["part_size_bytes"]),
            part_count=int(raw["part_count"]),
            parts=parts,
            backup=backup,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReassembleError("Manifest is missing required fields.") from exc


def reassemble_database(*, parts_dir: Path, output: Path, overwrite: bool = False) -> SplitManifest:
    if not parts_dir.is_dir():
        raise ReassembleError(f"Parts directory not found: {parts_dir}")
    manifest = _load_manifest(parts_dir)
    if len(manifest.parts) != manifest.part_count:
        raise ReassembleError("Manifest part_count does not match its own parts list.")

    if output.exists() and not overwrite:
        existing = output.read_bytes()
        if hashlib.sha256(existing).hexdigest() == manifest.total_sha256:
            raise ReassembleError(
                f"{output} already matches the manifest; nothing to do. "
                "Pass --overwrite to force a rewrite anyway."
            )
        raise ReassembleError(
            f"{output} already exists and does not match the manifest. "
            "Pass --overwrite only after reviewing the existing file."
        )

    chunks: list[bytes] = []
    for part in manifest.parts:
        part_path = parts_dir / part.filename
        if not part_path.is_file():
            raise ReassembleError(f"Missing part file: {part_path}")
        chunk = part_path.read_bytes()
        if len(chunk) != part.byte_count:
            raise ReassembleError(
                f"Part {part.filename} has byte count {len(chunk)}, expected {part.byte_count}."
            )
        if hashlib.sha256(chunk).hexdigest() != part.sha256:
            raise ReassembleError(f"Part {part.filename} failed SHA-256 verification.")
        chunks.append(chunk)

    payload = b"".join(chunks)
    if len(payload) != manifest.total_byte_count:
        raise ReassembleError(
            f"Reassembled byte count {len(payload)} does not match "
            f"manifest total {manifest.total_byte_count}."
        )
    if hashlib.sha256(payload).hexdigest() != manifest.total_sha256:
        raise ReassembleError("Reassembled bytes failed whole-file SHA-256 verification.")

    output.parent.mkdir(parents=True, exist_ok=True)
    # verify_restored_snapshot compares the full manifest, including filename,
    # so the staged file must be named exactly as it was when split_corpus_database.py
    # backed it up (manifest.backup.filename) -- not a `.tmp`-suffixed name.
    try:
        with tempfile.TemporaryDirectory(
            prefix="reassemble-corpus-database-", dir=output.parent
        ) as raw_staging_dir:
            staged = Path(raw_staging_dir) / manifest.backup.filename
            staged.write_bytes(payload)
            verify_restored_snapshot(snapshot_path=staged, manifest=manifest.backup)
            os.replace(staged, output)
    except OSError as exc:
        raise ReassembleError(
            f"Reassembled database could not be committed: {exc.__class__.__name__}"
        ) from exc

    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", type=Path, default=Path("data/db_parts"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing --output file that does not already match the manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = reassemble_database(
        parts_dir=args.parts_dir, output=args.output, overwrite=args.overwrite
    )
    print(
        json.dumps(
            {
                "output": args.output.as_posix(),
                "part_count": manifest.part_count,
                "total_byte_count": manifest.total_byte_count,
                "total_sha256": manifest.total_sha256,
                "sqlite_integrity_check": manifest.backup.integrity_check,
                "table_counts": manifest.backup.table_counts,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(f"\nReassembled and verified {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
