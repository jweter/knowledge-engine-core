from __future__ import annotations

import json
from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.general_question_extraction_promotion import (
    GENERAL_QUESTION_EXTRACTION_PROMOTION_RULES_VERSION,
    extraction_rejection_record_path,
    run_general_question_extraction_and_promotion,
)
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper

_RICH_TEXT = (
    "Abstract\n"
    "We enrolled 253 adults with obesity in this trial.\n"
    "Participants received semaglutide once weekly for 68 weeks.\n"
    "Weight loss was compared with placebo over the study period.\n"
    "The primary outcome was change in body weight from baseline.\n\n"
    "Methods\n"
    "This was a randomized, double-blind, placebo-controlled trial.\n\n"
    "Results\n"
    "Mean weight loss was 15.3% (95% CI, 12.1-18.5) versus 2.6% with placebo.\n\n"
    "Limitations\n"
    "This study was limited by a short follow-up period.\n\n"
    "Conclusion\n"
    "Semaglutide produced significantly greater weight loss than placebo.\n"
)

_SPARSE_TEXT = "This is an unstructured document with no recognizable headings at all."


def _database(tmp_path: Path, name: str = "db") -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / name,
            database_url=f"sqlite:///{tmp_path / name}.sqlite3",
        )
    )
    database.initialize()
    return database


def _parsed_paper(tmp_path: Path, content_hash: str, *, title: str, text: str) -> ParsedPaper:
    return ParsedPaper(
        source_path=tmp_path / f"{content_hash}.pdf",
        content_hash=content_hash,
        title=title,
        authors=["Ada Scientist"],
        abstract="An abstract about semaglutide and weight loss.",
        doi=f"10.1/{content_hash[:8]}",
        page_count=1,
        word_count=10,
        raw_text=text,
        body_text=text,
        pages=[ParsedPage(page_number=1, text=text)],
    )


def _receipt(
    tmp_path: Path,
    *,
    name: str,
    paper_ids: list[tuple[int, str]],
    search_run_id: str = "run-1",
    research_question_id: str = "rq-1",
    acquisition_route: str = "pmc_oa",
) -> Path:
    payload = {
        "schema_version": 1,
        "search_run_id": search_run_id,
        "research_question_id": research_question_id,
        "acquisition_route": acquisition_route,
        "import_run_id": "import-1",
        "parsed_count": len(paper_ids),
        "persisted_count": len(paper_ids),
        "reused_count": 0,
        "items": [
            {
                "candidate_id": f"candidate-{paper_id}",
                "paper_id": paper_id,
                "persistence_status": status,
            }
            for paper_id, status in paper_ids
        ],
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_promotes_a_grounded_candidate_and_writes_no_rejection_file(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Rich Paper", text=_RICH_TEXT)
        )
        paper_id = paper.id

    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(paper_id, "persisted")])
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.schema_version == GENERAL_QUESTION_EXTRACTION_PROMOTION_RULES_VERSION
    assert summary.search_run_id == "run-1"
    assert summary.research_question_id == "rq-1"
    assert summary.acquisition_route == "pmc_oa"
    assert summary.paper_count == 1
    assert summary.promoted_count >= 1
    assert summary.duplicate_count == 0
    assert summary.rejected == ()
    assert summary.rejection_record_path is None
    assert not extraction_rejection_record_path(receipt_path).exists()
    assert summary.duration_ms >= 0
    assert summary.extraction_duration_ms >= 0
    assert summary.promotion_duration_ms >= 0
    assert summary.evidence_store_record_count == summary.promoted_count

    payload = summary.to_dict()
    assert payload["paper_count"] == summary.paper_count
    assert payload["promoted_count"] == summary.promoted_count
    assert payload["rejected"] == []
    assert payload["rejection_record_path"] is None
    assert payload["duration_ms"] == summary.duration_ms
    assert payload["extraction_duration_ms"] == summary.extraction_duration_ms
    assert payload["promotion_duration_ms"] == summary.promotion_duration_ms
    assert payload["evidence_store_record_count"] == summary.evidence_store_record_count
    json.dumps(payload)  # to_dict() must be directly JSON-serializable.

    lines = evidence_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == summary.promoted_count
    records = [json.loads(line) for line in lines]
    for record in records:
        assert record["source_span"]["paper_id"] == paper_id
        assert record["review_status"] == "draft"
        assert record["claim_text"] in _RICH_TEXT
        assert record["result_summary"] in _RICH_TEXT


def test_rerunning_the_same_receipt_is_idempotent(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Rich Paper", text=_RICH_TEXT)
        )
        paper_id = paper.id

    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(paper_id, "reused")])
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        first = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )
    with database.session() as session:
        second = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert first.promoted_count >= 1
    assert second.promoted_count == 0
    assert second.duplicate_count == first.promoted_count
    lines = evidence_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == first.promoted_count
    # A duplicate re-run must not inflate the revision count: it stays the
    # same total, so a caller polling this field correctly sees no new
    # Evidence Records became available on the second call.
    assert first.evidence_store_record_count == first.promoted_count
    assert second.evidence_store_record_count == first.evidence_store_record_count


