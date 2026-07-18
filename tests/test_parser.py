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


def test_title_fallback_rejects_malformed_embedded_metadata(tmp_path: Path) -> None:
    parser = PyMuPDFParser()

    title = parser._extract_title(
        {"title": "PII: S0304-4165(98)00177-9"},
        (
            "Rapid estimation of avidin and streptavidin by fluorescence quenching or\n\n"
            "fluorescence polarization\n\nGerald Kada"
        ),
        tmp_path / "paper.pdf",
    )

    assert title == (
        "Rapid estimation of avidin and streptavidin by fluorescence quenching or "
        "fluorescence polarization"
    )


def test_title_fallback_skips_banner_and_combines_wrapped_title(tmp_path: Path) -> None:
    parser = PyMuPDFParser()

    title = parser._extract_title(
        {},
        "REVIEWS\n\nThe dark side of cosmology: Dark\n\nmatter and dark energy\n\nDavid N. Spergel",
        tmp_path / "paper.pdf",
    )

    assert title == "The dark side of cosmology: Dark matter and dark energy"


def test_title_fallback_reads_explicit_patent_title(tmp_path: Path) -> None:
    parser = PyMuPDFParser()

    title = parser._extract_title(
        {},
        (
            "(12) INTERNATIONAL APPLICATION PUBLISHED UNDER THE PCT\n\n"
            "(54) Title: MINIATURIZED SPECTROMETER FOR SENSITIVE AND ROBUST USE\n\n"
            "(57) Abstract: A miniature instrument."
        ),
        tmp_path / "patent.pdf",
    )

    assert title == "MINIATURIZED SPECTROMETER FOR SENSITIVE AND ROBUST USE"


def test_doi_extraction_ignores_distinct_reference_dois() -> None:
    parser = PyMuPDFParser()
    raw_text = (
        "A review without its own DOI.\n\nReferences\n\n"
        "First citation DOI: 10.1039/b618104j\n\n"
        "Second citation DOI: 10.4161/cbt.4.2.1440"
    )

    assert parser._extract_doi(raw_text) is None


def test_doi_extraction_accepts_repeated_document_identity_after_references() -> None:
    parser = PyMuPDFParser()
    raw_text = (
        "Review article.\n\nReferences\n\n"
        "10.1126/science.aaa0980\n\n"
        "DOI: 10.1126/science.aaa0980\n\nThe dark side of cosmology"
    )

    assert parser._extract_doi(raw_text) == "10.1126/science.aaa0980"
