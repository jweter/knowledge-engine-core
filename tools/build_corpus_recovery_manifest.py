"""Build a deterministic recovery manifest from a Knowledge Engine SQLite corpus.

This utility does not download anything. It reads the existing ``papers`` table and
writes a JSONL recovery queue that can later drive bounded, legally compliant
re-acquisition of source PDFs.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

_PMC_FILENAME = re.compile(r"^(PMC\d+)\.pdf$", re.IGNORECASE)


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()
    return row is not None


def _target_path(target_dir: Path, source_path: str) -> Path:
    return target_dir / Path(source_path).name


def _route_for(source_path: str, doi: str | None) -> tuple[str, str | None]:
    filename = Path(source_path).name
    pmc_match = _PMC_FILENAME.match(filename)
    if pmc_match:
        return "pmc_open_access_candidate", pmc_match.group(1).upper()
    if doi:
        return "doi_open_access_resolution_required", None
    return "manual_source_resolution_required", None


def build_manifest(database: Path, target_dir: Path, output: Path) -> dict[str, Any]:
    if not database.is_file():
        raise FileNotFoundError(f"Database not found: {database}")

    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    try:
        if not _table_exists(connection, "papers"):
            raise RuntimeError("Database does not contain a papers table.")

        rows = connection.execute(
            """
            SELECT id, title, doi, source_path, content_hash, publication_year,
                   page_count, word_count, created_at, updated_at
            FROM papers
            ORDER BY id
            """
        ).fetchall()
    finally:
        connection.close()

    output.parent.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)

    hashes = Counter(str(row["content_hash"]) for row in rows)
    route_counts: Counter[str] = Counter()
    local_present = 0

    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            source_path = str(row["source_path"])
            doi = str(row["doi"]) if row["doi"] else None
            route, pmcid = _route_for(source_path, doi)
            route_counts[route] += 1

            target_path = _target_path(target_dir, source_path)
            is_present = target_path.is_file()
            if is_present:
                local_present += 1

            record = {
                "schema_version": 1,
                "paper_id": int(row["id"]),
                "title": str(row["title"]),
                "doi": doi,
                "pmcid": pmcid,
                "original_source_path": source_path,
                "expected_filename": Path(source_path).name,
                "expected_content_hash": str(row["content_hash"]),
                "publication_year": row["publication_year"],
                "page_count": int(row["page_count"]),
                "word_count": int(row["word_count"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "recovery_route": route,
                "local_target_path": target_path.as_posix(),
                "local_file_present": is_present,
                "duplicate_content_hash_in_database": hashes[str(row["content_hash"])] > 1,
                "recovery_status": "already_present" if is_present else "pending",
                "review_status": "not_reviewed",
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    summary = {
        "schema_version": 1,
        "database": database.as_posix(),
        "target_dir": target_dir.as_posix(),
        "manifest": output.as_posix(),
        "papers": len(rows),
        "local_present": local_present,
        "pending": len(rows) - local_present,
        "duplicate_hash_records": sum(count for count in hashes.values() if count > 1),
        "recovery_routes": dict(sorted(route_counts.items())),
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic PDF recovery manifest from a Knowledge Engine SQLite corpus."
        )
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary = build_manifest(args.database, args.target_dir, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
