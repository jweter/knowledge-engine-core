from __future__ import annotations

import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from knowledge_engine.pdf_calibration_cli import app


def test_cli_writes_sanitized_calibration_report(tmp_path: Path) -> None:
    payload = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
    pdfs = tmp_path / "pdfs"
    pdfs.mkdir()
    (pdfs / "PMC1.pdf").write_bytes(payload)
    receipt = tmp_path / "receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "acquired_count": 1,
                "items": [
                    {
                        "pmid": "1",
                        "pmcid": "PMC1",
                        "license": "CC BY",
                        "filename": "PMC1.pdf",
                        "byte_count": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    result = CliRunner().invoke(
        app,
        [
            "inspect",
            "--receipt",
            str(receipt),
            "--pdf-directory",
            str(pdfs),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["sample_count"] == 1
    assert report["items"][0]["filename"] == "PMC1.pdf"
    assert str(tmp_path) not in output.read_text(encoding="utf-8")
    assert "hard failures: 0" in result.stdout
