from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from knowledge_engine.corpus_readiness import CorpusReadinessError, validate_corpus_readiness


def test_matching_license_is_reconciled_and_reported(tmp_path: Path) -> None:
    manifest, receipt, papers = _fixture(tmp_path, manifest_license="CC BY", receipt_license=" cc   by ")

    report = validate_corpus_readiness(
        manifest_path=manifest,
        receipt_paths=(receipt,),
        papers_directory=papers,
        expected_count=1,
    )

    assert report.items[0].license == "CC BY"


def test_license_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest, receipt, papers = _fixture(
        tmp_path,
        manifest_license="CC BY",
        receipt_license="CC BY-NC",
    )

    with pytest.raises(CorpusReadinessError, match="license does not match"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def test_missing_receipt_license_is_rejected(tmp_path: Path) -> None:
    manifest, receipt, papers = _fixture(tmp_path, manifest_license="CC BY", receipt_license=None)

    with pytest.raises(CorpusReadinessError, match="missing required evidence"):
        validate_corpus_readiness(
            manifest_path=manifest,
            receipt_paths=(receipt,),
            papers_directory=papers,
            expected_count=1,
        )


def _fixture(
    tmp_path: Path,
    *,
    manifest_license: str,
    receipt_license: str | None,
) -> tuple[Path, Path, Path]:
    papers = tmp_path / "papers"
    papers.mkdir()
    body = b"%PDF-1.7\nvalidated"
    (papers / "PMC100.pdf").write_bytes(body)

    manifest = tmp_path / "sources.csv"
    with manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "source_id",
                "pmid",
                "other_identifier",
                "local_path",
                "license_type",
                "usage_status",
                "inclusion_status",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_id": "source-1",
                "pmid": "100",
                "other_identifier": "PMC100",
                "local_path": "PMC100.pdf",
                "license_type": manifest_license,
                "usage_status": "approved_open_access",
                "inclusion_status": "included",
            }
        )

    item: dict[str, object] = {
        "pmid": "100",
        "pmcid": "PMC100",
        "filename": "PMC100.pdf",
        "byte_count": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    if receipt_license is not None:
        item["license"] = receipt_license
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps({"schema_version": 1, "acquired_count": 1, "items": [item]}),
        encoding="utf-8",
    )
    return manifest, receipt, papers
