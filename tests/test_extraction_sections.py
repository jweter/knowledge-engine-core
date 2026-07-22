from pathlib import Path

import fitz

from knowledge_engine.extraction import (
    SECTION_DETECTION_RULES_VERSION,
    SectionSpan,
    detect_sections,
)
from knowledge_engine.parser import ParsedPage, PyMuPDFParser


def test_empty_pages_produce_no_sections() -> None:
    assert detect_sections([]) == ()


def test_text_with_no_headings_produces_no_sections() -> None:
    pages = [ParsedPage(page_number=1, text="Just an ordinary paragraph of text.")]

    assert detect_sections(pages) == ()


def test_sentence_containing_results_is_not_detected_as_heading() -> None:
    """A false-positive guard: the word appearing mid-sentence must not match."""

    pages = [ParsedPage(page_number=1, text="The results were statistically significant.")]

    assert detect_sections(pages) == ()


def test_detects_single_section_heading() -> None:
    pages = [ParsedPage(page_number=1, text="Results\n\nWe observed a large effect.")]

    spans = detect_sections(pages)

    assert len(spans) == 1
    span = spans[0]
    assert span.section_type == "results"
    assert span.heading_text == "Results"
    assert span.start_page_number == 1
    assert span.start_offset == 0
    assert span.rules_version == SECTION_DETECTION_RULES_VERSION


def test_detects_numbered_heading() -> None:
    pages = [ParsedPage(page_number=1, text="3. Results\n\nWe observed a large effect.")]

    spans = detect_sections(pages)

    assert len(spans) == 1
    assert spans[0].section_type == "results"
    assert spans[0].heading_text == "3. Results"


def test_detects_numbered_references_heading() -> None:
    """References must support numbering like every other section heading;
    otherwise a numbered bibliography is missed and the preceding section's
    span silently swallows the citation text as body content."""

    pages = [ParsedPage(page_number=1, text="Results\n\nEffect seen.\n\n7. References\n\n1. Foo.")]

    spans = detect_sections(pages)

    assert [span.section_type for span in spans] == ["results", "references"]
    assert spans[1].heading_text == "7. References"


def test_detects_multiple_sections_in_document_order() -> None:
    pages = [
        ParsedPage(
            page_number=1,
            text="Methods\n\nWe recruited participants.\n\nResults\n\nWeight decreased.",
        )
    ]

    spans = detect_sections(pages)

    assert [span.section_type for span in spans] == ["methods", "results"]
    assert spans[0].start_offset < spans[1].start_offset
    # The Methods section ends exactly where Results begins.
    assert spans[0].end_page_number == spans[1].start_page_number
    assert spans[0].end_offset == spans[1].start_offset


def test_last_section_extends_to_end_of_last_page() -> None:
    text = "Discussion\n\nThe findings support prior work."
    pages = [ParsedPage(page_number=1, text=text)]

    spans = detect_sections(pages)

    assert len(spans) == 1
    assert spans[0].end_page_number == 1
    assert spans[0].end_offset == len(text)


def test_section_spans_a_page_boundary() -> None:
    pages = [
        ParsedPage(page_number=1, text="Methods\n\nParticipants were recruited from clinics."),
        ParsedPage(
            page_number=2, text="They completed follow-up visits.\n\nResults\n\nEffect seen."
        ),
    ]

    spans = detect_sections(pages)

    assert [span.section_type for span in spans] == ["methods", "results"]
    methods_span = spans[0]
    results_span = spans[1]
    assert methods_span.start_page_number == 1
    assert results_span.start_page_number == 2
    # Methods continues across the page boundary until Results begins on page 2.
    assert methods_span.end_page_number == 2
    assert methods_span.end_offset == results_span.start_offset


def test_section_span_is_frozen_and_hashable() -> None:
    span = SectionSpan(
        section_type="results",
        start_page_number=1,
        start_offset=0,
        end_page_number=1,
        end_offset=10,
        heading_text="Results",
        rules_version=SECTION_DETECTION_RULES_VERSION,
    )

    assert hash(span) is not None


def test_detects_sections_from_real_parser_output(tmp_path: Path) -> None:
    """Integration check: detect_sections works directly on PyMuPDFParser output,
    not just synthetic ParsedPage fixtures."""

    pdf_path = tmp_path / "paper.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text(
        (72, 72),
        (
            "Methods\n"
            "Adults with obesity were randomized to semaglutide or placebo.\n"
            "Results\n"
            "The semaglutide group lost significantly more weight."
        ),
    )
    document.save(pdf_path)
    document.close()

    parsed = PyMuPDFParser().parse(pdf_path)
    spans = detect_sections(parsed.pages)

    assert [span.section_type for span in spans] == ["methods", "results"]
