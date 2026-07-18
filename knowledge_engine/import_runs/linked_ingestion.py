"""Execution of immutable linked resume and retry corpus runs."""

from __future__ import annotations

from pathlib import Path

from knowledge_engine.database import PaperRepository
from knowledge_engine.duplicate_resolution import (
    DuplicateResolutionError,
    resolve_duplicate_before_persistence,
)
from knowledge_engine.import_runs._helpers import utc_now
from knowledge_engine.import_runs.ingestion import (
    CorpusIngestionService,
    ImportedCorpusRun,
    UnsafePersistedPathError,
    _final_review_status,
    _final_run_status,
    _IssueTemplate,
    _mark_unimported_items_skipped,
    _papers_directory,
    _PapersDirectoryError,
    _resolve_item_path,
    _result_from_run,
    _should_import_item,
)
from knowledge_engine.import_runs.linked import LinkedImportRunService
from knowledge_engine.import_runs.resume import RunMode
from knowledge_engine.parser import DocumentParseError


class LinkedCorpusIngestionService(CorpusIngestionService):
    """Execute a new immutable run linked to one prior import attempt."""

    def import_linked_corpus(
        self,
        corpus_path: Path,
        *,
        parent_import_run_id: str,
        mode: RunMode,
    ) -> ImportedCorpusRun:
        """Create and execute one explicit resume or retry-failed run."""

        persisted = LinkedImportRunService(
            self.session,
            project_root=self.project_root,
        ).create_linked_run(
            corpus_path,
            parent_import_run_id=parent_import_run_id,
            mode=mode,
            check_files=True,
        )
        run = self.repository.get_run(persisted.import_run_id)
        if run is None:
            raise RuntimeError("Linked import run was not readable after persistence.")

        if run.manifest_validity != "valid" or run.import_readiness != "ready":
            skipped_count = _mark_unimported_items_skipped(run)
            run.completed_at = utc_now()
            self.session.flush()
            return _result_from_run(
                run,
                imported_count=0,
                failed_count=0,
                skipped_count=skipped_count,
            )

        next_sequence = max((issue.sequence for issue in run.issues), default=0) + 1
        try:
            papers_dir = _papers_directory(run.manifest_snapshot, self.project_root)
        except _PapersDirectoryError:
            skipped_count = _mark_unimported_items_skipped(run)
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
            run.completed_at = utc_now()
            self.session.flush()
            return _result_from_run(
                run,
                imported_count=0,
                failed_count=0,
                skipped_count=skipped_count,
            )

        imported_count = 0
        failed_count = 0
        skipped_count = 0
        needs_review_count = 0

        for item in run.items:
            item.completed_at = utc_now()
            if item.item_status != "valid":
                skipped_count += 1
                continue
            if not _should_import_item(item):
                item.item_status = "skipped"
                skipped_count += 1
                continue

            try:
                local_path = _resolve_item_path(papers_dir, item.local_path or "")
            except UnsafePersistedPathError:
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
            except DocumentParseError:
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
                decision = resolve_duplicate_before_persistence(
                    self.session,
                    item=item,
                    parsed=parsed,
                )
            except DuplicateResolutionError:
                failed_count += 1
                item.item_status = "failed"
                next_sequence = self._record_issue(
                    run,
                    item,
                    next_sequence,
                    _IssueTemplate(
                        code="duplicate_resolution_failed",
                        message="Duplicate identity evidence could not be resolved safely.",
                    ),
                )
                continue

            item.item_status = decision.item_status
            if decision.item_status == "skipped":
                skipped_count += 1
                continue
            if decision.item_status == "needs_review":
                needs_review_count += 1
                continue

            try:
                with self.session.begin_nested():
                    paper = PaperRepository(self.session).add_parsed_paper(parsed)
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
            item.matched_paper_id = paper.id

        final_run_status = _final_run_status(imported_count, failed_count)
        final_review_status = _final_review_status(needs_review_count)
        run.run_status = final_run_status.value
        run.review_status = final_review_status.value
        run.completed_at = utc_now()
        self.session.flush()
        return ImportedCorpusRun(
            import_run_id=run.import_run_id,
            run_status=final_run_status,
            imported_count=imported_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            needs_review_count=needs_review_count,
            review_status=final_review_status,
        )
