from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from http.client import IncompleteRead

import pytest

from knowledge_engine.pubmed_discovery import (
    NcbiDiscoveryError,
    PubmedPmcDiscoveryService,
)


@dataclass
class FakeResponse:
    status_code: int
    body: bytes
    headers: Mapping[str, str]


class FakeTransport:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
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
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _service(
    transport: FakeTransport,
    *,
    max_attempts: int = 3,
    delays: list[float] | None = None,
) -> PubmedPmcDiscoveryService:
    recorded_delays = delays if delays is not None else []
    return PubmedPmcDiscoveryService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=max_attempts,
        sleep=recorded_delays.append,
    )


def _search_response(*pmids: str) -> FakeResponse:
    return FakeResponse(200, json.dumps({"esearchresult": {"idlist": list(pmids)}}).encode(), {})


def _metadata_response() -> FakeResponse:
    return FakeResponse(
        200,
        b"""
        <PubmedArticleSet>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>222</PMID>
              <Article>
                <ArticleTitle>Second title</ArticleTitle>
                <Abstract>
                  <AbstractText Label="BACKGROUND">Adults with obesity were enrolled.</AbstractText>
                  <AbstractText Label="METHODS">
                    Semaglutide therapy was compared with placebo.
                  </AbstractText>
                </Abstract>
                <AuthorList>
                  <Author><ForeName>Ada</ForeName><LastName>Lovelace</LastName></Author>
                  <Author><CollectiveName>Trial Group</CollectiveName></Author>
                </AuthorList>
                <Journal>
                  <JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue>
                  <Title>Journal of Verified Results</Title>
                </Journal>
              </Article>
            </MedlineCitation>
            <PubmedData>
              <ArticleIdList>
                <ArticleId IdType="doi">10.1000/second</ArticleId>
              </ArticleIdList>
            </PubmedData>
          </PubmedArticle>
          <PubmedArticle>
            <MedlineCitation>
              <PMID>111</PMID>
              <Article>
                <ArticleTitle>First <i>trial</i></ArticleTitle>
                <Journal>
                  <JournalIssue>
                    <PubDate><MedlineDate>2023 Spring</MedlineDate></PubDate>
                  </JournalIssue>
                </Journal>
              </Article>
            </MedlineCitation>
            <PubmedData><ArticleIdList /></PubmedData>
          </PubmedArticle>
        </PubmedArticleSet>
        """,
        {},
    )


def _id_converter_response(*records: dict[str, object]) -> FakeResponse:
    return FakeResponse(200, json.dumps({"status": "ok", "records": list(records)}).encode(), {})


