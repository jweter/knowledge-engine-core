"""Integration coverage for advisory title/year duplicate evidence."""

import json
from pathlib import Path

from sqlalchemy import text

from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.import_runs.ingestion import CorpusIngestionService
from tests.corpus_fixtures import get_run, make_database
from tests.test_corpus_import import StubParser, declare_pdf, make_corpus, parsed_paper, source_row


def _counts(database: Database) -> tuple[int, int, int]:
    with database.session() as session:
        papers = session.execute(text("SELECT count(*) FROM papers")).scalar_one()
        paper_texts = session.execute(text("SELECT count(*) FROM paper_texts")).scalar_one()
        search_rows = session.execute(text("SELECT count(*) FROM paper_search")).scalar_one()
    return int(papers), int(paper_texts), int(search_rows)


def test_manifest_title_year_match_requires_review_without_persistence(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(
                title="Shared Curated Title",
                publication_year="2024",
                local_path="candidate.pdf",
                doi="10.1234/candidate",
            )
        ],
    )
    existing_path = declare_pdf(tmp_path, "existing.pdf")
    with database.session() as session:
        existing = PaperRepository(session).add_parsed_paper(
            parsed_paper(
                existing_path,
                title="  shared curated title  ",
                doi="10.1234/existing",
                content_hash="a" * 64,
            )
        )
        existing.publication_year = 2024
        existing_id = existing.id
    before = _counts(database)

    candidate_path = declare_pdf(tmp_path, "candidate.pdf")
    parser = StubParser(
        {
            "candidate.pdf": parsed_paper(
                candidate_path,
                title="Parser Title Is Not Authoritative",
                doi="10.1234/candidate",
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
    assert item.duplicate_outcome == "possible_title_year_duplicate"
    assert item.matched_paper_id == existing_id
    assert evidence["candidate"]["publication_year"] == 2024
    assert evidence["candidate"]["normalized_title"] == "shared curated title"
    assert evidence["decision"]["reason_code"] == (
        "matching_normalized_title_and_publication_year"
    )
    assert evidence["matches"]["title_year"]["paper_id"] == existing_id
    assert _counts(database) == before


def test_missing_manifest_year_does_not_create_title_only_match(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    corpus_path = make_corpus(
        tmp_path,
        rows=[
            source_row(
                title="Shared Curated Title",
                publication_year="",
                local_path="candidate.pdf",
                doi="10.1234/candidate",
            )
        ],
    )
    existing_path = declare_pdf(tmp_path, "existing.pdf")
    with database.session() as session:
        existing = PaperRepository(session).add_parsed_paper(
            parsed_paper(
                existing_path,
                title="Shared Curated Title",
                doi="10.1234/existing",
                content_hash="c" * 64,
            )
        )
        existing.publication_year = 2024

    candidate_path = declare_pdf(tmp_path, "candidate.pdf")
    parser = StubParser(
        {
            "candidate.pdf": parsed_paper(
                candidate_path,
                title="Parser Title",
                doi="10.1234/candidate",
                content_hash="d" * 64,
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

    assert result.run_status == "succeeded"
    assert result.imported_count == 1
    assert result.needs_review_count == 0
    assert item.item_status == "imported"
    assert item.duplicate_outcome == "none"
    assert evidence["candidate"]["publication_year"] is None
    assert evidence["matches"]["title_year"] is None
    assert _counts(database) == (2, 2, 2)
