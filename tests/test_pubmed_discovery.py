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


def _s3_listing_response(pmcid: str, *versions: int) -> FakeResponse:
    prefixes = "".join(
        f"<CommonPrefixes><Prefix>{pmcid}.{version}/</Prefix></CommonPrefixes>"
        for version in versions
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"{prefixes}</ListBucketResult>"
    ).encode()
    return FakeResponse(200, body, {})


def _pmc_cloud_metadata_response(
    *,
    pmcid: str,
    version: int,
    is_pmc_openaccess: bool = True,
    license_code: str | None = "CC BY",
    pdf_key: str | None = "article.pdf",
    xml_key: str | None = "article.xml",
) -> FakeResponse:
    payload: dict[str, object] = {
        "pmcid": pmcid,
        "version": version,
        "is_pmc_openaccess": is_pmc_openaccess,
        "license_code": license_code,
    }
    if pdf_key is not None:
        payload["pdf_url"] = f"s3://pmc-oa-opendata/{pmcid}.{version}/{pdf_key}"
    if xml_key is not None:
        payload["xml_url"] = f"s3://pmc-oa-opendata/{pmcid}.{version}/{xml_key}"
    return FakeResponse(200, json.dumps(payload).encode(), {})


def test_discovery_returns_stable_reviewable_candidates() -> None:
    transport = FakeTransport(
        [
            _search_response("222", "111"),
            _metadata_response(),
            _id_converter_response(
                {"requested-id": "222", "pmid": 222, "pmcid": "PMC999"},
                {"requested-id": "111", "pmid": 111, "errmsg": "not found"},
            ),
            _s3_listing_response("PMC999", 1),
            _pmc_cloud_metadata_response(
                pmcid="PMC999",
                version=1,
                license_code="CC BY",
                pdf_key="PMC999.1.pdf",
                xml_key="PMC999.1.xml",
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
    assert result.candidates[0].pdf_url == (
        "https://pmc-oa-opendata.s3.amazonaws.com/PMC999.1/PMC999.1.pdf"
    )
    assert result.candidates[0].xml_url == (
        "https://pmc-oa-opendata.s3.amazonaws.com/PMC999.1/PMC999.1.xml"
    )
    assert result.candidates[0].metadata_source == "pubmed_efetch"
    assert result.candidates[0].pmcid_source == "pmc_id_converter"
    assert result.candidates[0].oa_source == "pmc_cloud_service"
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
    assert "prefix=PMC999." in transport.urls[3]
    assert "list-type=2" in transport.urls[3]
    assert transport.urls[4].endswith("/metadata/PMC999.1.json")


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


def test_discovery_rejects_pmc_cloud_metadata_that_does_not_reconcile() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            _s3_listing_response("PMC999", 1),
            _pmc_cloud_metadata_response(pmcid="PMC1000", version=1),
        ]
    )

    with pytest.raises(NcbiDiscoveryError, match="did not reconcile"):
        _service(transport).discover("semaglutide obesity", limit=1)


def test_discovery_treats_non_open_access_record_as_absent() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            _s3_listing_response("PMC999", 1),
            _pmc_cloud_metadata_response(
                pmcid="PMC999", version=1, is_pmc_openaccess=False, license_code="TDM"
            ),
        ]
    )

    result = _service(transport).discover("semaglutide obesity", limit=1)

    assert result.candidates[0].pmcid == "PMC999"
    assert result.candidates[0].open_access is False
    assert result.candidates[0].license is None
    assert result.candidates[0].oa_source is None
    assert result.candidates[0].status == "metadata_only"


def test_discovery_uses_latest_version_when_multiple_exist() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            _s3_listing_response("PMC999", 1, 2),
            _pmc_cloud_metadata_response(pmcid="PMC999", version=2, pdf_key="PMC999.2.pdf"),
        ]
    )

    result = _service(transport).discover("semaglutide obesity", limit=1)

    assert result.candidates[0].pdf_url == (
        "https://pmc-oa-opendata.s3.amazonaws.com/PMC999.2/PMC999.2.pdf"
    )
    assert transport.urls[4].endswith("/metadata/PMC999.2.json")


def test_discovery_treats_missing_pmc_cloud_listing_as_absent() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            _s3_listing_response("PMC999"),
        ]
    )

    result = _service(transport).discover("semaglutide obesity", limit=1)

    assert result.candidates[0].pmcid == "PMC999"
    assert result.candidates[0].open_access is False
    assert result.candidates[0].oa_source is None
    assert result.candidates[0].status == "metadata_only"


def test_discovery_rejects_malformed_pmc_cloud_listing() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            FakeResponse(
                200,
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<CommonPrefixes><Prefix>PMC999.latest/</Prefix></CommonPrefixes>"
                b"</ListBucketResult>",
                {},
            ),
        ]
    )

    with pytest.raises(NcbiDiscoveryError, match="did not reconcile"):
        _service(transport).discover("semaglutide obesity", limit=1)


def test_discovery_rejects_unexpected_object_uri_in_pmc_cloud_metadata() -> None:
    transport = FakeTransport(
        [
            _search_response("222"),
            _metadata_response(),
            _id_converter_response({"requested-id": "222", "pmid": 222, "pmcid": "PMC999"}),
            _s3_listing_response("PMC999", 1),
            FakeResponse(
                200,
                json.dumps(
                    {
                        "pmcid": "PMC999",
                        "version": 1,
                        "is_pmc_openaccess": True,
                        "license_code": "CC BY",
                        "pdf_url": "https://attacker.example/PMC999.1.pdf",
                    }
                ).encode(),
                {},
            ),
        ]
    )

    with pytest.raises(NcbiDiscoveryError, match="unexpected object URI"):
        _service(transport).discover("semaglutide obesity", limit=1)


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