def test_discovery_returns_stable_reviewable_candidates() -> None:
    transport = FakeTransport(
        [
            _search_response("222", "111"),
            _metadata_response(),
            _id_converter_response(
                {"requested-id": "222", "pmid": 222, "pmcid": "PMC999"},
                {"requested-id": "111", "pmid": 111, "errmsg": "not found"},
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

    result = _service(transport).discover(
        "semaglutide obesity",
        limit=2,
        retstart=0,
    )

    assert [candidate.pmid for candidate in result.candidates] == ["222", "111"]
    assert result.candidates[0].title == "Second title"
    assert result.candidates[0].abstract == (
        "BACKGROUND: Adults with obesity were enrolled. "
        "METHODS: Semaglutide therapy was compared with placebo."
    )
    assert result.candidates[0].authors == ("Ada Lovelace", "Trial Group")
    assert result.candidates[0].publication_year == 2024
    assert result.candidates[0].venue == "Journal of Verified Results"
    assert result.candidates[0].doi == "10.1000/second"
    assert result.candidates[0].pmcid == "PMC999"
    assert result.candidates[0].open_access is True
    assert result.candidates[0].license == "CC BY"
    assert result.candidates[0].pdf_url == "https://ftp.ncbi.nlm.nih.gov/article.pdf"
    assert result.candidates[0].metadata_source == "pubmed_efetch"
    assert result.candidates[0].pmcid_source == "pmc_id_converter"
    assert result.candidates[0].oa_source == "pmc_oa_service"
    assert result.candidates[1].title == "First trial"
    assert result.candidates[1].abstract is None
    assert result.candidates[1].publication_year == 2023
    assert result.candidates[1].status == "metadata_only"
    assert result.candidates[1].metadata_source == "pubmed_efetch"
    assert result.candidates[1].pmcid_source is None
    assert result.candidates[1].oa_source is None
    assert '"candidate_count": 2' in result.to_json()
    assert '"abstract": "BACKGROUND:' in result.to_json()
    assert '"authors": [' in result.to_json()
    assert "retmax=2" in transport.urls[0]
    assert "retstart=0" in transport.urls[0]
    assert "ids=222%2C111" in transport.urls[2]
    assert "idtype=pmid" in transport.urls[2]
    assert "format=json" in transport.urls[2]
    assert "id=PMC999" in transport.urls[3]


def test_identifier_requests_are_chunked_and_reconciled() -> None:
    pmids = [str(value) for value in range(1, 102)]
    first_records = [
        {"requested-id": pmid, "pmid": int(pmid), "pmcid": f"PMC9{pmid}"} for pmid in pmids[:100]
    ]
    second_records = [
        {
            "requested-id": pmids[100],
            "pmid": int(pmids[100]),
            "pmcid": f"PMC9{pmids[100]}",
        }
    ]
    transport = FakeTransport(
        [
            _id_converter_response(*first_records),
            _id_converter_response(*second_records),
        ]
    )

    result = _service(transport)._link_pmc(pmids)

    assert len(result) == 101
    assert result["1"] == "PMC91"
    assert result["101"] == "PMC9101"
    assert len(transport.urls) == 2
    assert "ids=" in transport.urls[0]
    assert "%2C100" in transport.urls[0]
    assert "101" not in transport.urls[0].split("ids=", 1)[1].split("&", 1)[0]
    assert "ids=101" in transport.urls[1]


def test_identifier_converter_rejects_conflicting_source_identity() -> None:
    transport = FakeTransport(
        [_id_converter_response({"requested-id": "222", "pmid": 111, "pmcid": "PMC999"})]
    )

    with pytest.raises(NcbiDiscoveryError, match="did not reconcile"):
        _service(transport)._link_pmc(["222"])


def test_identifier_converter_rejects_duplicate_records() -> None:
    transport = FakeTransport(
        [
            _id_converter_response(
                {"requested-id": "222", "pmid": 222, "pmcid": "PMC999"},
                {"requested-id": "222", "pmid": 222, "pmcid": "PMC1000"},
            )
        ]
    )

    with pytest.raises(NcbiDiscoveryError, match="did not reconcile"):
        _service(transport)._link_pmc(["222"])


def test_discovery_rejects_mismatched_pmc_oa_identity() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            FakeResponse(
                200,
                b'<OA><records><record id="PMC1000" license="CC BY" /></records></OA>',
                {},
            ),
        ]
    )

    result = _service(transport).discover("semaglutide obesity", limit=1)

    assert result.candidates[0].pmcid == "PMC999"
    assert result.candidates[0].open_access is False
    assert result.candidates[0].oa_source is None
    assert result.candidates[0].status == "metadata_only"


def test_discovery_retries_bounded_transient_provider_failures() -> None:
    transport = FakeTransport(
        [
            FakeResponse(429, b"rate limited", {}),
            FakeResponse(503, b"unavailable", {}),
            _search_response(),
        ]
    )

    result = _service(transport, max_attempts=3).discover("semaglutide obesity", limit=1)

    assert result.candidates == ()
    assert len(transport.urls) == 3


def test_discovery_retries_incomplete_response_bodies() -> None:
    transport = FakeTransport(
        [
            IncompleteRead(b"partial"),
            _search_response(),
        ]
    )

    result = _service(transport, max_attempts=2).discover("semaglutide obesity", limit=1)

    assert result.candidates == ()
    assert len(transport.urls) == 2


def test_discovery_rejects_unbounded_or_empty_requests() -> None:
    service = _service(FakeTransport([]))

    with pytest.raises(ValueError, match="must not be empty"):
        service.discover(" ", limit=1)
    with pytest.raises(ValueError, match="between 1 and 100"):
        service.discover("semaglutide", limit=101)
    with pytest.raises(ValueError, match="non-negative"):
        service.discover("semaglutide", limit=1, retstart=-1)


def test_discovery_sanitizes_provider_failures() -> None:
    service = _service(
        FakeTransport([FakeResponse(503, b"private", {})]),
        max_attempts=1,
    )

    with pytest.raises(NcbiDiscoveryError, match="non-success") as error:
        service.discover("semaglutide", limit=1)

    assert "private" not in str(error.value)
    assert "503" in str(error.value)


def test_discovery_backs_off_exponentially_between_retries() -> None:
    transport = FakeTransport(
        [
            FakeResponse(429, b"rate limited", {}),
            FakeResponse(503, b"unavailable", {}),
            FakeResponse(429, b"rate limited", {}),
        ]
    )
    delays: list[float] = []
    service = PubmedPmcDiscoveryService(
        transport,
        request_interval_seconds=0.0,
        max_attempts=3,
        retry_backoff_seconds=2.0,
        sleep=delays.append,
    )

    with pytest.raises(NcbiDiscoveryError, match="non-success") as error:
        service.discover("semaglutide", limit=1)

    assert delays == [2.0, 4.0]
    assert "429" in str(error.value)
    assert "3 attempt" in str(error.value)


def test_discovery_rejects_negative_retry_backoff() -> None:
    with pytest.raises(ValueError, match="retry backoff"):
        PubmedPmcDiscoveryService(FakeTransport([]), retry_backoff_seconds=-1.0)


def test_discovery_rejects_malformed_search_payload() -> None:
    service = _service(FakeTransport([FakeResponse(200, b"{}", {})]))

    with pytest.raises(NcbiDiscoveryError, match="search response was malformed"):
        service.discover("semaglutide", limit=1)
