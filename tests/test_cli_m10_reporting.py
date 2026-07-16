"""CLI reporting coverage for persisted M10 lineage and review state."""

from pathlib import Path

from typer.testing import CliRunner

import knowledge_engine.cli as cli
from knowledge_engine.cli import app
from knowledge_engine.database import PaperRepository
from knowledge_engine.import_runs import ImportRunService
from tests.corpus_fixtures import make_database
from tests.test_corpus_import import declare_pdf, make_corpus, parsed_paper, source_row


def test_corpus_run_show_reports_m10_lineage_and_review_fields(
    tmp_path: Path, monkeypatch
) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(source_id="source-review")],
    )

    paper_path = declare_pdf(tmp_path, "matched.pdf")
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            parsed_paper(
                paper_path,
                title="Matched",
                doi="10.1234/matched",
                content_hash="f" * 64,
            )
        )
        matched_paper_id = paper.id
        service = ImportRunService(session, project_root=tmp_path)
        persisted = service.create_run(corpus_path)
        run = service.get_run(persisted.import_run_id)
        assert run is not None
        run.run_mode = "resume"
        run.parent_import_run_id = "11111111-1111-1111-1111-111111111111"
        run.run_status = "needs_review"
        item = run.items[0]
        item.item_status = "needs_review"
        item.duplicate_outcome = "possible_title_year_duplicate"
        item.matched_paper_id = matched_paper_id
        item.matched_import_item_id = item.import_item_id
        item.retry_of_import_item_id = item.import_item_id
        import_item_id = item.import_item_id
        session.flush()

    monkeypatch.setattr(cli, "_database", lambda: database)
    result = CliRunner().invoke(app, ["corpus-run-show", persisted.import_run_id])

    assert result.exit_code == 0
    assert "Run mode: resume" in result.output
    assert (
        "Parent import run ID: 11111111-1111-1111-1111-111111111111" in result.output
    )
    assert "Needs review items: 1" in result.output
    assert "duplicate_outcome=possible_title_year_duplicate" in result.output
    assert f"matched_paper_id={matched_paper_id}" in result.output
    assert f"matched_import_item_id={import_item_id}" in result.output
    assert f"retry_of_import_item_id={import_item_id}" in result.output
