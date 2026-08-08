from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "reacquire_corpus_pdfs.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reacquire_corpus_pdfs", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reacquire = _load_module()


def test_pmc_cloud_pdf_url_converts_s3_uri_to_https() -> None:
    raw = "s3://pmc-oa-opendata/PMC9515581.1/PMC9515581.1.pdf?md5=51a34527d8578b580d95971b28d42b93"

    result = reacquire._pmc_cloud_pdf_url(raw)

    assert result == (
        "https://pmc-oa-opendata.s3.amazonaws.com/PMC9515581.1/PMC9515581.1.pdf"
        "?md5=51a34527d8578b580d95971b28d42b93"
    )


def test_pmc_cloud_pdf_url_preserves_key_without_query_string() -> None:
    raw = "s3://pmc-oa-opendata/PMC1.1/PMC1.1.pdf"

    result = reacquire._pmc_cloud_pdf_url(raw)

    assert result == "https://pmc-oa-opendata.s3.amazonaws.com/PMC1.1/PMC1.1.pdf"


def test_pmc_cloud_pdf_url_rejects_non_s3_scheme() -> None:
    with pytest.raises(reacquire.RecoveryError, match="non-allowlisted"):
        reacquire._pmc_cloud_pdf_url("https://evil.example/PMC1.1/PMC1.1.pdf")


def test_pmc_cloud_pdf_url_rejects_unexpected_bucket() -> None:
    with pytest.raises(reacquire.RecoveryError, match="non-allowlisted"):
        reacquire._pmc_cloud_pdf_url("s3://some-other-bucket/PMC1.1/PMC1.1.pdf")


def test_pmc_cloud_pdf_url_rejects_empty_key() -> None:
    with pytest.raises(reacquire.RecoveryError, match="empty PDF object key"):
        reacquire._pmc_cloud_pdf_url("s3://pmc-oa-opendata/")


def test_normalize_doi_strips_known_prefixes() -> None:
    assert reacquire.normalize_doi("https://doi.org/10.1000/Example") == "10.1000/example"
    assert reacquire.normalize_doi("doi:10.1000/Example.") == "10.1000/example"
    assert reacquire.normalize_doi(None) is None
    assert reacquire.normalize_doi("   ") is None


def test_safe_filename_accepts_pdf_basename() -> None:
    assert reacquire.safe_filename("papers/corpora/glp1_weight_loss/PMC123.pdf", 7) == "PMC123.pdf"


def test_safe_filename_falls_back_for_unsafe_names() -> None:
    assert reacquire.safe_filename("../../etc/passwd", 7) == "paper-7.pdf"
    assert reacquire.safe_filename("no-extension", 8) == "paper-8.pdf"


def test_sha256_file_matches_known_digest(tmp_path: Path) -> None:
    target = tmp_path / "sample.pdf"
    target.write_bytes(b"%PDF-1.4 sample content")

    import hashlib

    expected = hashlib.sha256(b"%PDF-1.4 sample content").hexdigest()
    assert reacquire.sha256_file(target) == expected


class _StubClient:
    """Stand-in for HttpClient that routes canned responses by URL substring."""

    def __init__(self, responses: dict[str, bytes]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, *, max_bytes: int, accept: str) -> bytes:
        self.calls.append(url)
        for substring, payload in self.responses.items():
            if substring in url:
                return payload
        raise AssertionError(f"Unexpected URL requested: {url}")


def _listing_xml(pmcid: str, version: int = 1) -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">
  <Name>pmc-oa-opendata</Name>
  <CommonPrefixes><Prefix>{pmcid}.{version}/</Prefix></CommonPrefixes>
</ListBucketResult>""".encode()


def _metadata_json(
    pmcid: str, version: int = 1, *, doi: str | None = None, open_access: bool = True
) -> bytes:
    import json as _json

    payload = {
        "pmcid": pmcid,
        "version": version,
        "is_pmc_openaccess": open_access,
        "license_code": "CC BY",
        "pdf_url": f"s3://pmc-oa-opendata/{pmcid}.{version}/{pmcid}.{version}.pdf?md5=abc",
    }
    if doi is not None:
        payload["doi"] = doi
    return _json.dumps(payload).encode()


def test_resolve_historical_pmcid_returns_none_for_non_pmc_filename() -> None:
    client = _StubClient({})

    result = reacquire.resolve_historical_pmcid(
        client, doi="10.1000/example", filename="paper-7.pdf"
    )

    assert result is None
    assert client.calls == []


def test_resolve_historical_pmcid_resolves_via_the_filenames_own_pmcid() -> None:
    client = _StubClient(
        {
            "list-type": _listing_xml("PMC13319496"),
            "metadata/PMC13319496.1.json": _metadata_json(
                "PMC13319496", doi="10.7759/cureus.111445"
            ),
        }
    )

    result = reacquire.resolve_historical_pmcid(
        client, doi="10.7759/cureus.111445", filename="PMC13319496.pdf"
    )

    assert result is not None
    assert result.provider == "pmc_article_datasets_cloud"
    assert result.pmcid == "PMC13319496"
    assert result.pdf_url.startswith("https://pmc-oa-opendata.s3.amazonaws.com/")


def test_resolve_historical_pmcid_works_without_a_stored_doi() -> None:
    client = _StubClient(
        {
            "list-type": _listing_xml("PMC13292179"),
            "metadata/PMC13292179.1.json": _metadata_json("PMC13292179", doi=None),
        }
    )

    result = reacquire.resolve_historical_pmcid(client, doi=None, filename="PMC13292179.pdf")

    assert result is not None
    assert result.pmcid == "PMC13292179"


def test_resolve_historical_pmcid_returns_none_when_not_open_access() -> None:
    client = _StubClient(
        {
            "list-type": _listing_xml("PMC10000001"),
            "metadata/PMC10000001.1.json": _metadata_json("PMC10000001", open_access=False),
        }
    )

    result = reacquire.resolve_historical_pmcid(client, doi=None, filename="PMC10000001.pdf")

    assert result is None


def test_pmc_resolution_raises_on_expected_doi_mismatch() -> None:
    client = _StubClient(
        {
            "list-type": _listing_xml("PMC10000002"),
            "metadata/PMC10000002.1.json": _metadata_json(
                "PMC10000002", doi="10.1000/actual-paper"
            ),
        }
    )

    with pytest.raises(reacquire.RecoveryError, match="did not match the expected paper identity"):
        reacquire._pmc_resolution(
            client,
            doi="10.1000/actual-paper",
            pmcid="PMC10000002",
            expected_doi="10.1000/wrong-paper",
        )


def test_pmc_resolution_accepts_matching_expected_doi() -> None:
    client = _StubClient(
        {
            "list-type": _listing_xml("PMC10000003"),
            "metadata/PMC10000003.1.json": _metadata_json("PMC10000003", doi="10.1000/same"),
        }
    )

    result = reacquire._pmc_resolution(
        client, doi="10.1000/same", pmcid="PMC10000003", expected_doi="10.1000/same"
    )

    assert result is not None
