from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import fitz
import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "detect_non_primary_article.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("detect_non_primary_article", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


detector = _load_module()


def _make_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def test_detects_commentary_label(tmp_path: Path) -> None:
    # Mirrors the real PACIFIC-5 near-miss this session: a standalone
    # article-type label line the journal itself prints on page 1.
    pdf_path = tmp_path / "commentary.pdf"
    _make_pdf(
        pdf_path,
        "Thoracic Cancer, 2026\nCOMMENTARY\nOPEN ACCESS\n"
        "A Real Trial: Refining Patient Selection for Something\n",
    )

    result = detector.detect_non_primary_article_type(pdf_path)

    assert result.verdict == "non_primary_article_type"
    assert result.matched_label == "commentary"


def test_detects_editorial_label(tmp_path: Path) -> None:
    pdf_path = tmp_path / "editorial.pdf"
    _make_pdf(pdf_path, "Journal Name\nEDITORIAL\nSome Editorial Title\n")

    result = detector.detect_non_primary_article_type(pdf_path)

    assert result.verdict == "non_primary_article_type"
    assert result.matched_label == "editorial"


def test_detects_correspondence_opening_phrase(tmp_path: Path) -> None:
    pdf_path = tmp_path / "letter.pdf"
    _make_pdf(
        pdf_path,
        "Journal Name\nA Response to a Prior Study\n\nTo the Editor,\n"
        "We read with interest the recent study by...\n",
    )

    result = detector.detect_non_primary_article_type(pdf_path)

    assert result.verdict == "non_primary_article_type"
    assert result.matched_label == "correspondence_opening"


def test_does_not_flag_primary_research_paper(tmp_path: Path) -> None:
    pdf_path = tmp_path / "primary.pdf"
    _make_pdf(
        pdf_path,
        "Journal of Oncology, 2026\nRESEARCH ARTICLE\n"
        "Pembrolizumab plus Chemotherapy in Advanced NSCLC: A Randomized Trial\n"
        "Abstract\nBackground: We conducted a phase 3 randomized controlled trial...\n",
    )

    result = detector.detect_non_primary_article_type(pdf_path)

    assert result.verdict == "primary_or_unknown"
    assert result.matched_label is None


def test_does_not_flag_marker_word_embedded_in_a_sentence(tmp_path: Path) -> None:
    # A discussion section can legitimately use these words in prose -- only
    # a standalone label line (or the exact correspondence-opening phrase)
    # should match, never a substring inside a longer sentence.
    pdf_path = tmp_path / "discussion.pdf"
    _make_pdf(
        pdf_path,
        "Journal Name\nRESEARCH ARTICLE\nA Real Trial\n"
        "Abstract\nThis editorial commentary style of discussion has been "
        "noted in prior correspondence about similar trials.\n",
    )

    result = detector.detect_non_primary_article_type(pdf_path)

    assert result.verdict == "primary_or_unknown"


def test_missing_pdf_returns_primary_or_unknown(tmp_path: Path) -> None:
    result = detector.detect_non_primary_article_type(tmp_path / "does-not-exist.pdf")

    assert result.verdict == "primary_or_unknown"
    assert result.matched_label is None


def _write_evidence_records(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def test_cli_flags_non_primary_pdf(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf_path = tmp_path / "commentary.pdf"
    _make_pdf(pdf_path, "Journal\nCOMMENTARY\nA Real Trial\n")
    evidence_path = tmp_path / "evidence_records.jsonl"
    _write_evidence_records(
        evidence_path,
        [
            {
                "evidence_record_id": "ev-1",
                "review_status": "reviewed",
                "source_span": {"local_pdf_path": str(pdf_path)},
            }
        ],
    )

    sys.argv = ["detect_non_primary_article.py", "--evidence", str(evidence_path)]
    result = detector.main()

    assert result == 1
    captured = capsys.readouterr()
    assert "1 PDF(s) flagged" in captured.out
    assert "ev-1" in captured.out


def test_cli_reports_clean_when_no_matches(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pdf_path = tmp_path / "primary.pdf"
    _make_pdf(pdf_path, "Journal\nRESEARCH ARTICLE\nA Real Trial\n")
    evidence_path = tmp_path / "evidence_records.jsonl"
    _write_evidence_records(
        evidence_path,
        [
            {
                "evidence_record_id": "ev-1",
                "review_status": "reviewed",
                "source_span": {"local_pdf_path": str(pdf_path)},
            }
        ],
    )

    sys.argv = ["detect_non_primary_article.py", "--evidence", str(evidence_path)]
    result = detector.main()

    assert result == 0
    captured = capsys.readouterr()
    assert "No non-primary article-type labels found" in captured.out


def test_cli_filters_by_review_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    commentary_pdf = tmp_path / "commentary.pdf"
    _make_pdf(commentary_pdf, "Journal\nCOMMENTARY\nA Real Trial\n")
    evidence_path = tmp_path / "evidence_records.jsonl"
    _write_evidence_records(
        evidence_path,
        [
            {
                "evidence_record_id": "ev-draft",
                "review_status": "draft",
                "source_span": {"local_pdf_path": str(commentary_pdf)},
            }
        ],
    )

    sys.argv = [
        "detect_non_primary_article.py",
        "--evidence",
        str(evidence_path),
        "--review-status",
        "reviewed",
    ]
    result = detector.main()

    assert result == 0
    captured = capsys.readouterr()
    assert "No evidence records with a source_span.local_pdf_path found" in captured.out
