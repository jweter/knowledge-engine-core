"""Loopback-only HTTP fixture server for the ke-online-evidence/v1 integration proof.

Serves the same three fixed, documented page shapes the online-evidence contract's
end-to-end test exercises against ``ke online-research``/``ke online-evidence-validate``:
one retrievable/citable page, one HTTP 500 endpoint, and one response over
``MAX_RESPONSE_BYTES``. ``tests/test_online_cli_end_to_end.py`` starts this exact server
instead of keeping a second, private copy of the page-serving logic, and the
``ke online-evidence-fixture-server`` command (``knowledge_engine/entrypoint.py``) exposes
it as a standalone process so knowledge-engine-ai and knowledge-engine-web can run the real
``ke online-research`` to ``ke online-evidence-validate`` pipeline against it in their own
CI, instead of mocking the Core CLI boundary. See ``docs/online_evidence_contract.md``.

The three page shapes (paths, status codes and the oversized-vs-``MAX_RESPONSE_BYTES``
relationship) are part of the contract and additive-only: a future change may add a new
page shape, but never remove or change the meaning of ``/good``, ``/broken`` or ``/huge``.
"""

from __future__ import annotations

import json
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TextIO

GOOD_PATH = "/good"
BROKEN_PATH = "/broken"
HUGE_PATH = "/huge"

GOOD_TEXT = (
    "<html><body><h1>Trial</h1>"
    "<p>Semaglutide reduced body weight by 15.2% versus placebo over 68 weeks.</p>"
    "<p>Recruitment was national.</p></body></html>"
)
MAX_RESPONSE_BYTES = 100_000  # matches the --max-response-mb 0.1 bound used against it
HUGE_BYTES = 150_000  # strictly over MAX_RESPONSE_BYTES


class FixtureRequestHandler(BaseHTTPRequestHandler):
    """Serves the three fixed, documented fixture page shapes."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler's own naming)
        if self.path == GOOD_PATH:
            body, status, content_type = GOOD_TEXT.encode("utf-8"), 200, "text/html; charset=utf-8"
        elif self.path == HUGE_PATH:
            body, status, content_type = b"w" * HUGE_BYTES, 200, "text/plain"
        elif self.path == BROKEN_PATH:
            body, status, content_type = b"boom", 500, "text/plain"
        else:
            body, status, content_type = b"not found", 404, "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        pass  # keep stdout reserved for the one JSON announcement line


def create_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Build the loopback-only fixture server, bound to an ephemeral port by default."""

    return ThreadingHTTPServer((host, port), FixtureRequestHandler)


def fixture_pages(host: str, port: int) -> dict[str, str]:
    """The fixed, documented page URLs this server serves, keyed by page shape name."""

    base = f"http://{host}:{port}"
    return {
        "retrievable": f"{base}{GOOD_PATH}",
        "http_500": f"{base}{BROKEN_PATH}",
        "oversized": f"{base}{HUGE_PATH}",
    }


class _ShutdownRequested(Exception):
    """Raised from the SIGTERM handler to interrupt the blocking stdin read."""


def run_fixture_server(stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
    """Start the fixture server, announce it, then block until stdin closes or SIGTERM.

    Prints ``{"port": <int>, "pages": {"retrievable": ..., "http_500": ..., "oversized":
    ...}}`` as one JSON line to ``stdout`` once the server is actually accepting
    connections, then blocks until ``stdin`` is closed (EOF) or the process receives
    SIGTERM, and shuts the server down cleanly before returning 0.
    """

    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout

    server = create_server()
    host, port = str(server.server_address[0]), int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def _handle_sigterm(_signum: int, _frame: object) -> None:
        raise _ShutdownRequested

    previous_handler = signal.signal(signal.SIGTERM, _handle_sigterm)
    try:
        stdout.write(json.dumps({"port": port, "pages": fixture_pages(host, port)}) + "\n")
        stdout.flush()
        try:
            while stdin.readline():
                pass
        except _ShutdownRequested:
            pass
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    return 0


__all__ = [
    "BROKEN_PATH",
    "GOOD_PATH",
    "GOOD_TEXT",
    "HUGE_BYTES",
    "HUGE_PATH",
    "MAX_RESPONSE_BYTES",
    "FixtureRequestHandler",
    "create_server",
    "fixture_pages",
    "run_fixture_server",
]
