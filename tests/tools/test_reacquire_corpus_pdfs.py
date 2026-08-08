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
