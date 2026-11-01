from knowledge_engine.extraction.sections import detect_sections
from knowledge_engine.parser import ParsedPage


def _types(text: str) -> list[str]:
    return [span.section_type for span in detect_sections([ParsedPage(page_number=1, text=text)])]


def test_methodology_heading_is_a_methods_section() -> None:
    assert _types("Methodology\nWe sampled.\nResults\nIt worked.\n") == ["methods", "results"]


def test_patients_and_subjects_methods_headings_are_methods_sections() -> None:
    assert _types("2. Patients and Methods\nCohort.\n") == ["methods"]
    assert _types("Subjects and methods: adults aged 40-65.\n") == ["methods"]


def test_existing_methods_headings_still_match_and_prose_does_not() -> None:
    assert _types("Materials and Methods\nHow.\nStudy design\nWhy.\n") == ["methods", "methods"]
    assert _types("Our methodology was simple.\n") == []
