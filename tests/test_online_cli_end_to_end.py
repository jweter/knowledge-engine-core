"""Core half of the AI/Web integration proof: question -> validated evidence bundle, via the CLI.

``ke online-research`` and ``ke online-evidence-validate`` run as real subprocesses against a
loopback HTTP source server, with no pre-ingested corpus and the vector stack unimported. The
subprocess runs the shipped Typer app unchanged; ``test_online_cli_harness.py``
installs the only two seams (a stub discovery provider and a loopback connection factory
beneath the production ``SafeHttpsFetcher``), so URL policy, size caps and offsets are the
production code paths.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "test_online_cli_harness.py"
GOOD_TEXT = (
    "<html><body><h1>Trial</h1>"
    "<p>Semaglutide reduced body weight by 15.2% versus placebo over 68 weeks.</p>"
    "<p>Recruitment was national.</p></body></html>"
)
MAX_RESPONSE_BYTES = 100_000  # --max-response-mb 0.1
HUGE_BYTES = 150_000


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/good":
            body, status, kind = GOOD_TEXT.encode(), 200, "text/html; charset=utf-8"
        elif self.path == "/huge":
            body, status, kind = b"w" * HUGE_BYTES, 200, "text/plain"
        else:
            body, status, kind = b"boom", 500, "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass


@pytest.fixture
def source_port() -> Iterator[int]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _ke(
    args: list[str], cwd: Path, report: Path, port: int | None
) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "KE_HARNESS_IMPORT_REPORT": str(report)}
    env.pop("KE_HARNESS_SOURCE_PORT", None)
    if port is not None:
        env["KE_HARNESS_SOURCE_PORT"] = str(port)
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_online_research_cli_end_to_end_on_loopback_without_a_corpus(
    tmp_path: Path, source_port: int
) -> None:
    work = tmp_path / "work"  # the process working directory: must stay empty
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
        source_port,
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
    for refused in ("doi:10.1/broken", "doi:10.1/huge"):
        assert sources[refused]["content_sha256"] is None

    # Excerpts quote only the retrieved source, at offsets that index the cached bytes exactly.
    good = sources["doi:10.1/good"]
    cached = (cache / f"{good['content_sha256']}.txt").read_bytes().decode("utf-8")
    assert bundle["excerpts"]
    for excerpt in bundle["excerpts"]:
        assert excerpt["source_id"] == "doi:10.1/good"
        assert cached[excerpt["char_start"] : excerpt["char_end"]] == excerpt["text"]
    assert any("15.2%" in excerpt["text"] for excerpt in bundle["excerpts"])
    # Nothing but the one retrieved text is held, and nothing oversized was ever cached.
    assert sorted(p.name for p in cache.iterdir()) == [f"{good['content_sha256']}.txt"]

    validate_args = ["online-evidence-validate", str(bundle_path), "--contents-dir", str(cache)]
    verified = _ke(validate_args, work, out / "imports-validate.json", None)
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "verified against retrieved content" in " ".join(verified.stdout.split())

    # Fails closed once the bounded cache is gone: traceability cannot be re-established.
    for entry in cache.iterdir():
        entry.unlink()
    expired = _ke(validate_args, work, out / "imports-expired.json", None)
    assert expired.returncode == 1
    assert "verified against retrieved content" not in " ".join(expired.stdout.split())

    # No corpus: no database, PDF or other artefact appeared in the working directory (or
    # anywhere in the output tree), and the heavy vector stack was never imported.
    assert list(work.rglob("*")) == []
    forbidden_suffixes = {".db", ".sqlite", ".sqlite3", ".pdf", ".faiss", ".index"}
    assert [p for p in out.rglob("*") if p.suffix.lower() in forbidden_suffixes] == []
    for name in ("imports-research.json", "imports-validate.json", "imports-expired.json"):
        assert json.loads((out / name).read_text(encoding="utf-8")) == []
