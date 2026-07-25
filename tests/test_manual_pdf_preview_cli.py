from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import fitz
import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint


def make_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "Semaglutide in Adults with Obesity\n"
            "Abstract\n"
            "This paper studies semaglutide treatment outcomes.\n"
            "Introduction\n"
            "Body text includes DOI 10.1234/example.doi and additional findings."
        ),
    )
    document.save(path)
    document.close()


def test_manual_pdf_preview_cli_writes_evidence_json(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    output = tmp_path / "preview.json"

    result = CliRunner().invoke(
        entrypoint.app,
        ["manual-pdf-preview", "--pdf", str(pdf_path), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "No DOI was found" not in result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["doi"] == "10.1234/example.doi"
    assert payload["doi_lookup_performed"] is False
    assert "no manifest row was written" in result.output


def test_manual_pdf_preview_cli_rejects_existing_output(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    output = tmp_path / "preview.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["manual-pdf-preview", "--pdf", str(pdf_path), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert output.read_text(encoding="utf-8") == "existing"


def test_manual_pdf_preview_cli_reports_missing_email_for_doi_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    output = tmp_path / "preview.json"

    def fail_if_called() -> None:
        raise ValueError("KE_UNPAYWALL_EMAIL is not set.")

    monkeypatch.setattr(entrypoint, "_unpaywall_lookup_service", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "manual-pdf-preview",
            "--pdf",
            str(pdf_path),
            "--output",
            str(output),
            "--doi-lookup",
        ],
    )

    assert result.exit_code != 0
    assert "KE_UNPAYWALL_EMAIL" in result.output
    assert not output.exists()


def _preview_payload(tmp_path: Path, **overrides: object) -> Path:
    base: dict[str, object] = {
        "source_path": str(tmp_path / "paper.pdf"),
        "content_hash": "a" * 64,
        "title": "Semaglutide in Adults with Obesity",
        "authors": ["Ada Lovelace"],
        "abstract": "An abstract.",
        "doi": "10.1234/example.doi",
        "page_count": 1,
        "word_count": 20,
        "doi_lookup_performed": True,
        "unpaywall_title": "Semaglutide in Adults with Obesity",
        "unpaywall_is_oa": True,
        "unpaywall_best_license": "CC BY",
        "license_rule_result": "passed",
        "previewed_at": datetime.now(UTC).isoformat(),
    }
    base.update(overrides)
    path = tmp_path / "preview.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return path


def test_manual_pdf_manifest_draft_cli_writes_one_row(tmp_path: Path) -> None:
    preview_path = _preview_payload(tmp_path)
    output = tmp_path / "draft.csv"

    result = CliRunner().invoke(
        entrypoint.app,
        ["manual-pdf-manifest-draft", "--preview", str(preview_path), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "No sources.csv file was modified" in " ".join(result.output.split())
    content = output.read_text(encoding="utf-8")
    assert "manual-" + "a" * 12 in content
    assert "Semaglutide in Adults with Obesity" in content


def test_manual_pdf_manifest_draft_cli_refuses_unverified_license(tmp_path: Path) -> None:
    preview_path = _preview_payload(tmp_path, license_rule_result="incomplete_missing_license")
    output = tmp_path / "draft.csv"

    result = CliRunner().invoke(
        entrypoint.app,
        ["manual-pdf-manifest-draft", "--preview", str(preview_path), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert not output.exists()
