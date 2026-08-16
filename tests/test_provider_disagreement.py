from __future__ import annotations

import json

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.provider_disagreement import (
    build_provider_disagreement_report,
    inspect_provider_disagreements,
)


def _observation(
    provider: str,
    provider_id: str,
    *,
    title: str = "A paper",
    publication_year: int | None = 2025,
    venue: str | None = "Journal A",
    doi: str | None = "10.1000/example",
    open_access: bool | None = True,
    retracted: bool | None = False,
    citation_count: int | None = 10,
) -> ProviderObservation:
    return ProviderObservation(
        provider=provider,
        provider_id=provider_id,
        title=title,
        publication_year=publication_year,
        venue=venue,
        doi=doi,
        open_access=open_access,
        retracted=retracted,
        citation_count=citation_count,
    )


def _candidate(*observations: ProviderObservation, canonical_id: str = "doi:10.1000/example") -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=canonical_id,
        title=observations[0].title,
        doi="10.1000/example",
        observations=observations,
    )


def test_conflicting_observed_metadata_is_reported_in_stable_field_order() -> None:
    candidate = _candidate(
        _observation("PubMed", "1", publication_year=2024, citation_count=7),
        _observation(
            "OpenAlex",
            "W1",
            title="A different paper title",
            publication_year=2025,
            open_access=False,
            retracted=True,
            citation_count=12,
        ),
    )

    disagreements = inspect_provider_disagreements(candidate)

    assert tuple(item.field for item in disagreements) == (
        "title",
        "publication_year",
        "open_access",
        "retracted",
        "citation_count",
    )
    year_assertions = disagreements[1].assertions
    assert tuple((item.provider, item.provider_id, item.value) for item in year_assertions) == (
        ("pubmed", "1", 2024),
        ("openalex", "W1", 2025),
    )


def test_cosmetic_text_and_normalized_doi_differences_are_not_disagreements() -> None:
    candidate = _candidate(
        _observation(
            "PubMed",
            "1",
            title="  A   Paper ",
            venue="JOURNAL A",
            doi="https://doi.org/10.1000/EXAMPLE",
        ),
        _observation(
            "Crossref",
            "10.1000/example",
            title="a paper",
            venue="journal a",
            doi="doi:10.1000/example",
        ),
    )

    assert inspect_provider_disagreements(candidate) == ()


def test_missing_metadata_is_unknown_not_a_conflict() -> None:
    candidate = _candidate(
        _observation("PubMed", "1", open_access=True, retracted=None, citation_count=None),
        _observation("Semantic Scholar", "S1", open_access=None, retracted=None, citation_count=None),
    )

    assert inspect_provider_disagreements(candidate) == ()


def test_report_contains_only_candidates_with_disagreement_and_never_selects_truth() -> None:
    conflicted = _candidate(
        _observation("PubMed", "1", publication_year=2024),
        _observation("Crossref", "10.1000/example", publication_year=2025),
    )
    clean = FederatedCandidate(
        canonical_id="doi:10.2000/clean",
        title="Clean paper",
        doi="10.2000/clean",
        observations=(
            _observation("OpenAlex", "W2", title="Clean paper", doi="10.2000/clean"),
            _observation("Semantic Scholar", "S2", title="Clean paper", doi="10.2000/clean"),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="metadata disagreement"),
        provider_statuses=(
            ProviderStatus("pubmed", ProviderOutcome.SUCCESS, True, result_count=1),
            ProviderStatus("crossref", ProviderOutcome.SUCCESS, True, result_count=1),
        ),
        candidates=(conflicted, clean),
    )

    report = build_provider_disagreement_report(result)
    payload = json.loads(report.to_json())

    assert report.disagreement_count == 1
    assert len(report.candidates) == 1
    assert report.candidates[0].canonical_id == "doi:10.1000/example"
    assert payload["disagreement_count"] == 1
    assertions = payload["candidates"][0]["disagreements"][0]["assertions"]
    assert assertions == [
        {"provider": "pubmed", "provider_id": "1", "value": 2024},
        {"provider": "crossref", "provider_id": "10.1000/example", "value": 2025},
    ]
    assert "preferred" not in payload["candidates"][0]["disagreements"][0]
