"""CLI adapter tests for immutable resume and retry corpus imports."""

from pathlib import Path

import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.import_runs.ingestion import ImportedCorpusRun
from knowledge_engine.import_runs.statuses import ReviewStatus, RunStatus
from tests.test_cli import write_cli_corpus


def test_corpus_import_rejects_conflicting_parent_options(tmp_path: Path) -> None:
    corpus_path = write_cli_corpus(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "corpus-import",
            str(corpus_path),
            "--resume-from",
            "run-one",
            "--retry-failed-from",
            "run-two",
        ],
    )

    assert result.exit_code == 2
    assert "mutually exclusive" in result.output
    assert not (tmp_path / "data" / "knowledge_engine.sqlite3").exists()


@pytest.mark.parametrize(
    ("option", "expected_mode"),
    [
        ("--resume-from", "resume"),
        ("--retry-failed-from", "retry_failed"),
    ],
)
def test_corpus_import_routes_linked_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    option: str,
    expected_mode: str,
) -> None:
    corpus_path = write_cli_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, str]] = []

    class StubLinkedCorpusIngestionService:
        def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
            self.session = session
            self.project_root = project_root or tmp_path

        def import_linked_corpus(
            self,
            path: Path,
            *,
            parent_import_run_id: str,
            mode: str,
        ) -> ImportedCorpusRun:
            calls.append((parent_import_run_id, mode))
            persisted = ImportRunService(self.session, project_root=self.project_root).create_run(
                path, check_files=True
            )
            run = ImportRunService(self.session, project_root=self.project_root).get_run(
                persisted.import_run_id
            )
            assert run is not None
            run.run_mode = mode
            run.parent_import_run_id = parent_import_run_id
            run.run_status = "succeeded"
            run.items[0].item_status = "skipped"
            self.session.flush()
            return ImportedCorpusRun(
                import_run_id=run.import_run_id,
                run_status=RunStatus.SUCCEEDED,
                imported_count=0,
                failed_count=0,
                skipped_count=1,
                needs_review_count=0,
                review_status=ReviewStatus.CLEAR,
            )

    monkeypatch.setattr(
        cli,
        "LinkedCorpusIngestionService",
        StubLinkedCorpusIngestionService,
    )

    result = CliRunner().invoke(
        app,
        ["corpus-import", str(corpus_path), option, " parent-run "],
    )

    assert result.exit_code == 0
    assert calls == [("parent-run", expected_mode)]
    assert "Corpus import finished" in result.output
    assert "Skipped items: 1" in result.output
