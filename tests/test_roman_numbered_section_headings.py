from knowledge_engine.extraction.sections import detect_sections
from knowledge_engine.parser import ParsedPage


def _types(text: str) -> list[str]:
    return [span.section_type for span in detect_sections([ParsedPage(page_number=1, text=text)])]


def test_roman_numbered_headings_are_recognized() -> None:
    text = "I. Introduction\nWhy.\nII. Methods\nHow.\nIII. RESULTS\nWhat.\nIV. Discussion\nSo.\n"
    assert _types(text) == ["introduction", "methods", "results", "discussion"]


def test_roman_numbered_inline_label_is_recognized() -> None:
    assert _types("V. Conclusions: the effect was small.\n") == ["conclusion"]


def test_digit_numbering_and_unnumbered_headings_still_match() -> None:
    assert _types("2. Methods\nHow.\n3.1 Results\nWhat.\nReferences\n") == [
        "methods",
        "results",
        "references",
    ]


def test_roman_numbering_does_not_make_combined_or_mid_sentence_headings_match() -> None:
    assert _types("II. Results and Discussion\nText.\nIn results we saw more.\n") == []
