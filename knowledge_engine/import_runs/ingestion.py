"""Application service for importing a validated local corpus."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from knowledge_engine.corpus.validation import (
    APPROVED_FULL_TEXT_STATUSES,
    _has_traversal,
    _is_relative_to,
    _looks_absolute,
    _resolve_under,
    discover_project_root,
)
from knowledge_engine.database import PaperRepository
from knowledge_engine.import_runs.repository import ImportRunRepository
from knowledge_engine.import_runs.service import ImportRunService
from knowledge_engine.models import ImportIssue, ImportItem, ImportRun, ManifestSnapshot
from knowledge_engine.parser import DocumentParser, PyMuPDFParser


@dataclass(frozen=True)
class ImportedCorpusRun:
    """Service result for one corpus import attempt."""

    import_run_id: str
    run_status: str
    imported_count: int
    failed_count: int
    skipped_count: int


@dataclass(frozen=True)
class _IssueTemplate:
    code: str
    message: str
    field: str | None = "local_path"


class _PapersDirectoryError(ValueError):
    """Persisted papers-directory metadata could not be resolved safely."""


class CorpusIngestionService:
    """Import local corpus files after persisting an M8 import run."""

    def __init__(
        self,
        session: Session,
        *,
        project_root: Path | None = None,
        parser: DocumentParser | None = None,
    ) -> None:
        self.session = session
        self.project_root = (project_root or discover_project_root()).resolve()
        self.parser = parser or PyMuPDFParser()
        self.repository = ImportRunRepository(session)
        self.run_service = ImportRunService(session, project_root=self.project_root)

    def import_corpus(self, corpus_path: Path) -> ImportedCorpusRun:
        """Validate, persist, and import a local corpus without downloading documents."""

        persisted = self.run_service.create_run(corpus_path, check_files=True)
        run = self.repository.get_run(persisted.import_run_id)
        if run is None:
            msg = "Import run was not readable after validation persistence."
            raise RuntimeError(msg)

        if run.manifest_validity != "valid" or run.import_readiness != "ready":
            run.completed_at = _utc_now()
            self.session.flush()
            return ImportedCorpusRun(
                import_run_id=run.import_run_id,
                run_status=run.run_status,
                imported_count=0,
                failed_count=0,
                skipped_count=len(run.items),
            )

        next_sequence = max((issue.sequence for issue in run.issues), default=0) + 1
        try:
            papers_dir = _papers_directory(run.manifest_snapshot, self.project_root)
        except _PapersDirectoryError:
            self._record_run_issue(
                run,
                next_sequence,
                _IssueTemplate(
                    code="persisted_papers_directory_invalid",
                    message="The persisted local papers directory could not be resolved safely.",
                    field="default_local_papers_directory",
                ),
            )
            run.run_status = "failed"
            run.completed_at = _utc_now()
            self.session.flush()
            return ImportedCorpusRun(
                import_run_id=run.import_run_id,
                run_status=run.run_status,
                imported_count=0,
                failed_count=0,
                skipped_count=len(run.items),
            )
        imported_count = 0
        failed_count = 0
        skipped_count = 0

        for item in run.items:
            item.completed_at = _utc_now()
            if not _should_import_item(item):
                item.item_status = "skipped"
                skipped_count += 1
                continue

            try:
                local_path = _resolve_item_path(papers_dir, item.local_path or "")
            except ValueError:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="declared_local_path_invalid",
                        message="The declared local file path could not be resolved safely.",
                    ),
                )
                continue

            try:
                parsed = self.parser.parse(local_path)
            except FileNotFoundError:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="local_file_missing_during_import",
                        message="The declared local file was missing when import started.",
                    ),
                )
                continue
            except OSError:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="local_file_unreadable",
                        message="The declared local file could not be read during import.",
                    ),
                )
                continue
            except Exception:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="paper_parse_failed",
                        message="The declared local file could not be parsed as a supported paper.",
                    ),
                )
                continue

            try:
                with self.session.begin_nested():
                    PaperRepository(self.session).add_parsed_paper(parsed)
            except ValueError:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="paper_already_imported",
                        message=(
                            "A paper with the same path, DOI, or content hash already exists."
                        ),
                    ),
                )
                continue
            except Exception:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="paper_persistence_failed",
                        message="The parsed paper could not be saved completely.",
                    ),
                )
                continue

            imported_count += 1
            item.item_status = "imported"

        run.run_status = _final_run_status(imported_count, failed_count)
        run.completed_at = _utc_now()
        self.session.flush()
        return ImportedCorpusRun(
            import_run_id=run.import_run_id,
            run_status=run.run_status,
            imported_count=imported_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
        )

    def _record_issue(
        self,
        run: ImportRun,
        item: ImportItem,
        sequence: int,
        template: _IssueTemplate,
    ) -> int:
        issue = ImportIssue(
            issue_id=_new_uuid(),
            import_run_id=run.import_run_id,
            import_item_id=item.import_item_id,
            code=template.code,
            severity="error",
            category="ingestion",
            message=template.message,
            source_id=item.source_id,
            field=template.field,
            csv_line_number=item.csv_line_number,
            blocks_manifest=False,
            blocks_import=True,
            sequence=sequence,
            created_at=_utc_now(),
        )
        self.repository.add_issues([issue])
        item.import_blocker_count += 1
        run.import_blocker_count += 1
        return sequence + 1

    def _record_run_issue(
        self,
        run: ImportRun,
        sequence: int,
        template: _IssueTemplate,
    ) -> int:
        issue = ImportIssue(
            issue_id=_new_uuid(),
            import_run_id=run.import_run_id,
            import_item_id=None,
            code=template.code,
            severity="error",
            category="ingestion",
            message=template.message,
            source_id=None,
            field=template.field,
            csv_line_number=None,
            blocks_manifest=False,
            blocks_import=True,
            sequence=sequence,
            created_at=_utc_now(),
        )
        self.repository.add_issues([issue])
        run.import_blocker_count += 1
        return sequence + 1


def _should_import_item(item: ImportItem) -> bool:
    return (
        not item.blocks_manifest
        and not item.blocks_import
        and item.inclusion_status == "included"
        and item.usage_status in APPROVED_FULL_TEXT_STATUSES
        and bool(item.local_path)
    )


def _papers_directory(snapshot: ManifestSnapshot, project_root: Path) -> Path:
    try:
        loaded = json.loads(snapshot.corpus_json_text)
    except json.JSONDecodeError as exc:
        raise _PapersDirectoryError("Persisted corpus snapshot is not valid JSON.") from exc
    if not isinstance(loaded, dict):
        msg = "Persisted corpus snapshot is not a JSON object."
        raise _PapersDirectoryError(msg)
    raw = loaded.get("default_local_papers_directory")
    if not isinstance(raw, str) or not raw.strip():
        msg = "Persisted corpus snapshot is missing default_local_papers_directory."
        raise _PapersDirectoryError(msg)
    path = Path(raw.strip())
    if _looks_absolute(path) or _has_traversal(path):
        msg = "Persisted default_local_papers_directory is not import-safe."
        raise _PapersDirectoryError(msg)
    try:
        resolved = _resolve_under(project_root, path)
    except OSError as exc:
        raise _PapersDirectoryError(
            "Persisted default_local_papers_directory could not be resolved."
        ) from exc
    if not _is_relative_to(resolved, project_root):
        msg = "Persisted default_local_papers_directory escapes the project root."
        raise _PapersDirectoryError(msg)
    return resolved


def _resolve_item_path(papers_dir: Path, local_path: str) -> Path:
    path = Path(local_path)
    if _looks_absolute(path) or _has_traversal(path):
        msg = "Persisted local_path is not import-safe."
        raise ValueError(msg)
    resolved = _resolve_under(papers_dir, path)
    if not _is_relative_to(resolved, papers_dir.resolve(strict=False)):
        msg = "Persisted local_path escapes the papers directory."
        raise ValueError(msg)
    return resolved


def _final_run_status(imported_count: int, failed_count: int) -> str:
    if failed_count and imported_count:
        return "partially_succeeded"
    if failed_count:
        return "failed"
    return "succeeded"


def _new_uuid() -> str:
    return str(uuid4())


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
