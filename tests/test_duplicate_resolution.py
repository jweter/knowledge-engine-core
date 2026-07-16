import json
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from knowledge_engine.duplicate_resolution import resolve_duplicate_before_persistence
from knowledge_engine.models import ImportItem, ImportRun, ManifestSnapshot, Paper
from knowledge_engine.parser import ParsedPaper
from tests.corpus_fixtures import make_database


def _add_run_and_item(
    session: Session,
    *,
    run_id: str = "run-current",
    item_id: str = "item-current",
    content_hash: str | None = None,
    normalized_doi: str | None = "10.1000/example",
    line: int = 2,
) -> ImportItem:
    snapshot_id = f"snapshot-{run_id}"
    session.add(
        ManifestSnapshot(
            snapshot_id=snapshot_id,
            corpus_path="data/corpus.json",
            source_manifest_path="data/sources.csv",
            corpus_json_bytes=b"{}",
            source_csv_bytes=b"source_id,title\n",
            corpus_json_text="{}",
            source_csv_text="source_id,title\n",
            corpus_json_sha256="a" * 64,
            source_csv_sha256="b" * 64,
            combined_sha256=(run_id[-1] if run_id else "c") * 64,
            captured_at="2026-07-16T00:00:00+00:00",
        )
    )
    session.add(
        ImportRun(
            import_run_id=run_id,
            corpus_id="corpus",
            corpus_name="Corpus",
            manifest_version=1,
            validation_mode="check_files",
            run_mode="fresh",
            run_status="running",
            manifest_validity="valid",
            import_readiness="ready",
            total_source_rows=1,
            valid_source_rows=1,
            warning_count=0,
            structural_error_count=0,
            import_blocker_count=0,
            created_at="2026-07-16T00:00:00+00:00",
            completed_at="2026-07-16T00:00:00+00:00",
            source_manifest_path="data/sources.csv",
            license_policy_path="data/license.md",
            corpus_path="data/corpus.json",
            parent_import_run_id=None,
            manifest_snapshot_id=snapshot_id,
        )
    )
    item = ImportItem(
        import_item_id=item_id,
        import_run_id=run_id,
        source_id=item_id,
        csv_line_number=line,
        title="Candidate Paper",
        normalized_doi=normalized_doi,
        inclusion_status="included",
        usage_status="approved_open_access",
        local_path=f"{item_id}.pdf",
        item_status="valid",
        duplicate_outcome=None,
        matched_paper_id=None,
        matched_import_item_id=None,
        computed_content_hash=content_hash,
        duplicate_evidence_json=None,
        retry_of_import_item_id=None,
        blocks_manifest=False,
        blocks_import=False,
        warning_count=0,
        structural_error_count=0,
        import_blocker_count=0,
        created_at="2026-07-16T00:00:00+00:00",
        completed_at="2026-07-16T00:00:00+00:00",
    )
    session.add(item)
    session.flush()
    return item


def _parsed(path: Path, *, content_hash: str, doi: str | None) -> ParsedPaper:
    return ParsedPaper(
        source_path=path,
        content_hash=content_hash,
        title="Candidate Paper",
        authors=[],
        abstract=None,
        doi=doi,
        page_count=1,
        word_count=2,
        raw_text="candidate text",
        body_text="candidate text",
    )


def _counts(session: Session) -> tuple[int, int]:
    paper_count = session.scalar(select(func.count()).select_from(Paper)) or 0
    fts_count = session.execute(text("SELECT count(*) FROM paper_search")).scalar_one()
    return int(paper_count), int(fts_count)


def test_no_duplicate_is_importable_and_persists_auditable_evidence(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    with database.session() as session:
        item = _add_run_and_item(session)
        before = _counts(session)

        decision = resolve_duplicate_before_persistence(
            session,
            item=item,
            parsed=_parsed(tmp_path / "candidate.pdf", content_hash="a" * 64, doi=None),
        )

        assert decision.item_status == "importable"
        assert item.duplicate_outcome == "none"
        assert item.computed_content_hash == "a" * 64
        assert item.matched_paper_id is None
        assert item.matched_import_item_id is None
        assert json.loads(item.duplicate_evidence_json or "{}")['decision']['reason_code'] == (
            "no_duplicate_signal"
        )
        assert _counts(session) == before


def test_exact_persisted_hash_is_skipped_without_new_paper_or_fts_write(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    with database.session() as session:
        existing = Paper(
            title="Existing",
            doi="10.1000/existing",
            source_path="existing.pdf",
            content_hash="a" * 64,
            publication_year=2024,
            page_count=1,
            word_count=2,
        )
        session.add(existing)
        item = _add_run_and_item(session)
        session.flush()
        before = _counts(session)

        decision = resolve_duplicate_before_persistence(
            session,
            item=item,
            parsed=_parsed(tmp_path / "candidate.pdf", content_hash="a" * 64, doi=None),
        )

        assert decision.item_status == "skipped"
        assert decision.duplicate_outcome == "exact_hash_duplicate"
        assert item.matched_paper_id == existing.id
        assert _counts(session) == before


def test_doi_hash_conflict_requires_review_without_paper_or_fts_write(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    with database.session() as session:
        existing = Paper(
            title="Existing",
            doi="https://doi.org/10.1000/example",
            source_path="existing.pdf",
            content_hash="b" * 64,
            publication_year=2024,
            page_count=1,
            word_count=2,
        )
        session.add(existing)
        item = _add_run_and_item(session)
        session.flush()
        before = _counts(session)

        decision = resolve_duplicate_before_persistence(
            session,
            item=item,
            parsed=_parsed(
                tmp_path / "candidate.pdf",
                content_hash="a" * 64,
                doi="doi:10.1000/example",
            ),
        )

        assert decision.item_status == "needs_review"
        assert decision.duplicate_outcome == "doi_hash_conflict"
        assert item.matched_paper_id == existing.id
        assert _counts(session) == before


def test_same_run_exact_hash_preserves_matched_import_item_identity(tmp_path: Path) -> None:
    database = make_database(tmp_path)
    with database.session() as session:
        first = _add_run_and_item(
            session,
            item_id="item-first",
            content_hash="a" * 64,
            normalized_doi=None,
            line=2,
        )
        current = ImportItem(
            import_item_id="item-current",
            import_run_id=first.import_run_id,
            source_id="source-current",
            csv_line_number=3,
            title="Candidate Paper",
            normalized_doi=None,
            inclusion_status="included",
            usage_status="approved_open_access",
            local_path="candidate.pdf",
            item_status="valid",
            duplicate_outcome=None,
            matched_paper_id=None,
            matched_import_item_id=None,
            computed_content_hash=None,
            duplicate_evidence_json=None,
            retry_of_import_item_id=None,
            blocks_manifest=False,
            blocks_import=False,
            warning_count=0,
            structural_error_count=0,
            import_blocker_count=0,
            created_at="2026-07-16T00:00:00+00:00",
            completed_at="2026-07-16T00:00:00+00:00",
        )
        session.add(current)
        session.flush()
        before = _counts(session)

        decision = resolve_duplicate_before_persistence(
            session,
            item=current,
            parsed=_parsed(tmp_path / "candidate.pdf", content_hash="a" * 64, doi=None),
        )

        assert decision.item_status == "skipped"
        assert decision.duplicate_outcome == "exact_hash_duplicate"
        assert current.matched_paper_id is None
        assert current.matched_import_item_id == "item-first"
        assert _counts(session) == before
