from knowledge_engine.citation_extraction import find_cited_dois


def test_no_heading_returns_empty_list() -> None:
    assert find_cited_dois("Just a plain document with no bibliography at all.") == []


def test_extracts_doi_from_numbered_reference_entry() -> None:
    text = (
        "Introduction text here.\n\n"
        "References\n\n"
        "1. Smith J, Doe A. A study of things. J Med. (2022) 10:1-9. "
        "doi: 10.1038/s41591-022-02026-4\n"
    )
    results = find_cited_dois(text)
    assert len(results) == 1
    assert results[0].doi == "10.1038/s41591-022-02026-4"
    assert "smith" in results[0].raw_snippet.lower()


def test_uses_last_heading_match_not_first() -> None:
    text = (
        "Findings\n\nReferences\n\n"
        "some table row [18]\n\n"
        "Later section.\n\n"
        "References\n\n"
        "1. Real Bibliography Entry. doi: 10.1000/real.doi\n"
    )
    results = find_cited_dois(text)
    assert len(results) == 1
    assert results[0].doi == "10.1000/real.doi"


def test_dedupes_repeated_doi() -> None:
    text = (
        "References\n\n"
        "1. First mention. doi: 10.1000/xyz123\n\n"
        "2. Second mention of the same work. doi: 10.1000/XYZ123.\n"
    )
    results = find_cited_dois(text)
    assert len(results) == 1
    assert results[0].doi == "10.1000/xyz123"


def test_no_dois_in_reference_section_returns_empty_list() -> None:
    text = "References\n\n1. Author-year entry with no DOI at all, Journal, 2020.\n"
    assert find_cited_dois(text) == []
