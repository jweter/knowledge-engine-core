from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from knowledge_engine.citation_traversal import CitationDirection
from knowledge_engine.federated_discovery import ProviderOutcome
from knowledge_engine.semantic_scholar_provider import (
    SemanticScholarProvider,
    TransportResponse,
)


@dataclass
class FakeTransport:
    response: TransportResponse
    calls: list[tuple[str, dict[str, str], float, int]] = field(default_factory=list)

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        self.calls.append((url, dict(headers), timeout_seconds, max_response_bytes))
        return self.response


def _response(payload: object, status_code: int = 200) -> TransportResponse:
    return TransportResponse(
        status_code=status_code,
        body=json.dumps(payload).encode(),
        headers={},
    )


def _paper(paper_id: str = "related-1") -> dict[str, object]:
    return {
        "paperId": paper_id,
        "title": "Related paper",
        "authors": [{"authorId": "author-1", "name": "Ada Example"}],
        "year": 2024,
        "venue": "Journal of Related Work",
        "abstract": "Related source abstract.",
        "externalIds": {"DOI": "10.1000/related"},
        "url": f"https://www.semanticscholar.org/paper/{paper_id}",
        "openAccessPdf": None,
        "citationCount": 4,
    }


def test_references_returns_candidates_with_replayable_edge_provenance() -> None:
    transport = FakeTransport(
        _response(
            {
                "offset": 20,
                "next": 21,
                "data": [{"citedPaper": _paper()}],
            }
        )
    )
    provider = SemanticScholarProvider(
        transport=transport,
        api_key="secret-key",
        clock=lambda: datetime(2026, 8, 16, 3, 15, tzinfo=UTC),
    )

    result = provider.references(
        "https://doi.org/10.2000/Seed",
        limit=5,
        offset=20,
    )

    assert result.query.direction is CitationDirection.REFERENCES
    assert result.query.limit == 5
    assert result.query.offset == 20
    assert result.provider_status.outcome is ProviderOutcome.SUCCESS
    assert result.provider_status.result_count == 1
    assert result.next_offset == 21
    assert result.candidates[0].observations[0].semantic_scholar_id == "related-1"
    assert result.candidates[0].doi == "10.1000/related"

    edge = result.edges[0]
    assert edge.provider == "semantic_scholar"
    assert edge.seed_identifier == "https://doi.org/10.2000/Seed"
    assert edge.related_provider_id == "related-1"
    assert edge.direction is CitationDirection.REFERENCES
    assert edge.retrieved_at == "2026-08-16T03:15:00+00:00"

    url, headers, _, _ = transport.calls[0]
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert parsed.path.endswith("/paper/DOI:10.2000%2Fseed/references")
    assert params["limit"] == ["5"]
    assert params["offset"] == ["20"]
    assert "tldr" not in params["fields"][0].lower()
    assert headers["x-api-key"] == "secret-key"
    assert "secret-key" not in url


def test_citations_uses_citing_paper_and_preserves_direction() -> None:
    transport = FakeTransport(
        _response(
            {
                "offset": 0,
                "data": [{"citingPaper": _paper("citing-1")}],
            }
        )
    )

    result = SemanticScholarProvider(transport=transport).citations("seed-paper", limit=1)

    assert result.query.direction is CitationDirection.CITATIONS
    assert result.provider_status.outcome is ProviderOutcome.SUCCESS
    assert result.candidates[0].observations[0].provider_id == "citing-1"
    assert result.edges[0].related_provider_id == "citing-1"
    assert result.edges[0].direction is CitationDirection.CITATIONS
    assert urlparse(transport.calls[0][0]).path.endswith("/paper/seed-paper/citations")


def test_empty_traversal_page_is_explicit_empty_outcome() -> None:
    transport = FakeTransport(_response({"offset": 0, "data": []}))

    result = SemanticScholarProvider(transport=transport).references("seed-paper", limit=10)

    assert result.provider_status.outcome is ProviderOutcome.EMPTY
    assert result.provider_status.result_count == 0
    assert result.candidates == ()
    assert result.edges == ()


def test_traversal_rejects_provider_page_larger_than_requested_bound() -> None:
    transport = FakeTransport(
        _response(
            {
                "data": [
                    {"citedPaper": _paper("one")},
                    {"citedPaper": _paper("two")},
                ]
            }
        )
    )

    result = SemanticScholarProvider(transport=transport).references("seed", limit=1)

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "oversized_result_page"
    assert result.candidates == ()
    assert result.edges == ()


def test_traversal_fails_closed_on_malformed_edge_payload() -> None:
    transport = FakeTransport(_response({"data": [{"citedPaper": None}]}))

    result = SemanticScholarProvider(transport=transport).references("seed")

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "malformed_response"


def test_missing_seed_is_distinct_from_valid_empty_page() -> None:
    transport = FakeTransport(_response({}, status_code=404))

    result = SemanticScholarProvider(transport=transport).references("missing-seed")

    assert result.provider_status.outcome is ProviderOutcome.FAILED
    assert result.provider_status.reason == "seed_not_found"


def test_traversal_surfaces_rate_limit_without_candidates() -> None:
    transport = FakeTransport(_response({}, status_code=429))

    result = SemanticScholarProvider(transport=transport).citations("seed")

    assert result.provider_status.outcome is ProviderOutcome.RATE_LIMITED
    assert result.provider_status.reason == "rate_limited"
    assert result.candidates == ()
