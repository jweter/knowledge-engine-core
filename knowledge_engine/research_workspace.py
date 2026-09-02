"""Deterministic bootstrap for a persistent hosted Research workspace."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import import_corpus_library
from knowledge_engine.database import Database
from knowledge_engine.models import Paper


@dataclass(frozen=True)
class ResearchWorkspaceBootstrapSummary:
    """Result of seeding or reconciling one persistent Research workspace."""

    workspace_dir: Path
    database_path: Path
    evidence_path: Path
    imported_paper_count: int
    skipped_existing_paper_count: int
    imported_evidence_record_count: int
    skipped_existing_evidence_record_count: int
    total_paper_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        payload = asdict(self)
        payload["workspace_dir"] = str(self.workspace_dir)
        payload["database_path"] = str(self.database_path)
        payload["evidence_path"] = str(self.evidence_path)
        return payload


def _import_snapshot_with_schema_compatibility(
    *,
    target_session: Any,
    snapshot_path: Path,
    evidence_output_path: Path,
) -> Any:
    """Import a compressed corpus snapshot after migrating a temporary copy.

    Corpus-library snapshots intentionally omit the working database's schema
    version history. A committed snapshot can therefore predate a later
    additive model column even though the application importing it is current.
    Migrating only the decompressed temporary copy keeps the committed seed
    immutable while allowing the normal import path to select the current ORM
    model safely. The temporary database is discarded after the import.
    """

    with tempfile.TemporaryDirectory() as raw_dir:
        raw_root = Path(raw_dir)
        raw_path = raw_root / "snapshot.sqlite3"
        with gzip.open(snapshot_path, "rb") as compressed_file, raw_path.open("wb") as raw_file:
            shutil.copyfileobj(compressed_file, raw_file)

        snapshot_database = Database(
            Settings(
                project_root=raw_root,
                data_dir=raw_root,
                database_url=f"sqlite:///{raw_path}",
            )
        )
        try:
            snapshot_database.initialize()
        finally:
            snapshot_database.engine.dispose()

        return import_corpus_library(target_session, raw_path, evidence_output_path)


def bootstrap_research_workspace(
    *,
    workspace_dir: Path,
    snapshot_path: Path,
    evidence_path: Path | None = None,
) -> ResearchWorkspaceBootstrapSummary:
    """Initialize a writable Core workspace and seed it from a corpus snapshot.

    Import is intentionally idempotent: existing papers are matched by content
    hash and existing EvidenceRecords by evidence_record_id, so the same
    persistent volume can be reconciled on every deploy without replacing
    newly acquired state.
    """

    if not snapshot_path.is_file():
        msg = f"Research workspace snapshot does not exist: {snapshot_path}"
        raise FileNotFoundError(msg)

    workspace_dir.mkdir(parents=True, exist_ok=True)
    database_path = workspace_dir / "knowledge_engine.sqlite3"
    resolved_evidence_path = evidence_path or workspace_dir / "evidence_records.jsonl"
    resolved_evidence_path.parent.mkdir(parents=True, exist_ok=True)

    database = Database(
        Settings(
            project_root=workspace_dir.parent,
            data_dir=workspace_dir,
            database_url=f"sqlite:///{database_path}",
        )
    )
    try:
        database.initialize()
        with database.session() as session:
            imported = _import_snapshot_with_schema_compatibility(
                target_session=session,
                snapshot_path=snapshot_path,
                evidence_output_path=resolved_evidence_path,
            )
            total_paper_count = int(session.scalar(select(func.count()).select_from(Paper)) or 0)

        # Downstream evidence commands accept an empty JSONL file. Creating it
        # here keeps a newly bootstrapped workspace structurally complete even
        # when an older public snapshot carries no embedded EvidenceRecords.
        resolved_evidence_path.touch(exist_ok=True)

        return ResearchWorkspaceBootstrapSummary(
            workspace_dir=workspace_dir,
            database_path=database_path,
            evidence_path=resolved_evidence_path,
            imported_paper_count=imported.imported_paper_count,
            skipped_existing_paper_count=imported.skipped_existing_paper_count,
            imported_evidence_record_count=imported.imported_evidence_record_count,
            skipped_existing_evidence_record_count=imported.skipped_existing_evidence_record_count,
            total_paper_count=total_paper_count,
        )
    finally:
        database.engine.dispose()


def main() -> None:
    """CLI entry point for hosted deployment bootstrap."""

    parser = argparse.ArgumentParser(
        description="Initialize or reconcile a persistent Knowledge Engine Research workspace."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="Persistent writable directory that will hold the Core database and evidence JSONL.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Committed/public corpus-library snapshot (*.sqlite3.gz) used as the seed.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        default=None,
        help="Optional evidence JSONL path; defaults inside --workspace.",
    )
    args = parser.parse_args()

    summary = bootstrap_research_workspace(
        workspace_dir=args.workspace,
        snapshot_path=args.snapshot,
        evidence_path=args.evidence,
    )
    print(json.dumps(summary.to_dict(), sort_keys=True))


if __name__ == "__main__":
    main()
