from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

from knowledge_engine.pubmed_discovery import (
    GetTransport,
    NcbiDiscoveryError,
    PubmedPmcDiscoveryService,
)


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport(GetTransport):
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> FakeResponse:
        del headers, timeout_seconds, max_response_bytes
        self.urls.append(url)
        return self.responses.pop(0)


def test_discovery_returns_stable_reviewable_candidates() -> None:
    transport = FakeTransport(
        [
            FakeResponse(
                200,
                json.dumps({"esearchresult": {"idlist": ["222", "111"]}}).encode(),
                {},
            ),
            FakeResponse(
                200,
                b"""
                <PubmedArticleSet>
                  <PubmedArticle>
                    <MedlineCitation><PMID>222</PMID><Article><ArticleTitle>Second title</ArticleTitle></Article></MedlineCitation>
                    <PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/second</ArticleId></ArticleIdList></PubmedData>
                  </PubmedArticle>
                  <PubmedArticle>
                    <MedlineCitation><PMID>111</PMID><Article><ArticleTitle>First <i>trial</i></ArticleTitle></Article></MedlineCitation>
                    <PubmedData><ArticleIdList /></PubmedData>
                  </PubmedArticle>
                </PubmedArticleSet>
                """,
                {},
            ),
            FakeResponse(
                200,
                json.dumps(
                    {
                        "linksets": [
                            {
                                "ids": ["222"],
                                "linksetdbs": [{"linkname": "pubmed_pmc", "links": ["999"]}],
                            },
                            {"ids": ["111"], "linksetdbs": []},
                        ]
                    }
                ).encode(),
                {},
            ),
            FakeResponse(
                200,
                b"""
                <OA><records><record id="PMC999" license="CC BY">
                  <link format="pdf" href="ftp://ftp.ncbi.nlm.nih.gov/article.pdf" />
                  <link format="tgz" href="ftp://ftp.ncbi.nlm.nih.gov/article.tar.gz" />
                </record></records></OA>
                """,
                {},
            ),
        ]
    )

    result = PubmedPmcDiscoveryService(transport).discover(
        "semaglutide obesity",
        limit=2,
        retstart=0,
    )

    assert [candidate.pmid for candidate in result.candidates] == ["222", "111"]
    assert result.candidates[0].title == "Second title"
    assert result.candidates[0].doi == "10.1000/second"
    assert result.candidates[0].pmcid == "PMC999"
    assert result.candidates[0].open_access is True
    assert result.candidates[0].license == "CC BY"
    assert result.candidates[0].pdf_url == "https://ftp.ncbi.nlm.nih.gov/article.pdf"
    assert result.candidates[1].title == "First trial"
    assert result.candidates[1].status == "metadata_only"
    assert '"candidate_count": 2' in result.to_json()
    assert "retmax=2" in transport.urls[0]
    assert "retstart=0" in transport.urls[0]


def test_discovery_rejects_unbounded_or_empty_requests() -> None:
    service = PubmedPmcDiscoveryService(FakeTransport([]))

    with pytest.raises(ValueError, match="must not be empty"):
        service.discover(" ", limit=1)
    with pytest.raises(ValueError, match="between 1 and 100"):
        service.discover("semaglutide", limit=101)
    with pytest.raises(ValueError, match="non-negative"):
        service.discover("semaglutide", limit=1, retstart=-1)


def test_discovery_sanitizes_provider_failures() -> None:
    service = PubmedPmcDiscoveryService(FakeTransport([FakeResponse(503, b"private", {})]))

    with pytest.raises(NcbiDiscoveryError, match="non-success") as error:
        service.discover("semaglutide", limit=1)

    assert "private" not in str(error.value)


def test_discovery_rejects_malformed_search_payload() -> None:
    service = PubmedPmcDiscoveryService(FakeTransport([FakeResponse(200, b"{}", {})]))

    with pytest.raises(NcbiDiscoveryError, match="search response was malformed"):
        service.discover("semaglutide", limit=1)
