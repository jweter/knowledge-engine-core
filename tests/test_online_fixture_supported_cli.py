"""Public Core CLI integration fixture; no private tests/test_online_cli_harness imports."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from knowledge_engine.online_evidence_fixture_server import MAX_RESPONSE_BYTES

CLI = [sys.executable, "-c", "from knowledge_engine.command_surface import app; app()"]
REPO = Path(__file__).resolve().parents[1]


def run_cli(
    args: list[str], work: Path, *, allow_fixture: bool
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join((str(REPO), env.get("PYTHONPATH", "")))
    env.pop("KE_ALLOW_LOOPBACK_FIXTURE", None)
    if allow_fixture:
        env["KE_ALLOW_LOOPBACK_FIXTURE"] = "1"
    return subprocess.run(
        [*CLI, *args],
        cwd=work,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


def test_installed_cli_requires_explicit_fixture_mode(tmp_path: Path) -> None:
    args = [
        "online-research",
        "Does semaglutide reduce weight?",
        "--fixture-server-port",
        "33333",
        "--cache-dir",
        str(tmp_path / "cache"),
        "--ledger-root",
        str(tmp_path / "ledger"),
        "--output",
        str(tmp_path / "out.json"),
    ]
    refused = run_cli(args, tmp_path, allow_fixture=False)
    assert refused.returncode != 0
    assert "KE_ALLOW_LOOPBACK_FIXTURE=1" in (refused.stderr + refused.stdout)
    assert not (tmp_path / "out.json").exists()
    assert not (tmp_path / "cache").exists()


def test_installed_cli_retrieves_fixture_and_validates_without_private_harness(
    tmp_path: Path,
) -> None:
    server = subprocess.Popen(
        [*CLI, "online-evidence-fixture-server"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join((str(REPO), os.environ.get("PYTHONPATH", ""))),
        },
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert server.stdin is not None and server.stdout is not None
    try:
        announcement = json.loads(server.stdout.readline())
        port = announcement["port"]
        assert set(announcement["pages"]) == {"retrievable", "http_500", "oversized"}
        assert all(
            url.startswith(f"http://127.0.0.1:{port}/") for url in announcement["pages"].values()
        )

        cache = tmp_path / "cache"
        ledger = tmp_path / "ledger"
        bundle = tmp_path / "evidence.json"
        research = run_cli(
            [
                "online-research",
                "Does semaglutide reduce body weight versus placebo?",
                "--fixture-server-port",
                str(port),
                "--cache-dir",
                str(cache),
                "--ledger-root",
                str(ledger),
                "--output",
                str(bundle),
                "--max-response-mb",
                "0.1",
                "--cache-max-mb",
                "1",
            ],
            tmp_path,
            allow_fixture=True,
        )
        assert research.returncode == 0, research.stdout + research.stderr
        data = json.loads(bundle.read_text(encoding="utf-8"))
        sources = {s["source_id"]: s for s in data["sources"]}
        assert {sid: s["status"] for sid, s in sources.items()} == {
            "doi:10.1/good": "retrieved",
            "doi:10.1/broken": "failed",
            "doi:10.1/huge": "failed",
        }
        assert "HTTP 500" in sources["doi:10.1/broken"]["failure_reason"]
        assert f"exceeds {MAX_RESPONSE_BYTES} bytes" in sources["doi:10.1/huge"]["failure_reason"]
        good = sources["doi:10.1/good"]
        cached = (cache / f"{good['content_sha256']}.txt").read_text(encoding="utf-8")
        assert data["excerpts"]
        assert all(
            x["source_id"] == "doi:10.1/good"
            and cached[x["char_start"] : x["char_end"]] == x["text"]
            for x in data["excerpts"]
        )
        discovery = json.loads(
            (tmp_path / "evidence.json.discovery.json").read_text(encoding="utf-8")
        )
        assert discovery["test_fixture"] is True
        verified = run_cli(
            [
                "online-evidence-validate",
                str(bundle),
                "--contents-dir",
                str(cache),
            ],
            tmp_path,
            allow_fixture=False,
        )
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
