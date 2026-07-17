from __future__ import annotations

from datetime import UTC, datetime

import pytest

from knowledge_engine.metadata_enrichment import (
    MetadataCandidate,
    MetadataField,
    MetadataProvider,
    MetadataProviderResult,
    MetadataQuery,
    classify_candidate,
    normalize_candidate_value,
    validate_candidates,
)


class FakeProvider:
    @property
    def name(self) -> str:
        return "fake"

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        candidate = MetadataCandidate(
            provider=self.name,
            provider_record_id="record-1",
            queried_identifier=query.normalized_doi,
            field="title",
            value="Example Paper",
            normalized_value="example paper",
            retrieved_at=datetime(2026, 7, 17, tzinfo=UTC),
        )
        return MetadataProviderResult(candidates=(candidate,))


def _accepts_provider(provider: MetadataProvider) -> MetadataProvider:
    return provider


def test_fake_provider_satisfies_contract() -> None:
    provider = _accepts_provider(FakeProvider())

    result = provider.lookup(MetadataQuery(doi="https://doi.org/10.1000/ABC"))

    assert provider.name == "fake"
    assert result.candidates[0].queried_identifier == "10.1000/abc"
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("doi", " https://doi.org/10.1000/ABC ", "10.1000/abc"),
        ("title", "  Example   Paper ", "example paper"),
        ("journal", " Journal of Tests ", "journal of tests"),
        ("author", " Jane   Doe ", "jane doe"),
        ("publication_year", " 2024 ", "2024"),
        ("issn", " 1234-5678 ", "1234-5678"),
    ],
)
def test_normalize_candidate_value(
    field: MetadataField,
    value: str,
    expected: str,
) -> None:
    assert normalize_candidate_value(field, value) == expected


def test_candidate_corroborates_protected_value() -> None:
    assert (
        classify_candidate(
            field="title",
            protected_value="Example Paper",
            candidate_value=" example   paper ",
        )
        == "corroborates"
    )


def test_candidate_fills_missing_value() -> None:
    assert (
        classify_candidate(field="journal", protected_value=None, candidate_value="Test Journal")
        == "fills_missing"
    )


def test_candidate_conflict_preserves_difference() -> None:
    assert (
        classify_candidate(
            field="publication_year",
            protected_value="2024",
            candidate_value="2025",
        )
        == "conflicts"
    )


def test_blank_candidate_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        classify_candidate(field="title", protected_value=None, candidate_value="   ")


def test_validate_candidates_accepts_deterministic_normalization() -> None:
    candidate = MetadataCandidate(
        provider="crossref",
        provider_record_id="10.1000/example",
        queried_identifier="10.1000/example",
        field="title",
        value="Example Paper",
        normalized_value="example paper",
        retrieved_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    assert validate_candidates([candidate]) == (candidate,)


def test_validate_candidates_rejects_mismatched_normalization() -> None:
    candidate = MetadataCandidate(
        provider="crossref",
        provider_record_id="10.1000/example",
        queried_identifier="10.1000/example",
        field="title",
        value="Example Paper",
        normalized_value="different",
        retrieved_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="does not match"):
        validate_candidates([candidate])


def test_validate_candidates_rejects_oversized_value() -> None:
    candidate = MetadataCandidate(
        provider="crossref",
        provider_record_id="10.1000/example",
        queried_identifier="10.1000/example",
        field="title",
        value="x" * 4097,
        normalized_value="x" * 4097,
        retrieved_at=datetime(2026, 7, 17, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="4096-character"):
        validate_candidates([candidate])
