from pathlib import Path

import fitz

from knowledge_engine.parser import PyMuPDFParser


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
