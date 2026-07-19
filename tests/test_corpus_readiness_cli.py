from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.corpus_readiness_cli import app


def test_cli_writes_sanitized_readiness_report(tmp_path: Path) -> None:
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
                "license_type": "CC-BY",
                "usage_status": "approved_open_access",
                "inclusion_status": "included",
            }
        )
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 1,
                "items": [
                    {
                        "pmid": "100",
                        "pmcid": "PMC100",
                        "license": "CC BY",
                        "filename": "PMC100.pdf",
                        "byte_count": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "readiness.json"

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "--manifest",
            str(manifest),
            "--receipt",
            str(receipt),
            "--papers-dir",
            str(papers),
            "--expected-count",
            "1",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert "Corpus ready: 1 manifest rows, 1 receipts, 1 PDFs." in result.output
    report = output.read_text(encoding="utf-8")
    assert '"ready": true' in report
    assert str(tmp_path) not in report


def test_existing_output_fails_before_validation(tmp_path: Path) -> None:
    output = tmp_path / "readiness.json"
    output.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "--manifest",
            str(tmp_path / "missing.csv"),
            "--receipt",
            str(tmp_path / "missing.json"),
            "--papers-dir",
            str(tmp_path / "papers"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "already exists" in result.output
