"""Integration tests for immutable linked corpus ingestion."""

from pathlib import Path

from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from knowledge_engine.import_runs.linked_ingestion import LinkedCorpusIngestionService
from tests.corpus_fixtures import get_run, make_database
from tests.test_corpus_import import (
    StubParser,
    declare_pdf,
    make_corpus,
    parsed_paper,
    source_row,
)


def test_resume_does_not_reparse_prior_success(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(local_path="paper.pdf", doi="10.1234/source")],
    )
    paper_path = declare_pdf(tmp_path, "paper.pdf")

    with database.session() as session:
        first = CorpusIngestionService(
            session,
            project_root=tmp_path,
            parser=StubParser(
                {
                    "paper.pdf": parsed_paper(
                        paper_path,
                        title="Imported",
                        doi="10.1234/source",
                        content_hash="a" * 64,
                    )
                }
            ),
        ).import_corpus(corpus_path)

    with database.session() as session:
        resumed = LinkedCorpusIngestionService(
            session,
            project_root=tmp_path,
            parser=StubParser(
                {
                    "paper.pdf": AssertionError(
                        "prior success must not be parsed during resume"
                    )
                }
            ),
        ).import_linked_corpus(
            corpus_path,
            parent_import_run_id=first.import_run_id,
            mode="resume",
        )

    parent = get_run(database, first.import_run_id)
    run = get_run(database, resumed.import_run_id)
    assert resumed.run_status == "succeeded"
    assert resumed.imported_count == 0
    assert resumed.failed_count == 0
    assert resumed.skipped_count == 1
    assert run.run_mode == "resume"
    assert run.parent_import_run_id == first.import_run_id
    assert run.items[0].item_status == "skipped"
    assert run.items[0].matched_import_item_id == parent.items[0].import_item_id
    assert parent.items[0].item_status == "imported"


def test_retry_failed_processes_only_failed_parent_item(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(
                source_id="failed-source",
                local_path="failed.pdf",
                doi="10.1234/failed",
            ),
            source_row(
                source_id="success-source",
                local_path="success.pdf",
                doi="10.1234/success",
            ),
        ],
    )
    failed_path = declare_pdf(tmp_path, "failed.pdf")
    success_path = declare_pdf(tmp_path, "success.pdf")

    with database.session() as session:
        first = CorpusIngestionService(
            session,
            project_root=tmp_path,
            parser=StubParser(
                {
                    "failed.pdf": RuntimeError("parse failure"),
                    "success.pdf": parsed_paper(
                        success_path,
                        title="Success",
                        doi="10.1234/success",
                        content_hash="b" * 64,
                    ),
                }
            ),
        ).import_corpus(corpus_path)

    with database.session() as session:
        retried = LinkedCorpusIngestionService(
            session,
            project_root=tmp_path,
            parser=StubParser(
                {
                    "failed.pdf": parsed_paper(
                        failed_path,
                        title="Recovered",
                        doi="10.1234/failed",
                        content_hash="c" * 64,
                    ),
                    "success.pdf": AssertionError(
                        "prior success must not be parsed during retry"
                    ),
                }
            ),
        ).import_linked_corpus(
            corpus_path,
            parent_import_run_id=first.import_run_id,
            mode="retry_failed",
        )

    parent = get_run(database, first.import_run_id)
    run = get_run(database, retried.import_run_id)
    items = {item.source_id: item for item in run.items}
    parent_items = {item.source_id: item for item in parent.items}

    assert retried.run_status == "succeeded"
    assert retried.imported_count == 1
    assert retried.failed_count == 0
    assert retried.skipped_count == 1
    assert run.run_mode == "retry_failed"
    assert items["failed-source"].item_status == "imported"
    assert (
        items["failed-source"].retry_of_import_item_id
        == parent_items["failed-source"].import_item_id
    )
    assert items["success-source"].item_status == "skipped"
    assert parent_items["failed-source"].item_status == "failed"
    assert parent_items["success-source"].item_status == "imported"
