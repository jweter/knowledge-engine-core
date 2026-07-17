from __future__ import annotations

from datetime import UTC, datetime

from knowledge_engine.crossref import parse_crossref_work
from knowledge_engine.metadata_enrichment import MetadataQuery


def test_parse_crossref_work_returns_bounded_candidates() -> None:
    retrieved_at = datetime(2026, 7, 18, tzinfo=UTC)
    payload = {
        "status": "ok",
        "message": {
            "DOI": "10.1000/EXAMPLE",
            "title": [" Example   Paper "],
            "container-title": [" Journal of Tests "],
            "published-print": {"date-parts": [[2024, 3, 1]]},
            "author": [
                {"given": "Jane", "family": "Doe"},
                {"given": "John", "family": "Smith"},
            ],
            "ISSN": ["1234-5678", "8765-4321"],
        },
    }

    result = parse_crossref_work(
        payload,
        query=MetadataQuery(doi="https://doi.org/10.1000/example"),
        retrieved_at=retrieved_at,
    )

    assert result.diagnostics == ()
    assert [(candidate.field, candidate.normalized_value) for candidate in result.candidates] == [
        ("doi", "10.1000/example"),
        ("title", "example paper"),
        ("journal", "journal of tests"),
        ("publication_year", "2024"),
        ("author", "jane doe"),
        ("author", "john smith"),
        ("issn", "1234-5678"),
        ("issn", "8765-4321"),
    ]
    assert all(candidate.provider == "crossref" for candidate in result.candidates)
    assert all(candidate.provider_record_id == "10.1000/EXAMPLE" for candidate in result.candidates)
    assert all(candidate.retrieved_at == retrieved_at for candidate in result.candidates)


def test_parse_crossref_work_uses_date_fallback_order() -> None:
    payload = {
        "message": {
            "published-online": {"date-parts": [[2023, 11, 8]]},
            "issued": {"date-parts": [[2022]]},
        }
    }

    result = parse_crossref_work(
        payload,
        query=MetadataQuery(doi="10.1000/example"),
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    years = [
        candidate.value for candidate in result.candidates if candidate.field == "publication_year"
    ]
    assert years == ["2023"]


def test_parse_crossref_work_ignores_unusable_optional_fields() -> None:
    payload = {
        "message": {
            "DOI": "10.1000/example",
            "title": [],
            "container-title": [None, 42],
            "author": [None, {"given": "", "family": ""}],
            "ISSN": "not-a-list",
            "issued": {"date-parts": [["2024"]]},
        }
    }

    result = parse_crossref_work(
        payload,
        query=MetadataQuery(doi="10.1000/example"),
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    assert [(candidate.field, candidate.value) for candidate in result.candidates] == [
        ("doi", "10.1000/example")
    ]
    assert result.diagnostics == ()


def test_parse_crossref_work_reports_non_object_payload() -> None:
    result = parse_crossref_work(
        [],
        query=MetadataQuery(doi="10.1000/example"),
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    assert result.candidates == ()
    assert result.diagnostics[0].code == "malformed_response"
    assert result.diagnostics[0].message == "Crossref response must be a JSON object."


def test_parse_crossref_work_reports_missing_message() -> None:
    result = parse_crossref_work(
        {"status": "ok"},
        query=MetadataQuery(doi="10.1000/example"),
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    assert result.candidates == ()
    assert result.diagnostics[0].code == "malformed_response"
    assert result.diagnostics[0].message == "Crossref response is missing a work object."


def test_parse_crossref_work_bounds_repeated_values() -> None:
    payload = {
        "message": {
            "author": [{"given": "A", "family": str(index)} for index in range(100)],
            "ISSN": [str(index) for index in range(100)],
        }
    }

    result = parse_crossref_work(
        payload,
        query=MetadataQuery(doi="10.1000/example"),
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    authors = [candidate for candidate in result.candidates if candidate.field == "author"]
    issns = [candidate for candidate in result.candidates if candidate.field == "issn"]
    assert len(authors) == 64
    assert len(issns) == 32
