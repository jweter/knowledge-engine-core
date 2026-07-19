from __future__ import annotations

from dataclasses import dataclass

import pytest

from knowledge_engine.pubmed_batch_discovery import discover_candidate_batch
from knowledge_engine.pubmed_discovery import DiscoveryResult, PubmedCandidate


@dataclass
class FakeDiscoveryService:
    pages: dict[int, tuple[PubmedCandidate, ...]]

    def __post_init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        self.calls.append((query, limit, retstart))
        candidates = self.pages.get(retstart, ())[:limit]
        return DiscoveryResult(
            query=query,
            retstart=retstart,
            limit=limit,
            candidates=candidates,
        )


def _candidate(pmid: str) -> PubmedCandidate:
    return PubmedCandidate(
        pmid=pmid,
        title=f"Paper {pmid}",
        authors=(),
        publication_year=2026,
        venue="Journal",
        doi=None,
        pmcid=None,
        open_access=False,
        license=None,
        pdf_url=None,
        xml_url=None,
        status="metadata_only",
    )


def test_batch_discovery_pages_and_removes_cross_page_duplicates() -> None:
    service = FakeDiscoveryService(
        {
            0: (_candidate("1"), _candidate("2"), _candidate("3")),
            3: (_candidate("3"), _candidate("4")),
            5: (_candidate("5"),),
        }
    )

    result = discover_candidate_batch(
        service,
        "  GLP-1 obesity  ",
        total_limit=5,
        page_size=3,
    )

    assert [candidate.pmid for candidate in result.candidates] == ["1", "2", "3", "4", "5"]
    assert result.query == "GLP-1 obesity"
    assert result.fetched_page_count == 3
    assert result.duplicate_pmids_removed == 1
    assert result.exhausted is False
    assert service.calls == [
        ("GLP-1 obesity", 3, 0),
        ("GLP-1 obesity", 2, 3),
        ("GLP-1 obesity", 1, 5),
    ]
    assert '"candidate_count": 5' in result.to_json()


def test_batch_discovery_stops_on_short_page() -> None:
    service = FakeDiscoveryService({10: (_candidate("10"), _candidate("11"))})

    result = discover_candidate_batch(
        service,
        "liraglutide",
        total_limit=150,
        retstart=10,
        page_size=100,
    )

    assert [candidate.pmid for candidate in result.candidates] == ["10", "11"]
    assert result.exhausted is True
    assert result.fetched_page_count == 1
    assert service.calls == [("liraglutide", 100, 10)]


def test_batch_discovery_rejects_invalid_bounds() -> None:
    service = FakeDiscoveryService({})

    with pytest.raises(ValueError, match="must not be empty"):
        discover_candidate_batch(service, " ", total_limit=1)
    with pytest.raises(ValueError, match="between 1 and 5000"):
        discover_candidate_batch(service, "semaglutide", total_limit=5001)
    with pytest.raises(ValueError, match="between 1 and 100"):
        discover_candidate_batch(service, "semaglutide", total_limit=1, page_size=101)
    with pytest.raises(ValueError, match="non-negative"):
        discover_candidate_batch(service, "semaglutide", total_limit=1, retstart=-1)
