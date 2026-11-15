"""Proof that `ke online-evidence-fixture-server` is a standalone, documented integration
fixture: spawned as its own subprocess (not a pytest-managed server, not a Python import),
it announces its port and page URLs on stdout, and the real `ke online-research` ->
`ke online-evidence-validate` pipeline runs against it exactly as it does against the
pytest-managed server in tests/test_online_cli_end_to_end.py.

This proves the Core half only: knowledge-engine-ai and knowledge-engine-web still owe
their own non-mocked subprocess test against this same command.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from knowledge_engine.online_evidence_fixture_server import MAX_RESPONSE_BYTES
from tests.test_online_cli_end_to_end import _ke


def test_online_evidence_fixture_server_cli_serves_the_proof_and_shuts_down_cleanly(
    tmp_path: Path,
) -> None:
    server = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys\nfrom knowledge_engine.entrypoint import app\napp(args=sys.argv[1:])\n",
            "online-evidence-fixture-server",
        ],
        cwd=tmp_path,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert server.stdin is not None
    assert server.stdout is not None
    try:
        announcement = server.stdout.readline()
        payload = json.loads(announcement)
        port = payload["port"]
        pages = payload["pages"]
        assert pages == {
            "retrievable": f"http://127.0.0.1:{port}/good",
            "http_500": f"http://127.0.0.1:{port}/broken",
            "oversized": f"http://127.0.0.1:{port}/huge",
        }

        work = tmp_path / "work"
        out = tmp_path / "out"
        work.mkdir()
        out.mkdir()
        cache, ledger, bundle_path = out / "cache", out / "ledger", out / "bundle.json"

        researched = _ke(
            [
                "online-research",
                "Does semaglutide reduce body weight versus placebo?",
                "--cache-dir",
                str(cache),
                "--output",
                str(bundle_path),
                "--ledger-root",
                str(ledger),
                "--max-response-mb",
                "0.1",
                "--cache-max-mb",
                "1",
            ],
            work,
            out / "imports-research.json",
            port,
        )
        assert researched.returncode == 0, researched.stdout + researched.stderr

        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        sources = {source["source_id"]: source for source in bundle["sources"]}
        assert {sid: s["status"] for sid, s in sources.items()} == {
            "doi:10.1/good": "retrieved",
            "doi:10.1/broken": "failed",
            "doi:10.1/huge": "failed",
        }
        assert "HTTP 500" in sources["doi:10.1/broken"]["failure_reason"]
        assert f"exceeds {MAX_RESPONSE_BYTES} bytes" in sources["doi:10.1/huge"]["failure_reason"]

        good = sources["doi:10.1/good"]
        cached = (cache / f"{good['content_sha256']}.txt").read_bytes().decode("utf-8")
        assert bundle["excerpts"]
        for excerpt in bundle["excerpts"]:
            assert excerpt["source_id"] == "doi:10.1/good"
            assert cached[excerpt["char_start"] : excerpt["char_end"]] == excerpt["text"]

        validate_args = ["online-evidence-validate", str(bundle_path), "--contents-dir", str(cache)]
        verified = _ke(validate_args, work, out / "imports-validate.json", None)
        assert verified.returncode == 0, verified.stdout + verified.stderr
        assert "verified against retrieved content" in " ".join(verified.stdout.split())
    finally:
        server.stdin.close()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.terminate()
            server.wait(timeout=5)
    assert server.returncode == 0
