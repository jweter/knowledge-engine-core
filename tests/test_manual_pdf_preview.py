from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import fitz
import pytest

from knowledge_engine.manual_pdf_preview import (
    ManualPdfPreviewError,
    export_manual_pdf_manifest_draft,
    prepare_manual_pdf_preview,
)
from knowledge_engine.unpaywall_lookup import UnpaywallLookupResult, UnpaywallRecord


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
    document.set_metadata(
        {
            "title": "Semaglutide in Adults with Obesity",
            "author": "Ada Lovelace; Grace Hopper",
        }
    )
    document.save(path)
    document.close()


class FakeUnpaywallLookup:
    def __init__(self, result: UnpaywallLookupResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def lookup(self, doi: str) -> UnpaywallLookupResult:
        self.calls.append(doi)
        return self.result


def _found_result(license_rule_result: str = "passed") -> UnpaywallLookupResult:
    record = UnpaywallRecord(
        title="Semaglutide in Adults with Obesity",
        is_oa=True,
        oa_status="gold",
        best_oa_location_url="https://example.org/preprint.pdf",
        best_oa_location_license="cc-by",
        license_rule_result=license_rule_result,
        oa_locations=(),
    )
    return UnpaywallLookupResult(doi="10.1234/example.doi", found=True, record=record)


def test_prepare_preview_parses_pdf_locally_without_lookup(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)

    preview = prepare_manual_pdf_preview(pdf_path)

    assert preview.title == "Semaglutide in Adults with Obesity"
    assert preview.authors == ("Ada Lovelace", "Grace Hopper")
    assert preview.doi == "10.1234/example.doi"
    assert preview.page_count == 1
    assert preview.doi_lookup_performed is False
    assert preview.unpaywall_best_license is None
    assert preview.license_rule_result == "incomplete_missing_license"
    assert datetime.fromisoformat(preview.previewed_at).tzinfo is not None


def test_prepare_preview_looks_up_doi_when_service_supplied(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    service = FakeUnpaywallLookup(_found_result())

    preview = prepare_manual_pdf_preview(pdf_path, unpaywall_service=service)

    assert service.calls == ["10.1234/example.doi"]
    assert preview.doi_lookup_performed is True
    assert preview.unpaywall_is_oa is True
    assert preview.unpaywall_best_license == "CC BY"
    assert preview.license_rule_result == "passed"


def test_prepare_preview_skips_lookup_when_no_doi_found(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "No identifiers here at all.")
    document.save(pdf_path)
    document.close()
    service = FakeUnpaywallLookup(_found_result())

    preview = prepare_manual_pdf_preview(pdf_path, unpaywall_service=service)

    assert preview.doi is None
    assert preview.doi_lookup_performed is False
    assert service.calls == []


def test_prepare_preview_raises_on_malformed_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "bad.pdf"
    pdf_path.write_bytes(b"not a real pdf")

    with pytest.raises(ManualPdfPreviewError):
        prepare_manual_pdf_preview(pdf_path)


def test_prepare_preview_rejects_a_symlinked_pdf(tmp_path: Path) -> None:
    real_path = tmp_path / "real.pdf"
    make_pdf(real_path)
    symlink_path = tmp_path / "link.pdf"
    symlink_path.symlink_to(real_path)

    with pytest.raises(ManualPdfPreviewError, match="symbolic link"):
        prepare_manual_pdf_preview(symlink_path)


def test_preview_to_json_round_trips(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)

    preview = prepare_manual_pdf_preview(pdf_path)
    payload = json.loads(preview.to_json())

    assert payload["title"] == "Semaglutide in Adults with Obesity"
    assert payload["authors"] == ["Ada Lovelace", "Grace Hopper"]


def _preview_payload(tmp_path: Path, **overrides: object) -> Path:
    base: dict[str, object] = {
        "source_path": str(tmp_path / "paper.pdf"),
        "content_hash": "a" * 64,
        "title": "Semaglutide in Adults with Obesity",
        "authors": ["Ada Lovelace", "Grace Hopper"],
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


def test_manifest_draft_produces_one_row_for_a_passed_preview(tmp_path: Path) -> None:
    preview_path = _preview_payload(tmp_path)

    draft = export_manual_pdf_manifest_draft(preview_path)

    assert len(draft.rows) == 1
    row = draft.rows[0]
    assert row["source_id"] == "manual-" + "a" * 12
    assert row["title"] == "Semaglutide in Adults with Obesity"
    assert row["authors"] == "Ada Lovelace; Grace Hopper"
    assert row["doi"] == "10.1234/example.doi"
    assert row["source_url"] == "https://doi.org/10.1234/example.doi"
    assert row["local_path"] == "paper.pdf"
    assert row["license_type"] == "CC BY"
    assert row["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert row["inclusion_status"] == "included"
    assert row["expected_content_hash"] == "sha256:" + "a" * 64


def test_manifest_draft_refuses_when_license_not_passed(tmp_path: Path) -> None:
    preview_path = _preview_payload(tmp_path, license_rule_result="incomplete_missing_license")

    with pytest.raises(ManualPdfPreviewError, match="license evidence is not verified"):
        export_manual_pdf_manifest_draft(preview_path)


def test_manifest_draft_refuses_when_no_doi(tmp_path: Path) -> None:
    preview_path = _preview_payload(tmp_path, doi=None)

    with pytest.raises(ManualPdfPreviewError, match="missing a DOI"):
        export_manual_pdf_manifest_draft(preview_path)


def test_manifest_draft_rejects_a_symlinked_input(tmp_path: Path) -> None:
    real_path = _preview_payload(tmp_path)
    symlink_path = tmp_path / "link.json"
    symlink_path.symlink_to(real_path)

    with pytest.raises(ManualPdfPreviewError, match="symbolic link"):
        export_manual_pdf_manifest_draft(symlink_path)


def test_manifest_draft_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "preview.json"
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(ManualPdfPreviewError, match="not valid JSON"):
        export_manual_pdf_manifest_draft(path)


def test_preview_then_manifest_draft_end_to_end(tmp_path: Path) -> None:
    """A real preview's `unpaywall_best_license` (Unpaywall's own raw,
    hyphenated token format, e.g. "cc-by") must already be normalized to
    the space-separated "CC BY" format `license_deed_url` expects -- found
    via a live smoke test where this exact two-step flow raised
    "License evidence has no canonical deed URL" because the raw token was
    stored unnormalized. A hand-authored preview fixture with an
    already-normalized license would never have caught this; only driving
    both functions together does."""

    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)
    service = FakeUnpaywallLookup(_found_result())
    preview = prepare_manual_pdf_preview(pdf_path, unpaywall_service=service)
    preview_path = tmp_path / "preview.json"
    preview_path.write_text(preview.to_json(), encoding="utf-8")

    draft = export_manual_pdf_manifest_draft(preview_path)

    assert draft.rows[0]["license_type"] == "CC BY"
    assert draft.rows[0]["license_url"] == "https://creativecommons.org/licenses/by/4.0/"
