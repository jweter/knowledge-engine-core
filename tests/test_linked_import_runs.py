from pathlib import Path

import pytest
from sqlalchemy import func, select

from knowledge_engine.database import Database
from knowledge_engine.import_runs.linked import LinkedImportRunService
from knowledge_engine.import_runs.service import ImportRunService
from knowledge_engine.models import ImportRun
from tests.corpus_fixtures import get_run, make_database
from tests.test_corpus_import import make_corpus, source_row


def _set_parent_outcomes(database: Database, run_id: str) -> dict[str, str]:
    with database.session() as session:
        run = ImportRunService(session, project_root=database.settings.project_root).get_run(run_id)
        assert run is not None
        items = {item.source_id: item for item in run.items}
        success = items["source-success"]
        failure = items["source-failed"]
        success.item_status = "imported"
        success.matched_paper_id = None
        failure.item_status = "failed"
        session.flush()
        return {
            "success": success.import_item_id,
            "failed": failure.import_item_id,
        }


def test_resume_creates_linked_run_without_mutating_parent(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-success", local_path="success.pdf"),
            source_row(source_id="source-failed", local_path="failed.pdf"),
        ],
    )
    with database.session() as session:
        parent = ImportRunService(session, project_root=tmp_path).create_run(corpus_path)
    parent_ids = _set_parent_outcomes(database, parent.import_run_id)

    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-new", local_path="new.pdf"),
            source_row(source_id="source-failed", local_path="failed.pdf"),
            source_row(source_id="source-success", local_path="success.pdf"),
        ],
    )
    with database.session() as session:
        linked = LinkedImportRunService(session, project_root=tmp_path).create_linked_run(
            corpus_path,
            parent_import_run_id=parent.import_run_id,
            mode="resume",
        )

    parent_run = get_run(database, parent.import_run_id)
    linked_run = get_run(database, linked.import_run_id)
    linked_items = {item.source_id: item for item in linked_run.items}

    assert linked_run.import_run_id != parent_run.import_run_id
    assert linked_run.parent_import_run_id == parent_run.import_run_id
    assert linked_run.run_mode == "resume"
    assert linked_items["source-success"].item_status == "skipped"
    assert linked_items["source-success"].matched_import_item_id == parent_ids["success"]
    assert linked_items["source-failed"].item_status == "skipped"
    assert linked_items["source-failed"].matched_import_item_id == parent_ids["failed"]
    assert linked_items["source-new"].item_status == "valid"
    assert {item.source_id: item.item_status for item in parent_run.items} == {
        "source-success": "imported",
        "source-failed": "failed",
    }


def test_retry_failed_links_only_failed_parent_item(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(source_id="source-success", local_path="success.pdf"),
            source_row(source_id="source-failed", local_path="failed.pdf"),
        ],
    )
    with database.session() as session:
        parent = ImportRunService(session, project_root=tmp_path).create_run(corpus_path)
    parent_ids = _set_parent_outcomes(database, parent.import_run_id)

    with database.session() as session:
        linked = LinkedImportRunService(session, project_root=tmp_path).create_linked_run(
            corpus_path,
            parent_import_run_id=parent.import_run_id,
            mode="retry_failed",
        )

    linked_run = get_run(database, linked.import_run_id)
    linked_items = {item.source_id: item for item in linked_run.items}

    assert linked_run.run_mode == "retry_failed"
    assert linked_items["source-failed"].item_status == "valid"
    assert linked_items["source-failed"].retry_of_import_item_id == parent_ids["failed"]
    assert linked_items["source-success"].item_status == "skipped"
    assert linked_items["source-success"].matched_import_item_id == parent_ids["success"]


def test_corpus_mismatch_rolls_back_new_linked_run(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    parent_path = make_corpus(tmp_path, rows=[source_row(source_id="source-1")])
    with database.session() as session:
        parent = ImportRunService(session, project_root=tmp_path).create_run(parent_path)

    other_path = make_corpus(tmp_path, rows=[source_row(source_id="source-1")])
    other_path.write_text(
        other_path.read_text(encoding="utf-8").replace("test_corpus", "other_corpus"),
        encoding="utf-8",
    )

    with database.session() as session:
        before = session.scalar(select(func.count()).select_from(ImportRun))
        with pytest.raises(ValueError, match="corpus_id"):
            LinkedImportRunService(session, project_root=tmp_path).create_linked_run(
                other_path,
                parent_import_run_id=parent.import_run_id,
                mode="resume",
            )
        after = session.scalar(select(func.count()).select_from(ImportRun))

    assert before == after == 1
