import json
from pathlib import Path

from sqlalchemy import text

from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from knowledge_engine.parser import ParsedPaper
from tests.corpus_fixtures import get_run, make_database
from tests.test_corpus_import import StubParser, declare_pdf, make_corpus, parsed_paper, source_row


def _counts(database: Database) -> tuple[int, int, int]:
    with database.session() as session:
        papers = session.execute(text("SELECT count(*) FROM papers")).scalar_one()
        paper_texts = session.execute(text("SELECT count(*) FROM paper_texts")).scalar_one()
        search_rows = session.execute(text("SELECT count(*) FROM paper_search")).scalar_one()
    return int(papers), int(paper_texts), int(search_rows)


def _seed_paper(database: Database, parsed: ParsedPaper) -> int:
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(parsed)
        return paper.id


def test_exact_hash_duplicate_skips_without_paper_text_or_fts_write(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    existing_path = declare_pdf(tmp_path, "existing.pdf")
    existing_id = _seed_paper(
        database,
        parsed_paper(
            existing_path,
            title="Existing",
            doi="10.1234/existing",
            content_hash="a" * 64,
        ),
    )
    before = _counts(database)

    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(local_path="candidate.pdf", doi="10.1234/candidate")],
    )
    candidate_path = declare_pdf(tmp_path, "candidate.pdf")
    parser = StubParser(
        {
            "candidate.pdf": parsed_paper(
                candidate_path,
                title="Candidate",
                doi="10.1234/candidate",
                content_hash="a" * 64,
            )
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    item = run.items[0]

    assert result.run_status == "succeeded"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 1
    assert result.needs_review_count == 0
    assert item.item_status == "skipped"
    assert item.duplicate_outcome == "exact_hash_duplicate"
    assert item.matched_paper_id == existing_id
    assert item.computed_content_hash == "a" * 64
    evidence = json.loads(item.duplicate_evidence_json or "{}")
    assert evidence["decision"]["reason_code"] == "matching_content_hash"
    assert _counts(database) == before


def test_doi_hash_conflict_requires_review_without_persistence_write(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    existing_path = declare_pdf(tmp_path, "existing.pdf")
    existing_id = _seed_paper(
        database,
        parsed_paper(
            existing_path,
            title="Existing",
            doi="10.1234/shared",
            content_hash="a" * 64,
        ),
    )
    before = _counts(database)

    corpus_path = make_corpus(
        tmp_path,
        rows=[source_row(local_path="candidate.pdf", doi="10.1234/shared")],
    )
    candidate_path = declare_pdf(tmp_path, "candidate.pdf")
    parser = StubParser(
        {
            "candidate.pdf": parsed_paper(
                candidate_path,
                title="Changed Version",
                doi="10.1234/shared",
                content_hash="b" * 64,
            )
        }
    )

    with database.session() as session:
        result = CorpusIngestionService(
            session, project_root=tmp_path, parser=parser
        ).import_corpus(corpus_path)

    run = get_run(database, result.import_run_id)
    item = run.items[0]
    evidence = json.loads(item.duplicate_evidence_json or "{}")

    assert result.run_status == "needs_review"
    assert result.imported_count == 0
    assert result.failed_count == 0
    assert result.skipped_count == 0
    assert result.needs_review_count == 1
    assert item.item_status == "needs_review"
    assert item.duplicate_outcome == "doi_hash_conflict"
    assert item.matched_paper_id == existing_id
    assert item.computed_content_hash == "b" * 64
    assert evidence["decision"]["reason_code"] == "matching_doi_conflicting_content_hash"
    assert _counts(database) == before
