from pathlib import Path

import fitz
import pytest

from knowledge_engine.parser import MalformedDocumentError, PyMuPDFParser


def make_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "Metabolic Signals in Alzheimer Research\n"
            "Abstract\n"
            "This paper studies alzheimer biomarkers and metabolic signaling.\n"
            "Introduction\n"
            "Body text includes DOI 10.1234/example.doi and additional findings."
        ),
    )
    document.set_metadata(
        {
            "title": "Metabolic Signals in Alzheimer Research",
            "author": "Ada Lovelace; Grace Hopper",
        }
    )
    document.save(path)
    document.close()


def make_encrypted_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page()
    document.save(
        path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    document.close()


def test_parser_extracts_pdf_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    make_pdf(pdf_path)

    parsed = PyMuPDFParser().parse(pdf_path)

    assert parsed.title == "Metabolic Signals in Alzheimer Research"
    assert parsed.authors == ["Ada Lovelace", "Grace Hopper"]
    assert parsed.doi == "10.1234/example.doi"
    assert parsed.page_count == 1
    assert parsed.word_count > 10
    assert "alzheimer biomarkers" in parsed.raw_text.lower()


def test_parser_classifies_encrypted_pdf_as_expected_failure(tmp_path: Path) -> None:
    pdf_path = tmp_path / "encrypted.pdf"
    make_encrypted_pdf(pdf_path)

    with pytest.raises(MalformedDocumentError, match="encrypted"):
        PyMuPDFParser().parse(pdf_path)
