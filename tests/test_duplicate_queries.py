from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository, normalize_title
from knowledge_engine.models import Base, ImportItem, ImportRun, ManifestSnapshot, Paper


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _add_run(session: Session, run_id: str) -> None:
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
            run_status="succeeded",
            manifest_validity="valid",
            import_readiness="ready",
            total_source_rows=2,
            valid_source_rows=2,
            warning_count=0,
            structural_error_count=0,
            import_blocker_count=0,
            created_at="2026-07-16T00:00:00+00:00",
            completed_at="2026-07-16T00:01:00+00:00",
            source_manifest_path="data/sources.csv",
            license_policy_path="data/license.md",
            corpus_path="data/corpus.json",
            parent_import_run_id=None,
            manifest_snapshot_id=snapshot_id,
        )
    )


def _item(
    run_id: str,
    item_id: str,
    line: int,
    *,
    source_id: str,
    content_hash: str | None = None,
    doi: str | None = None,
) -> ImportItem:
    return ImportItem(
        import_item_id=item_id,
        import_run_id=run_id,
        source_id=source_id,
        csv_line_number=line,
        title=f"Title {line}",
        normalized_doi=doi,
        inclusion_status="included",
        usage_status="approved_open_access",
        local_path=f"paper-{line}.pdf",
        item_status="imported",
        duplicate_outcome="none",
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
        completed_at="2026-07-16T00:01:00+00:00",
    )


def test_paper_hash_and_doi_lookups_normalize_deterministically() -> None:
    with _session() as session:
        paper = Paper(
            title="A Paper",
            doi="https://doi.org/10.1000/Example",
            source_path="paper.pdf",
            content_hash="a" * 64,
            publication_year=2024,
            page_count=1,
            word_count=10,
        )
        session.add(paper)
        session.flush()
        repository = DuplicateQueryRepository(session)

        assert repository.paper_by_content_hash("a" * 64) is paper
        assert repository.paper_by_normalized_doi("doi:10.1000/example") is paper
        assert repository.paper_by_normalized_doi(None) is None


def test_title_year_lookup_is_unicode_case_whitespace_normalized_and_ordered() -> None:
    with _session() as session:
        session.add_all(
            [
                Paper(
                    title="  THE   Study  ",
                    doi=None,
                    source_path="one.pdf",
                    content_hash="a" * 64,
                    publication_year=2024,
                    page_count=1,
                    word_count=10,
                ),
                Paper(
                    title="The Study",
                    doi=None,
                    source_path="two.pdf",
                    content_hash="b" * 64,
                    publication_year=2024,
                    page_count=1,
                    word_count=10,
                ),
                Paper(
                    title="The Study",
                    doi=None,
                    source_path="other-year.pdf",
                    content_hash="c" * 64,
                    publication_year=2023,
                    page_count=1,
                    word_count=10,
                ),
            ]
        )
        session.flush()

        matches = DuplicateQueryRepository(session).papers_by_normalized_title_year(
            "the study", 2024
        )

        assert [paper.source_path for paper in matches] == ["one.pdf", "two.pdf"]
        assert normalize_title("Ｔｈｅ\nStudy") == "the study"


def test_same_run_hash_lookup_returns_earliest_item_and_supports_exclusion() -> None:
    with _session() as session:
        _add_run(session, "run-1")
        session.add_all(
            [
                _item("run-1", "item-2", 3, source_id="source-2", content_hash="a" * 64),
                _item("run-1", "item-1", 2, source_id="source-1", content_hash="a" * 64),
            ]
        )
        session.flush()
        repository = DuplicateQueryRepository(session)

        assert repository.same_run_item_by_content_hash("run-1", "a" * 64).import_item_id == "item-1"
        assert (
            repository.same_run_item_by_content_hash(
                "run-1", "a" * 64, exclude_import_item_id="item-1"
            ).import_item_id
            == "item-2"
        )


def test_same_run_doi_lookup_is_scoped_to_run() -> None:
    with _session() as session:
        _add_run(session, "run-1")
        _add_run(session, "run-2")
        session.add_all(
            [
                _item("run-1", "item-1", 2, source_id="source-1", doi="10.1000/example"),
                _item("run-2", "item-2", 2, source_id="source-2", doi="10.1000/example"),
            ]
        )
        session.flush()

        match = DuplicateQueryRepository(session).same_run_item_by_normalized_doi(
            "run-2", "10.1000/example"
        )

        assert match is not None
        assert match.import_item_id == "item-2"


def test_prior_source_lookup_uses_stable_source_id_not_row_position() -> None:
    with _session() as session:
        _add_run(session, "run-1")
        session.add_all(
            [
                _item("run-1", "item-a", 10, source_id="stable-a"),
                _item("run-1", "item-b", 2, source_id="stable-b"),
            ]
        )
        session.flush()

        match = DuplicateQueryRepository(session).prior_item_by_source_id("run-1", "stable-a")

        assert match is not None
        assert match.import_item_id == "item-a"
        assert match.csv_line_number == 10