def test_paper_with_no_claim_candidates_is_rejected_with_a_durable_reason(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "b" * 64, title="Sparse Paper", text=_SPARSE_TEXT)
        )
        paper_id = paper.id

    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(paper_id, "persisted")])
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.promoted_count == 0
    assert len(summary.rejected) == 1
    assert summary.rejected[0].paper_id == paper_id
    assert summary.rejected[0].stage == "no_claim_candidates"
    assert not evidence_path.exists()
    # Nothing was ever promoted to this evidence file, so the revision
    # count is 0 rather than raising on a missing file.
    assert summary.evidence_store_record_count == 0
    # No candidate ever reached the promotion call, so that substage never ran.
    assert summary.promotion_duration_ms == 0
    # to_dict() must serialize rejection_record_path as a string, not a Path.
    assert summary.to_dict()["rejection_record_path"] == str(summary.rejection_record_path)
    assert summary.to_dict()["rejected"] == [
        {"paper_id": paper_id, "stage": "no_claim_candidates", "reason": summary.rejected[0].reason}
    ]

    rejection_path = summary.rejection_record_path
    assert rejection_path == extraction_rejection_record_path(receipt_path)
    assert rejection_path is not None
    payload = json.loads(rejection_path.read_text(encoding="utf-8"))
    assert payload["search_run_id"] == "run-1"
    assert payload["research_question_id"] == "rq-1"
    assert payload["acquisition_route"] == "pmc_oa"
    assert len(payload["rejections"]) == 1
    assert payload["rejections"][0]["paper_id"] == paper_id
    assert payload["rejections"][0]["stage"] == "no_claim_candidates"


def test_paper_with_no_persisted_pages_is_rejected(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        paper = Paper(
            title="Pageless Paper",
            source_path=str(tmp_path / "pageless.pdf"),
            content_hash="c" * 64,
            page_count=0,
            word_count=0,
        )
        session.add(paper)
        session.flush()
        paper_id = paper.id

    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(paper_id, "persisted")])
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.promoted_count == 0
    assert len(summary.rejected) == 1
    assert summary.rejected[0].paper_id == paper_id
    assert summary.rejected[0].stage == "no_parsed_pages"
    assert summary.rejected[0].reason == "Paper has no persisted pages to extract from."


def test_unknown_paper_id_in_receipt_is_rejected_as_paper_not_found(tmp_path: Path) -> None:
    database = _database(tmp_path)
    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(999, "persisted")])
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.paper_count == 1
    assert summary.promoted_count == 0
    assert len(summary.rejected) == 1
    assert summary.rejected[0].paper_id == 999
    assert summary.rejected[0].stage == "paper_not_found"


def test_a_later_success_clears_a_stale_rejection_record(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with database.session() as session:
        sparse = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "d" * 64, title="Sparse Paper", text=_SPARSE_TEXT)
        )
        sparse_id = sparse.id

    receipt_path = _receipt(tmp_path, name="receipt.json", paper_ids=[(sparse_id, "persisted")])
    evidence_path = tmp_path / "evidence.jsonl"
    with database.session() as session:
        run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )
    assert extraction_rejection_record_path(receipt_path).exists()

    # Overwrite the receipt at the same path to name a rich, promotable paper instead.
    with database.session() as session:
        rich = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "e" * 64, title="Rich Paper", text=_RICH_TEXT)
        )
        rich_id = rich.id
    _receipt(tmp_path, name="receipt.json", paper_ids=[(rich_id, "persisted")])

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.promoted_count >= 1
    assert summary.rejected == ()
    assert not extraction_rejection_record_path(receipt_path).exists()


def test_evidence_store_record_count_accumulates_across_receipts(tmp_path: Path) -> None:
    """issue #433 re-retrieval readiness: the count rises only when a later
    receipt against the same evidence file actually promotes something new,
    giving a caller a cheap signal for when it is worth re-retrieving.
    """

    database = _database(tmp_path)
    with database.session() as session:
        first_paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "a" * 64, title="Rich Paper One", text=_RICH_TEXT)
        )
        first_paper_id = first_paper.id

    evidence_path = tmp_path / "evidence.jsonl"
    first_receipt = _receipt(
        tmp_path, name="receipt-1.json", paper_ids=[(first_paper_id, "persisted")]
    )
    with database.session() as session:
        first = run_general_question_extraction_and_promotion(
            session, receipt_path=first_receipt, evidence_output_path=evidence_path
        )
    assert first.promoted_count >= 1
    assert first.evidence_store_record_count == first.promoted_count

    with database.session() as session:
        second_paper = PaperRepository(session).add_parsed_paper(
            _parsed_paper(tmp_path, "b" * 64, title="Rich Paper Two", text=_RICH_TEXT)
        )
        second_paper_id = second_paper.id

    second_receipt = _receipt(
        tmp_path,
        name="receipt-2.json",
        paper_ids=[(second_paper_id, "persisted")],
        search_run_id="run-2",
    )
    with database.session() as session:
        second = run_general_question_extraction_and_promotion(
            session, receipt_path=second_receipt, evidence_output_path=evidence_path
        )

    assert second.promoted_count >= 1
    assert second.evidence_store_record_count == first.evidence_store_record_count + (
        second.promoted_count
    )


def test_ignores_receipt_items_that_are_not_persisted_or_reused(tmp_path: Path) -> None:
    database = _database(tmp_path)
    receipt_path = _receipt(
        tmp_path, name="receipt.json", paper_ids=[(1, "failed"), (2, "skipped")]
    )
    evidence_path = tmp_path / "evidence.jsonl"

    with database.session() as session:
        summary = run_general_question_extraction_and_promotion(
            session, receipt_path=receipt_path, evidence_output_path=evidence_path
        )

    assert summary.paper_count == 0
    assert summary.rejected == ()
    assert summary.rejection_record_path is None
