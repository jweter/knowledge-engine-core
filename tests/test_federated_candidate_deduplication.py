from __future__ import annotations

from knowledge_engine.federated_candidate_deduplication import (
    deduplicate_candidates_by_exact_doi,
)
from knowledge_engine.federated_discovery import FederatedCandidate, ProviderObservation


def _candidate(
    provider: str,
    provider_id: str,
    *,
    title: str,
    doi: str | None = None,
    observation_doi: str | None = None,
    publication_year: int | None = None,
) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=f"{provider}:{provider_id}",
        title=title,
        doi=doi,
        publication_year=publication_year,
        observations=(
            ProviderObservation(
                provider=provider,
                provider_id=provider_id,
                title=title,
                doi=observation_doi,
                publication_year=publication_year,
            ),
        ),
    )


def test_exact_normalized_doi_collapses_candidates_and_preserves_observations() -> None:
    pubmed = _candidate(
        "pubmed",
        "123",
        title="First provider title",
        doi="10.1000/ABC",
        observation_doi="10.1000/ABC",
        publication_year=2024,
    )
    crossref = _candidate(
        "crossref",
        "10.1000/abc",
        title="Second provider title",
        doi="https://doi.org/10.1000/abc",
        observation_doi="10.1000/abc",
        publication_year=2025,
    )

    result = deduplicate_candidates_by_exact_doi((pubmed, crossref))

    assert len(result) == 1
    candidate = result[0]
    assert candidate.canonical_id == "doi:10.1000/abc"
    assert candidate.doi == "10.1000/abc"
    assert candidate.title == "First provider title"
    assert candidate.publication_year == 2024
    assert candidate.providers == ("pubmed", "crossref")
    assert tuple(observation.title for observation in candidate.observations) == (
        "First provider title",
        "Second provider title",
    )


def test_observation_only_doi_establishes_canonical_identity() -> None:
    candidate = _candidate(
        "openalex",
        "W1",
        title="Observation DOI",
        observation_doi="doi:10.2000/example",
    )

    result = deduplicate_candidates_by_exact_doi((candidate,))

    assert result[0].canonical_id == "doi:10.2000/example"
    assert result[0].doi == "10.2000/example"


def test_candidates_without_doi_are_not_weakly_merged() -> None:
    first = _candidate("pubmed", "1", title="Same title")
    second = _candidate("openalex", "W2", title="Same title")

    result = deduplicate_candidates_by_exact_doi((first, second))

    assert result == (first, second)


def test_distinct_dois_are_not_merged() -> None:
    first = _candidate("pubmed", "1", title="Paper", doi="10.1/one")
    second = _candidate("crossref", "2", title="Paper", doi="10.1/two")

    result = deduplicate_candidates_by_exact_doi((first, second))

    assert len(result) == 2
    assert result[0].canonical_id == "doi:10.1/one"
    assert result[1].canonical_id == "doi:10.1/two"


def test_internally_conflicting_doi_assertions_are_not_merged() -> None:
    conflicting = _candidate(
        "openalex",
        "W3",
        title="Conflict",
        doi="10.3/one",
        observation_doi="10.3/two",
    )
    matching_other = _candidate(
        "crossref",
        "10.3/one",
        title="Other",
        doi="10.3/one",
    )

    result = deduplicate_candidates_by_exact_doi((conflicting, matching_other))

    assert result[0] is conflicting
    assert result[1].canonical_id == "doi:10.3/one"
    assert len(result) == 2
