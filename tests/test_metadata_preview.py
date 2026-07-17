from __future__ import annotations

from datetime import UTC, datetime

from knowledge_engine.metadata_enrichment import MetadataCandidate
from knowledge_engine.metadata_preview import ProtectedMetadataValue, compare_candidates


def _candidate(*, field: str, value: str, normalized_value: str) -> MetadataCandidate:
    return MetadataCandidate(
        provider="crossref",
        provider_record_id="10.1000/example",
        queried_identifier="10.1000/example",
        field=field,  # type: ignore[arg-type]
        value=value,
        normalized_value=normalized_value,
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )


def test_compare_candidates_marks_missing_local_field() -> None:
    comparisons = compare_candidates(
        [_candidate(field="journal", value="Journal of Tests", normalized_value="journal of tests")],
        [],
    )

    assert len(comparisons) == 1
    assert comparisons[0].disposition == "fills_missing"
    assert comparisons[0].protected_source is None
    assert comparisons[0].protected_value is None


def test_compare_candidates_preserves_corroborating_curated_value() -> None:
    comparisons = compare_candidates(
        [_candidate(field="title", value="Example Paper", normalized_value="example paper")],
        [
            ProtectedMetadataValue(
                source="curated_manifest",
                field="title",
                value=" example   paper ",
            )
        ],
    )

    assert comparisons[0].disposition == "corroborates"
    assert comparisons[0].protected_source == "curated_manifest"
    assert comparisons[0].protected_value == " example   paper "


def test_compare_candidates_preserves_parser_conflict() -> None:
    comparisons = compare_candidates(
        [_candidate(field="publication_year", value="2025", normalized_value="2025")],
        [ProtectedMetadataValue(source="parser", field="publication_year", value="2024")],
    )

    assert comparisons[0].disposition == "conflicts"
    assert comparisons[0].protected_source == "parser"
    assert comparisons[0].protected_value == "2024"


def test_compare_candidates_keeps_multiple_local_owners_visible() -> None:
    comparisons = compare_candidates(
        [_candidate(field="title", value="Example Paper", normalized_value="example paper")],
        [
            ProtectedMetadataValue(
                source="curated_manifest",
                field="title",
                value="Example Paper",
            ),
            ProtectedMetadataValue(
                source="parser",
                field="title",
                value="Different Parser Title",
            ),
            ProtectedMetadataValue(
                source="preferred",
                field="title",
                value="Example Paper",
            ),
        ],
    )

    assert [comparison.protected_source for comparison in comparisons] == [
        "curated_manifest",
        "parser",
        "preferred",
    ]
    assert [comparison.disposition for comparison in comparisons] == [
        "corroborates",
        "conflicts",
        "corroborates",
    ]
