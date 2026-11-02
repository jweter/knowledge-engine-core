from __future__ import annotations

import http.client
import inspect
import json
import os
import socket
import ssl
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
import knowledge_engine.online_retrieval as retrieval
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.online_evidence import (
    EvidenceExcerpt,
    OnlineEvidenceBundle,
    RetrievalStatus,
    content_sha256,
    verify_against_retrieved_content,
)
from knowledge_engine.online_retrieval import (
    BoundedTextCache,
    CacheBudgetError,
    FetchedPage,
    RetrievalFailure,
    RetrievalLimits,
    SafeHttpsFetcher,
    UnsafeUrlError,
    check_public_https_url,
    extract_text,
    research_online,
    retrieve_source,
    select_excerpts,
)

NOW = datetime(2026, 10, 31, 16, 0, tzinfo=UTC)
PUBLIC = {
    "example.org": "93.184.216.34",
    "cdn.example.org": "93.184.216.35",
    "papers.example.org": "93.184.216.36",
}
HOSTILE = {
    "localhost": "127.0.0.1",
    "internal.example.org": "10.0.0.5",
    "metadata.example.org": "169.254.169.254",
    "lan.example.org": "192.168.1.20",
    "loop6.example.org": "::1",
    "mapped.example.org": "::ffff:127.0.0.1",
    "shared.example.org": "100.64.0.1",
}


def resolver(host: str, _port: int) -> tuple[str, ...]:
    table = {**PUBLIC, **HOSTILE}
    if host == "mixed.example.org":
        return ("93.184.216.34", "10.0.0.9")
    if host not in table:
        raise OSError("no such host")
    return (table[host],)


class FakeResponse:
    def __init__(
        self,
        status: int = 200,
        body: bytes = b"",
        content_type: str | None = "text/plain; charset=utf-8",
        location: str | None = None,
        content_length: str | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._headers = {
            "Content-Type": content_type,
            "Location": location,
            "Content-Length": content_length,
        }

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self._headers.get(name) or default

    def read1(self, amt: int) -> bytes:
        chunk, self._body = self._body[:amt], self._body[amt:]
        return chunk


class FakeConnections:
    """Connection factory that serves scripted responses and records every connect."""

    def __init__(self, routes: dict[str, FakeResponse | Exception]) -> None:
        self.routes = routes
        self.connects: list[tuple[str, str]] = []
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.timeouts: list[float] = []
        self.closed = 0

    def __call__(self, host: str, address: str, timeout: float) -> FakeConnections:
        self.connects.append((host, address))
        self.timeouts.append(timeout)
        self._host = host
        return self

    def request(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))
        # Bind to the real signature so the fakes cannot accept a call that http.client misreads.
        bound = inspect.signature(http.client.HTTPSConnection.request).bind(self, *args, **kwargs)
        target = str(bound.arguments["url"])
        headers = dict(bound.arguments.get("headers") or {})
        self.requests.append((target, headers))
        self._key = f"https://{self._host}{target}"

    def set_timeout(self, seconds: float) -> None:
        self.timeouts.append(seconds)

    def abort(self) -> None:
        pass

    def getresponse(self) -> FakeResponse:
        outcome = self.routes[self._key]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self) -> None:
        self.closed += 1


def limits(**overrides: object) -> RetrievalLimits:
    return RetrievalLimits(**overrides)  # type: ignore[arg-type]


def fetcher_for(
    routes: dict[str, FakeResponse | Exception], **overrides: object
) -> tuple[SafeHttpsFetcher, FakeConnections]:
    connections = FakeConnections(routes)
    return SafeHttpsFetcher(
        limits(**overrides), resolver=resolver, connection_factory=connections
    ), connections


# --- URL safety -------------------------------------------------------------------------


def test_a_public_https_url_resolves_to_its_validated_address() -> None:
    assert check_public_https_url("https://example.org/a?b=1", resolver) == (
        "example.org",
        "93.184.216.34",
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/a",
        "ftp://example.org/a",
        "file:///C:/secret.txt",
        "https://" + "user" + ":" + "pass" + "@example.org/a",  # assembled: not a literal secret
        "https://example.org:8443/a",
        "https:///nohost",
        "https://localhost/a",
        "https://internal.example.org/a",
        "https://metadata.example.org/latest/meta-data",
        "https://lan.example.org/a",
        "https://loop6.example.org/a",
        "https://mapped.example.org/a",
        "https://shared.example.org/a",
        "https://mixed.example.org/a",
        "https://127.0.0.1/a",
    ],
)
def test_unsafe_urls_are_refused(url: str) -> None:
    def literal_aware(host: str, port: int) -> tuple[str, ...]:
        return (host,) if host[0].isdigit() else tuple(resolver(host, port))

    with pytest.raises(UnsafeUrlError):
        check_public_https_url(url, literal_aware)


def test_an_unresolvable_host_is_a_failure_not_an_unsafe_url() -> None:
    with pytest.raises(RetrievalFailure) as caught:
        check_public_https_url("https://nowhere.example.org/a", resolver)

    assert caught.value.status is RetrievalStatus.FAILED


# --- Fetching ---------------------------------------------------------------------------


def test_the_fetcher_connects_to_the_validated_address_with_the_original_host() -> None:
    fetcher, connections = fetcher_for(
        {"https://example.org/a?x=1": FakeResponse(body=b"hello", content_type="text/plain")}
    )

    page = fetcher.fetch("https://example.org/a?x=1")

    assert page == FetchedPage("https://example.org/a?x=1", 200, "text/plain", b"hello")
    assert connections.connects == [("example.org", "93.184.216.34")]
    target, headers = connections.requests[0]
    assert target == "/a?x=1" and "Host" not in headers  # http.client adds the pinned host
    assert headers["Accept-Encoding"] == "identity"
    assert connections.closed == 1


def test_redirects_are_followed_and_every_hop_is_revalidated() -> None:
    fetcher, connections = fetcher_for(
        {
            "https://example.org/a": FakeResponse(302, location="https://cdn.example.org/b"),
            "https://cdn.example.org/b": FakeResponse(302, location="/c"),
            "https://cdn.example.org/c": FakeResponse(body=b"done", content_type="text/plain"),
        }
    )

    page = fetcher.fetch("https://example.org/a")

    assert page.final_url == "https://cdn.example.org/c" and page.body == b"done"
    assert [host for host, _ in connections.connects] == [
        "example.org",
        "cdn.example.org",
        "cdn.example.org",
    ]


@pytest.mark.parametrize(
    "target",
    [
        "http://example.org/plain",
        "https://internal.example.org/admin",
        "https://metadata.example.org/latest",
        "https://example.org:8443/a",
        "file:///C:/secret.txt",
    ],
)
def test_an_unsafe_redirect_is_refused_before_any_connection(target: str) -> None:
    fetcher, connections = fetcher_for(
        {"https://example.org/a": FakeResponse(302, location=target)}
    )

    with pytest.raises(RetrievalFailure) as caught:
        fetcher.fetch("https://example.org/a")

    assert caught.value.status is RetrievalStatus.NOT_PERMITTED
    assert "Unsafe URL" in caught.value.reason
    assert [host for host, _ in connections.connects] == ["example.org"]  # never the target


def test_a_redirect_loop_is_bounded() -> None:
    fetcher, connections = fetcher_for(
        {"https://example.org/a": FakeResponse(302, location="/a")}, max_redirects=2
    )

    with pytest.raises(RetrievalFailure, match="2 redirects"):
        fetcher.fetch("https://example.org/a")

    assert len(connections.connects) == 3


def test_oversized_responses_are_refused_by_header_and_by_body() -> None:
    declared, _ = fetcher_for(
        {"https://example.org/a": FakeResponse(body=b"x", content_length="999999")},
        max_response_bytes=1000,
        cache_max_bytes=1000,
    )
    streamed, _ = fetcher_for(
        {"https://example.org/a": FakeResponse(body=b"x" * 1001)},
        max_response_bytes=1000,
        cache_max_bytes=1000,
    )
    exact, _ = fetcher_for(
        {"https://example.org/a": FakeResponse(body=b"x" * 1000)},
        max_response_bytes=1000,
        cache_max_bytes=1000,
    )

    for fetcher in (declared, streamed):
        with pytest.raises(RetrievalFailure, match="exceeds 1000 bytes"):
            fetcher.fetch("https://example.org/a")
    assert len(exact.fetch("https://example.org/a").body) == 1000


@pytest.mark.parametrize(
    ("error", "reason"),
    [(TimeoutError(), "timed out"), (ConnectionResetError(), "Transport error")],
)
def test_timeouts_and_transport_errors_are_recorded_failures(error: Exception, reason: str) -> None:
    fetcher, connections = fetcher_for({"https://example.org/a": error})

    with pytest.raises(RetrievalFailure, match=reason) as caught:
        fetcher.fetch("https://example.org/a")

    assert caught.value.status is RetrievalStatus.FAILED and connections.closed == 1


def test_the_real_connection_dials_the_pinned_address_not_the_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialled: list[tuple[str, int]] = []

    def fake_create_connection(address: tuple[str, int], _timeout: float) -> socket.socket:
        dialled.append(address)
        raise OSError("stop after recording")

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    connection = retrieval._pinned_connection("example.org", "93.184.216.34", 5.0)

    with pytest.raises(OSError, match="stop after recording"):
        connection.request("GET", "/", headers={})

    assert dialled == [("93.184.216.34", 443)]


# --- Text extraction --------------------------------------------------------------------


def test_plain_text_is_stored_exactly_with_its_original_line_endings() -> None:
    body = b"Results.\r\nWeight fell.\r\n\r\nNext\rline\n"

    text = extract_text(FetchedPage("u", 200, "text/plain; charset=utf-8", body))

    assert text == "Results.\r\nWeight fell.\r\n\r\nNext\rline\n"


def test_html_is_reduced_deterministically_without_scripts_or_styles() -> None:
    html = (
        b"<html><head><title>T</title><style>p{}</style></head><body><script>evil()</script>"
        b"<h1>Title</h1><p>First &amp; second.</p><p>Third<br>line</p></body></html>"
    )

    text = extract_text(FetchedPage("u", 200, "text/html", html))

    assert text == "Title\n\nFirst & second.\n\nThird\n\nline"
    assert "evil" not in text and "p{}" not in text


@pytest.mark.parametrize(
    ("content_type", "body", "status", "fragment"),
    [
        ("application/pdf", b"%PDF-1.7", RetrievalStatus.UNAVAILABLE, "Unsupported content type"),
        ("", b"abc", RetrievalStatus.UNAVAILABLE, "Unsupported content type"),
        ("text/plain; charset=utf-8", b"\xff\xfe\x00bad", RetrievalStatus.FAILED, "decodable"),
        ("text/html", b"<script>x</script>", RetrievalStatus.UNAVAILABLE, "no text"),
    ],
)
def test_unextractable_pages_fail_with_an_explicit_status(
    content_type: str, body: bytes, status: RetrievalStatus, fragment: str
) -> None:
    with pytest.raises(RetrievalFailure, match=fragment) as caught:
        extract_text(FetchedPage("u", 200, content_type, body))

    assert caught.value.status is status


# --- Bounded temporary cache ------------------------------------------------------------


def test_the_cache_stores_by_hash_and_returns_exact_text(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "c", max_bytes=1000, max_age_seconds=60)
    text = "a\r\nb\rc\n"

    digest = cache.put(text)

    assert digest == content_sha256(text)
    assert (tmp_path / "c" / f"{digest}.txt").read_bytes() == text.encode()
    assert cache.get(digest) == text and cache.get("0" * 64) is None


def test_the_cache_evicts_oldest_first_to_stay_within_its_budget(tmp_path: Path) -> None:
    clock = [1000.0]
    cache = BoundedTextCache(
        tmp_path / "c", max_bytes=25, max_age_seconds=10_000, clock=lambda: clock[0]
    )
    digests = []
    for index, letter in enumerate("abc"):
        digests.append(cache.put(letter * 10))
        os.utime(tmp_path / "c" / f"{digests[-1]}.txt", (1000 + index, 1000 + index))
    cache.prune()

    names = {p.name for p in cache.entries()}

    assert names == {f"{digests[1]}.txt", f"{digests[2]}.txt"}  # the oldest was evicted
    assert sum(p.stat().st_size for p in cache.entries()) <= 25


def test_expired_texts_are_deleted_and_not_served(tmp_path: Path) -> None:
    clock = [1000.0]
    cache = BoundedTextCache(
        tmp_path / "c", max_bytes=1000, max_age_seconds=60, clock=lambda: clock[0]
    )
    digest = cache.put("old text")
    os.utime(tmp_path / "c" / f"{digest}.txt", (1000, 1000))
    clock[0] = 1061.0

    assert cache.get(digest) is None
    assert cache.prune() == [f"{digest}.txt"] and cache.entries() == []


def test_the_cache_never_touches_files_that_are_not_its_own(tmp_path: Path) -> None:
    directory = tmp_path / "c"
    cache = BoundedTextCache(directory, max_bytes=20, max_age_seconds=1)
    foreign = [directory / "notes.txt", directory / ("a" * 64 + ".pdf"), directory / "paper.docx"]
    for path in foreign:
        path.write_bytes(b"user document " * 50)
        os.utime(path, (1, 1))  # ancient: would be expired if it were cache-owned
    cache.put("fits")
    cache.prune()
    cache.clear()

    assert all(path.exists() for path in foreign)
    assert (tmp_path / "outside.txt").exists() is False


def test_a_text_larger_than_the_whole_budget_is_rejected(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "c", max_bytes=10, max_age_seconds=60)

    with pytest.raises(CacheBudgetError):
        cache.put("x" * 11)
    assert cache.entries() == []


def test_a_tampered_cache_file_is_not_served(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "c", max_bytes=1000, max_age_seconds=60)
    digest = cache.put("genuine")
    (tmp_path / "c" / f"{digest}.txt").write_bytes(b"forged")

    assert cache.get(digest) is None


# --- Retrieval of one source ------------------------------------------------------------


def observation(
    host: str = "example.org", path: str = "/a", **overrides: object
) -> ProviderObservation:
    fields: dict[str, object] = {
        "provider": "openalex",
        "provider_id": f"id-{host}{path}",
        "title": f"Paper at {host}{path}",
        "full_text_url": f"https://{host}{path}",
    }
    fields.update(overrides)
    return ProviderObservation(**fields)  # type: ignore[arg-type]


def cache_for(tmp_path: Path) -> BoundedTextCache:
    return BoundedTextCache(tmp_path / "cache", max_bytes=100_000, max_age_seconds=3600)


@pytest.mark.parametrize(
    ("response", "status", "fragment"),
    [
        (FakeResponse(404), RetrievalStatus.UNAVAILABLE, "HTTP 404"),
        (FakeResponse(410), RetrievalStatus.UNAVAILABLE, "HTTP 410"),
        (FakeResponse(403), RetrievalStatus.NOT_PERMITTED, "HTTP 403"),
        (FakeResponse(451), RetrievalStatus.NOT_PERMITTED, "HTTP 451"),
        (FakeResponse(429), RetrievalStatus.FAILED, "HTTP 429"),
        (FakeResponse(503), RetrievalStatus.FAILED, "HTTP 503"),
        (FakeResponse(200, b"%PDF", "application/pdf"), RetrievalStatus.UNAVAILABLE, "Unsupported"),
    ],
)
def test_every_failed_retrieval_becomes_a_recorded_unciteable_source(
    tmp_path: Path, response: FakeResponse, status: RetrievalStatus, fragment: str
) -> None:
    fetcher, _ = fetcher_for({"https://example.org/a": response})
    cache = cache_for(tmp_path)

    source = retrieve_source(
        observation(), "https://example.org/a", fetcher=fetcher, cache=cache, now=lambda: NOW
    )

    assert source.status is status and fragment in (source.failure_reason or "")
    assert source.content_sha256 is None and cache.entries() == []
    assert source.retrieved_at == NOW.isoformat() and source.url == "https://example.org/a"


def test_an_unsafe_source_url_is_recorded_as_not_permitted(tmp_path: Path) -> None:
    fetcher, connections = fetcher_for({})
    url = "https://internal.example.org/paper"

    source = retrieve_source(
        observation("internal.example.org", "/paper"),
        url,
        fetcher=fetcher,
        cache=cache_for(tmp_path),
        now=lambda: NOW,
    )

    assert source.status is RetrievalStatus.NOT_PERMITTED
    assert "non-public address" in (source.failure_reason or "")
    assert connections.connects == []


def test_a_retrieved_source_keeps_identifiers_provider_url_time_and_hash(tmp_path: Path) -> None:
    body = b"Weight loss in adults.\r\nSecond line."
    fetcher, _ = fetcher_for({"https://example.org/a": FakeResponse(body=body)})
    cache = cache_for(tmp_path)

    source = retrieve_source(
        observation(doi="10.1/ABC", pmid="42"),
        "https://example.org/a",
        fetcher=fetcher,
        cache=cache,
        now=lambda: NOW,
    )

    text = body.decode()
    assert source.status is RetrievalStatus.RETRIEVED
    assert source.source_id == "doi:10.1/abc" and source.pmid == "42"
    assert source.provider == "openalex" and source.url == "https://example.org/a"
    assert (
        source.content_sha256 == content_sha256(text) and cache.get(source.content_sha256) == text
    )


def test_a_text_too_big_for_the_cache_is_a_recorded_failure(tmp_path: Path) -> None:
    fetcher, _ = fetcher_for({"https://example.org/a": FakeResponse(body=b"x" * 50)})
    cache = BoundedTextCache(tmp_path / "c", max_bytes=10, max_age_seconds=60)

    source = retrieve_source(
        observation(), "https://example.org/a", fetcher=fetcher, cache=cache, now=lambda: NOW
    )

    assert source.status is RetrievalStatus.FAILED and "cache budget" in (
        source.failure_reason or ""
    )


# --- Excerpt selection ------------------------------------------------------------------

TRIAL = (
    "Background.\n\nSemaglutide reduced body weight by 15.2% over 104 weeks compared with "
    "placebo.\n\nUnrelated methods paragraph about recruitment.\n\n"
    "Adverse events were mostly gastrointestinal."
)


def test_excerpts_are_exact_offset_slices_ranked_by_term_overlap() -> None:
    terms = retrieval.question_terms("Does semaglutide reduce body weight versus placebo?")

    excerpts = select_excerpts("doi:10.1/x", TRIAL, terms, limit=2, max_chars=600)

    assert excerpts[0].text.startswith("Semaglutide reduced body weight")
    for excerpt in excerpts:
        assert excerpt.char_start is not None and excerpt.char_end is not None
        assert TRIAL[excerpt.char_start : excerpt.char_end] == excerpt.text
    assert not any("recruitment" in e.text for e in excerpts)


def test_excerpts_keep_crlf_and_are_capped_at_a_sentence_boundary() -> None:
    sentence = "Weight fell by a large and clinically meaningful amount in every treated group. "
    text = "Intro\r\n\r\n" + sentence * 20
    terms = retrieval.question_terms("weight fell")

    (excerpt,) = select_excerpts("doi:10.1/x", text, terms, limit=1, max_chars=200)

    assert excerpt.char_start == 9 and len(excerpt.text) <= 200
    assert (
        excerpt.text.endswith(".") and text[excerpt.char_start : excerpt.char_end] == excerpt.text
    )


def test_a_question_with_no_usable_terms_selects_nothing() -> None:
    assert retrieval.question_terms("who are you and what was that?") == frozenset()
    assert select_excerpts("doi:10.1/x", TRIAL, frozenset(), limit=3, max_chars=600) == []


# --- End-to-end workflow (no network) ---------------------------------------------------


class FakeBroker:
    def __init__(self, candidates: tuple[FederatedCandidate, ...]) -> None:
        self.candidates = candidates
        self.queries: list[DiscoveryQuery] = []

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        self.queries.append(query)
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus("openalex", ProviderOutcome.SUCCESS, True, len(self.candidates)),
            ),
            candidates=self.candidates,
        )


def candidate(
    key: str, *observations: ProviderObservation, doi: str | None = None
) -> FederatedCandidate:
    return FederatedCandidate(
        canonical_id=key, title=f"Candidate {key}", observations=observations, doi=doi
    )


def build_world(
    tmp_path: Path, **overrides: object
) -> tuple[FakeBroker, SafeHttpsFetcher, BoundedTextCache, RetrievalLimits]:
    html = (
        b"<html><body><h1>Trial</h1><p>Semaglutide reduced body weight by 15.2% versus placebo."
        b"</p><p>Recruitment was national.</p></body></html>"
    )
    plain = b"Liraglutide lowered body weight modestly.\r\n\r\nNo placebo group was used.\r\n"
    fetcher, _ = fetcher_for(
        {
            "https://example.org/trial": FakeResponse(body=html, content_type="text/html"),
            "https://cdn.example.org/plain": FakeResponse(body=plain),
            "https://papers.example.org/gone": FakeResponse(404),
            "https://papers.example.org/walled": FakeResponse(403),
        },
        **overrides,
    )
    broker = FakeBroker(
        (
            candidate("c1", observation("example.org", "/trial", doi="10.1/trial")),
            candidate("c2", observation("cdn.example.org", "/plain", doi="10.1/plain")),
            candidate("c3", observation("papers.example.org", "/gone", doi="10.1/gone")),
            candidate("c4", observation("papers.example.org", "/walled", pmid="777")),
            candidate("c5", ProviderObservation("pubmed", "p5", "No URL candidate", pmid="5")),
            candidate("c6", observation("example.org", "/trial", doi="10.1/TRIAL")),
        )
    )
    use = limits(max_sources=5, **overrides)
    return broker, fetcher, cache_for(tmp_path), use


def test_a_question_becomes_a_valid_verifiable_bundle_with_explicit_failures(
    tmp_path: Path,
) -> None:
    broker, fetcher, cache, use = build_world(tmp_path)
    question = "Does semaglutide reduce body weight versus placebo?"

    result = research_online(
        question, broker=broker, fetcher=fetcher, cache=cache, limits=use, now=lambda: NOW
    )

    bundle = result.bundle
    by_status = {s.source_id: s.status for s in bundle.sources}
    assert by_status == {
        "doi:10.1/trial": RetrievalStatus.RETRIEVED,
        "doi:10.1/plain": RetrievalStatus.RETRIEVED,
        "doi:10.1/gone": RetrievalStatus.UNAVAILABLE,
        "pmid:777": RetrievalStatus.NOT_PERMITTED,
    }
    assert {r for _, r in result.skipped} == {
        "no retrievable URL",
        "duplicate source doi:10.1/trial",
    }
    assert broker.queries[0].text == question
    assert all(s.retrieved_at == NOW.isoformat() for s in bundle.sources)
    quoted = {e.source_id for e in bundle.excerpts}
    assert quoted == {"doi:10.1/trial", "doi:10.1/plain"}  # nothing is quoted from a failed source
    assert any("Semaglutide reduced body weight by 15.2%" in e.text for e in bundle.excerpts)
    assert bundle.claims == ()  # drawing claims is analysis, left to the report layer
    contents = {
        s.source_id: cache.get(s.content_sha256)
        for s in bundle.sources
        if s.content_sha256 is not None
    }
    assert verify_against_retrieved_content(bundle, contents) == []  # type: ignore[arg-type]
    assert OnlineEvidenceBundle.from_dict(json.loads(json.dumps(bundle.to_dict()))) == bundle


def test_the_bundle_validates_through_the_existing_cli_against_the_cache(tmp_path: Path) -> None:
    broker, fetcher, cache, use = build_world(tmp_path)
    result = research_online(
        "semaglutide body weight placebo",
        broker=broker,
        fetcher=fetcher,
        cache=cache,
        limits=use,
        now=lambda: NOW,
    )
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(result.bundle.to_dict()), encoding="utf-8")

    ok = CliRunner().invoke(
        entrypoint.app,
        ["online-evidence-validate", str(path), "--contents-dir", str(cache.directory)],
    )
    forged = result.bundle.excerpts[0]
    tampered = OnlineEvidenceBundle(
        result.bundle.question,
        result.bundle.sources,
        (*result.bundle.excerpts, EvidenceExcerpt.quote(forged.source_id, "Invented finding.")),
    )
    path.write_text(json.dumps(tampered.to_dict()), encoding="utf-8")
    bad = CliRunner().invoke(
        entrypoint.app,
        ["online-evidence-validate", str(path), "--contents-dir", str(cache.directory)],
    )

    assert ok.exit_code == 0, ok.output
    assert "verified against retrieved content" in " ".join(ok.output.split())
    assert bad.exit_code == 1 and "text not found in its source" in " ".join(bad.output.split())


def test_corpus_free_bundle_validates_from_ephemeral_cache_and_fails_closed_after_cleanup(
    tmp_path: Path,
) -> None:
    """A Research Report evidence bundle needs no pre-ingested corpus or vector index."""
    retrieved = "Semaglutide reduced body weight versus placebo.\nFollow-up was two years."
    fetcher, _ = fetcher_for(
        {
            "https://example.org/trial": FakeResponse(body=retrieved.encode()),
            "https://cdn.example.org/failed": FakeResponse(503),
            "https://papers.example.org/gone": FakeResponse(404),
        }
    )
    broker = FakeBroker(
        (
            candidate("trial", observation("example.org", "/trial", doi="10.1/trial")),
            candidate("failed", observation("cdn.example.org", "/failed", doi="10.1/failed")),
            candidate("gone", observation("papers.example.org", "/gone", doi="10.1/gone")),
        )
    )
    cache = BoundedTextCache(tmp_path / "ephemeral", max_bytes=500, max_age_seconds=60)
    result = research_online(
        "Does semaglutide reduce body weight versus placebo?",
        broker=broker,
        fetcher=fetcher,
        cache=cache,
        limits=limits(max_sources=3, max_response_bytes=500, cache_max_bytes=500),
        now=lambda: NOW,
    )
    bundle = result.bundle
    by_id = {source.source_id: source for source in bundle.sources}
    assert {key: source.status for key, source in by_id.items()} == {
        "doi:10.1/trial": RetrievalStatus.RETRIEVED,
        "doi:10.1/failed": RetrievalStatus.FAILED,
        "doi:10.1/gone": RetrievalStatus.UNAVAILABLE,
    }
    assert all(by_id[key].failure_reason for key in ("doi:10.1/failed", "doi:10.1/gone"))
    assert {excerpt.source_id for excerpt in bundle.excerpts} == {"doi:10.1/trial"}
    assert bundle.excerpts
    for excerpt in bundle.excerpts:
        source = by_id[excerpt.source_id]
        assert source.retrieved_at == NOW.isoformat()
        assert source.content_sha256 == content_sha256(retrieved)
        assert excerpt.char_start is not None and excerpt.char_end is not None
        assert retrieved[excerpt.char_start : excerpt.char_end] == excerpt.text

    path = tmp_path / "report-evidence.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    args = ["online-evidence-validate", str(path), "--contents-dir", str(cache.directory)]
    verified = CliRunner().invoke(entrypoint.app, args)
    assert verified.exit_code == 0, verified.output
    assert sum(entry.stat().st_size for entry in cache.entries()) <= 500

    cache.clear()
    assert cache.entries() == []
    unavailable = CliRunner().invoke(entrypoint.app, args)
    assert unavailable.exit_code != 0
    assert "verified against retrieved content" not in " ".join(unavailable.output.split())


def test_the_source_limit_bounds_how_many_candidates_are_retrieved(tmp_path: Path) -> None:
    broker, fetcher, cache, _ = build_world(tmp_path)

    result = research_online(
        "semaglutide body weight",
        broker=broker,
        fetcher=fetcher,
        cache=cache,
        limits=limits(max_sources=2),
        now=lambda: NOW,
    )

    assert [s.source_id for s in result.bundle.sources] == ["doi:10.1/trial", "doi:10.1/plain"]


def test_no_candidates_gives_an_empty_valid_bundle(tmp_path: Path) -> None:
    fetcher, connections = fetcher_for({})

    result = research_online(
        "anything about nothing",
        broker=FakeBroker(()),
        fetcher=fetcher,
        cache=cache_for(tmp_path),
        limits=limits(),
        now=lambda: NOW,
    )

    assert result.bundle.sources == () and result.bundle.excerpts == ()
    assert connections.connects == []


def test_expired_cache_files_are_removed_at_the_start_of_a_run(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "cache", max_bytes=100_000, max_age_seconds=60)
    stale = cache.put("stale text from an earlier question")
    os.utime(cache.directory / f"{stale}.txt", (1, 1))
    fetcher, _ = fetcher_for({})

    research_online(
        "semaglutide",
        broker=FakeBroker(()),
        fetcher=fetcher,
        cache=cache,
        limits=limits(),
        now=lambda: NOW,
    )

    assert cache.entries() == []


def test_retrieval_limits_reject_inconsistent_bounds() -> None:
    for bad in (
        {"max_sources": 0},
        {"timeout_seconds": 0},
        {"excerpt_chars": 5000},
        {"max_response_bytes": 10, "cache_max_bytes": 5},
        {"cache_max_age_seconds": 0},
    ):
        with pytest.raises(ValueError):
            limits(**bad)


# --- CLI --------------------------------------------------------------------------------


class NamedBroker(FakeBroker):
    name = "openalex"


def patch_cli_world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SafeHttpsFetcher:
    from knowledge_engine.discovery_provider_registry import DiscoveryProviderRegistry

    broker, fetcher, _cache, _use = build_world(tmp_path)
    provider = NamedBroker(broker.candidates)
    monkeypatch.setattr(
        entrypoint,
        "_federated_discovery_registry",
        lambda **_: DiscoveryProviderRegistry([provider]),
    )
    monkeypatch.setattr(retrieval, "SafeHttpsFetcher", lambda _limits: fetcher)
    return fetcher


def test_cli_writes_a_bundle_that_validates_against_its_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cli_world(monkeypatch, tmp_path)
    cache_dir, output = tmp_path / "cache", tmp_path / "bundle.json"
    runner = CliRunner()

    result = runner.invoke(
        entrypoint.app,
        [
            "online-research",
            "Does semaglutide reduce body weight versus placebo?",
            "--cache-dir",
            str(cache_dir),
            "--output",
            str(output),
            "--ledger-root",
            str(tmp_path / "ledger"),
            "--max-sources",
            "5",
        ],
    )

    text = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert "Sources: 2 retrieved, 2 unavailable" in text
    assert "doi:10.1/gone unavailable: HTTP 404." in text
    assert "pmid:777 not_permitted: HTTP 403." in text
    assert "skipped c5: no retrievable URL" in text
    checked = runner.invoke(
        entrypoint.app, ["online-evidence-validate", str(output), "--contents-dir", str(cache_dir)]
    )
    assert checked.exit_code == 0, checked.output
    assert "verified against retrieved content" in " ".join(checked.output.split())


def test_cli_refuses_to_overwrite_an_existing_bundle_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cli_world(monkeypatch, tmp_path)
    output = tmp_path / "bundle.json"
    output.write_text("keep me", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "online-research",
            "semaglutide",
            "--cache-dir",
            str(tmp_path / "c"),
            "--output",
            str(output),
            "--ledger-root",
            str(tmp_path / "ledger"),
        ],
    )

    assert result.exit_code == 2 and output.read_text(encoding="utf-8") == "keep me"


# --- Review findings on #559: real connection, run-scoped cache, deadline ----------------


class _TlsServer:
    """One-shot loopback TLS server for example.org, so the *real* connection class is used."""

    def __init__(self, tmp_path: Path, respond: Callable[[ssl.SSLSocket, bytes], None]) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
        ca = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(start)
            .not_valid_after(start + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), False)
            .sign(ca_key, hashes.SHA256())
        )
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "example.org")]))
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(start)
            .not_valid_after(start + timedelta(days=3650))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("example.org")]), False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False)
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), False
            )
            .sign(ca_key, hashes.SHA256())
        )
        self.pem = ca.public_bytes(serialization.Encoding.PEM).decode("ascii")  # the trust anchor
        cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
        cert_file.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
        key_file.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        self._listener = socket.create_server(("127.0.0.1", 0))
        self.port: int = self._listener.getsockname()[1]
        self.request = b""
        self._respond = respond
        self._context = context
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            raw, _ = self._listener.accept()
            with self._context.wrap_socket(raw, server_side=True) as connection:
                data = b""
                while b"\r\n\r\n" not in data:
                    chunk = connection.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                self.request = data
                self._respond(connection, data)
        except OSError:
            pass  # the client hung up (expected when its deadline fires)
        finally:
            self._listener.close()

    def factory(self) -> retrieval.ConnectionFactory:
        def connect(host: str, _address: str, timeout: float) -> retrieval._Connection:
            connection = retrieval._PinnedHTTPSConnection(
                host, "127.0.0.1", timeout, port=self.port
            )
            # These tests exercise the request/stream code of the real class against a loopback
            # server with a throwaway certificate; certificate validation itself is not under test.
            connection._tls.check_hostname = False
            connection._tls.verify_mode = ssl.CERT_NONE
            return connection  # type: ignore[return-value]

        return connect

    def join(self) -> None:
        self._thread.join(timeout=10)


def test_the_real_pinned_connection_sends_a_header_bearing_get_with_no_body(
    tmp_path: Path,
) -> None:
    def respond(connection: ssl.SSLSocket, _request: bytes) -> None:
        connection.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 5\r\n"
            b"Connection: close\r\n\r\nhello"
        )

    server = _TlsServer(tmp_path, respond)
    fetcher = SafeHttpsFetcher(limits(), resolver=resolver, connection_factory=server.factory())

    page = fetcher.fetch("https://example.org/a?x=1")
    server.join()

    assert (page.status, page.body, page.content_type) == (200, b"hello", "text/plain")
    head, _, body = server.request.partition(b"\r\n\r\n")
    lines = head.split(b"\r\n")
    assert lines[0] == b"GET /a?x=1 HTTP/1.1" and body == b""
    # The original host (plus the test server's non-443 port), although we dialled loopback.
    assert b"Host: example.org:" + str(server.port).encode() in lines
    assert b"Accept-Encoding: identity" in lines
    assert any(line.startswith(b"User-Agent: ") for line in lines)
    assert not any(line.lower().startswith(b"content-length") for line in lines)


def test_the_real_connection_enforces_one_deadline_on_a_slow_continuous_stream(
    tmp_path: Path,
) -> None:
    def respond(connection: ssl.SSLSocket, _request: bytes) -> None:
        connection.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n"
        )
        for _ in range(60):  # a byte every 0.1 s: each read succeeds well inside the socket timeout
            connection.sendall(b"x")
            time.sleep(0.1)

    server = _TlsServer(tmp_path, respond)
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=1.0), resolver=resolver, connection_factory=server.factory()
    )

    started = time.monotonic()
    with pytest.raises(RetrievalFailure, match="timed out") as caught:
        fetcher.fetch("https://example.org/slow")
    elapsed = time.monotonic() - started
    server.join()

    assert caught.value.status is RetrievalStatus.FAILED
    assert elapsed < 3.0  # the stream would have run for ~6 s


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _TrickleResponse(FakeResponse):
    """Never-ending body, one byte per read, each read costing one second of the clock."""

    def __init__(self, clock: _Clock) -> None:
        super().__init__()
        self.clock = clock
        self.reads = 0

    def read1(self, amt: int) -> bytes:
        self.reads += 1
        self.clock.now += 1.0
        return b"x"


def test_the_deadline_spans_connection_redirects_and_reading() -> None:
    clock = _Clock()
    trickle = _TrickleResponse(clock)

    class Slow(FakeConnections):
        def getresponse(self) -> FakeResponse:
            clock.now += 2.0  # each hop's response headers take 2 s
            return super().getresponse()

    connections = Slow(
        {
            "https://example.org/a": FakeResponse(302, location="https://cdn.example.org/b"),
            "https://cdn.example.org/b": trickle,
        }
    )
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=10.0, max_response_bytes=10_000),
        resolver=resolver,
        connection_factory=connections,
        clock=clock,
    )

    with pytest.raises(RetrievalFailure, match="timed out"):
        fetcher.fetch("https://example.org/a")

    assert trickle.reads == 6  # 10 s - 2 s (hop 1) - 2 s (hop 2) = 6 s of reading, no more
    assert connections.closed == 2
    assert all(0 < seconds <= 10.0 for seconds in connections.timeouts)
    assert connections.timeouts == sorted(connections.timeouts, reverse=True)  # only ever tightens


def test_a_deadline_that_expires_before_a_redirect_hop_stops_the_chain() -> None:
    clock = _Clock()

    class Slow(FakeConnections):
        def getresponse(self) -> FakeResponse:
            clock.now += 6.0
            return super().getresponse()

    connections = Slow(
        {
            "https://example.org/a": FakeResponse(302, location="https://cdn.example.org/b"),
            "https://cdn.example.org/b": FakeResponse(body=b"never fetched"),
        }
    )
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=5.0), resolver=resolver, connection_factory=connections, clock=clock
    )

    with pytest.raises(RetrievalFailure, match="timed out"):
        fetcher.fetch("https://example.org/a")

    assert [host for host, _ in connections.connects] == ["example.org"]


def test_the_fetcher_call_binds_to_the_real_http_client_signature() -> None:
    fetcher, connections = fetcher_for({"https://example.org/a": FakeResponse(body=b"ok")})

    fetcher.fetch("https://example.org/a")

    (args, kwargs), *_ = connections.calls
    bound = inspect.signature(http.client.HTTPSConnection.request).bind(object(), *args, **kwargs)
    assert bound.arguments.get("body") is None  # headers must never land in the body slot
    assert "User-Agent" in bound.arguments["headers"]


def test_only_the_caches_own_partial_files_are_cleaned_up(tmp_path: Path) -> None:
    directory = tmp_path / "c"
    cache = BoundedTextCache(directory, max_bytes=1000, max_age_seconds=1)
    foreign = [
        directory / "download.partial",  # a browser or user download in progress
        directory / "report.docx.partial",
        directory / "ke-cache-not-hex.partial",
        directory / ("ke-cache-" + "A" * 32 + ".partial"),
        directory / ("ke-cache-" + "0" * 31 + ".partial"),
        directory / ("0" * 64 + ".txt.partial"),
    ]
    own_stale = directory / ("ke-cache-" + "ab" * 16 + ".partial")
    own_fresh = directory / ("ke-cache-" + "cd" * 16 + ".partial")
    for path in [*foreign, own_stale, own_fresh]:
        path.write_bytes(b"data")
    for path in [*foreign, own_stale]:
        os.utime(path, (1, 1))  # ancient

    cache.put("hello")
    cache.prune()
    cache.clear()

    assert all(path.read_bytes() == b"data" for path in foreign)  # never touched
    assert not own_stale.exists()  # an interrupted put of this cache, long expired
    assert own_fresh.exists()  # possibly a put in progress in another process


def test_a_put_leaves_no_partial_file_behind(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "c", max_bytes=1000, max_age_seconds=60)

    cache.put("one")
    cache.put("two")

    assert sorted(p.suffix for p in (tmp_path / "c").iterdir()) == [".txt", ".txt"]


def test_held_texts_survive_pruning_until_the_run_releases_them(tmp_path: Path) -> None:
    clock = _Clock()
    clock.now = time.time()
    cache = BoundedTextCache(tmp_path / "c", max_bytes=25, max_age_seconds=10, clock=clock)
    first = cache.put("a" * 10, hold=True)
    second = cache.put("b" * 10, hold=True)

    with pytest.raises(CacheBudgetError):  # a third held text would not fit: refuse, don't evict
        cache.put("c" * 10, hold=True)
    cache.put("d" * 4)  # an unheld text may come and go
    clock.now += 100.0  # everything is now past its lifetime
    cache.prune()

    assert cache.get(first) == "a" * 10 and cache.get(second) == "b" * 10
    cache.release()
    cache.prune()
    assert cache.entries() == []


def test_a_run_never_cites_content_the_cache_could_not_keep(tmp_path: Path) -> None:
    docs = {
        f"/d{n}": (f"Semaglutide trial {n} reduced body weight. " * 2).encode() for n in (1, 2, 3)
    }
    fetcher, _ = fetcher_for(
        {f"https://example.org{path}": FakeResponse(body=body) for path, body in docs.items()},
        max_response_bytes=100,
        cache_max_bytes=150,  # room for one text, not two
    )
    broker = FakeBroker(
        tuple(
            candidate(f"c{n}", observation("example.org", f"/d{n}", doi=f"10.1/d{n}"))
            for n in (1, 2, 3)
        )
    )
    cache = BoundedTextCache(tmp_path / "cache", max_bytes=150, max_age_seconds=3600)

    result = research_online(
        "semaglutide body weight",
        broker=broker,
        fetcher=fetcher,
        cache=cache,
        limits=limits(max_sources=3, max_response_bytes=100, cache_max_bytes=150),
        now=lambda: NOW,
    )

    statuses = {s.source_id: s.status for s in result.bundle.sources}
    assert statuses["doi:10.1/d1"] is RetrievalStatus.RETRIEVED
    assert statuses["doi:10.1/d2"] is RetrievalStatus.FAILED
    assert statuses["doi:10.1/d3"] is RetrievalStatus.FAILED
    assert {e.source_id for e in result.bundle.excerpts} == {"doi:10.1/d1"}
    contents = {
        s.source_id: cache.get(s.content_sha256)
        for s in result.bundle.sources
        if s.content_sha256 is not None
    }
    assert verify_against_retrieved_content(result.bundle, contents) == []  # type: ignore[arg-type]


def test_content_evicted_by_another_process_is_withheld_not_cited(tmp_path: Path) -> None:
    cache = BoundedTextCache(tmp_path / "cache", max_bytes=100_000, max_age_seconds=3600)
    inner, _ = fetcher_for(
        {
            "https://example.org/a": FakeResponse(body=b"Semaglutide lowered body weight."),
            "https://cdn.example.org/b": FakeResponse(body=b"Semaglutide also lowered weight."),
        }
    )

    class Evicting:
        def fetch(self, url: str) -> FetchedPage:
            if url.endswith("/b"):  # a second process clears the cache mid-run
                for path in cache.directory.glob("*.txt"):
                    path.unlink()
            return inner.fetch(url)

    broker = FakeBroker(
        (
            candidate("c1", observation("example.org", "/a", doi="10.1/a")),
            candidate("c2", observation("cdn.example.org", "/b", doi="10.1/b")),
        )
    )

    result = research_online(
        "semaglutide body weight",
        broker=broker,
        fetcher=Evicting(),
        cache=cache,
        limits=limits(max_sources=2),
        now=lambda: NOW,
    )

    first = next(s for s in result.bundle.sources if s.source_id == "doi:10.1/a")
    assert first.status is RetrievalStatus.UNAVAILABLE and "evicted" in (first.failure_reason or "")
    assert first.content_sha256 is None
    assert {e.source_id for e in result.bundle.excerpts} == {"doi:10.1/b"}


# --- Review findings on #561: header deadline, ledger, long-paragraph windows ------------


def test_a_trickled_status_line_and_headers_cannot_outlast_the_deadline(tmp_path: Path) -> None:
    def respond(connection: ssl.SSLSocket, _request: bytes) -> None:
        for byte in b"HTTP/1.1 200 OK\r\nX-Slow: " + b"y" * 400:  # headers never finish
            connection.sendall(bytes([byte]))
            time.sleep(0.1)

    server = _TlsServer(tmp_path, respond)
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=0.3), resolver=resolver, connection_factory=server.factory()
    )

    started = time.monotonic()
    with pytest.raises(RetrievalFailure, match="timed out") as caught:
        fetcher.fetch("https://example.org/slow-headers")
    elapsed = time.monotonic() - started
    server.join()

    assert caught.value.status is RetrievalStatus.FAILED
    assert elapsed < 0.9  # bytes keep arriving inside the read timeout; the old code took ~1.5 s


def test_online_research_records_the_discovery_run_and_keeps_its_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cli_world(monkeypatch, tmp_path)
    ledger, output = tmp_path / "ledger", tmp_path / "bundle.json"
    runner = CliRunner()

    result = runner.invoke(
        entrypoint.app,
        [
            "online-research",
            "Does semaglutide reduce body weight versus placebo?",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--output",
            str(output),
            "--ledger-root",
            str(ledger),
            "--max-sources",
            "5",
        ],
    )

    assert result.exit_code == 0, result.output
    sidecar = json.loads((tmp_path / "bundle.json.discovery.json").read_text(encoding="utf-8"))
    run_id = sidecar["search_run_id"]
    assert sidecar["bundle"] == "bundle.json" and run_id in " ".join(result.output.split())
    assert list(ledger.rglob("*.json"))  # the run is persisted, not just reported
    coverage = runner.invoke(
        entrypoint.app, ["federated-coverage-report", run_id, "--ledger-root", str(ledger)]
    )
    assert coverage.exit_code == 0, coverage.output  # and can be audited later by its id


def test_online_research_requires_a_ledger_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_cli_world(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "online-research",
            "semaglutide",
            "--cache-dir",
            str(tmp_path / "c"),
            "--output",
            str(tmp_path / "bundle.json"),
        ],
    )

    assert result.exit_code == 2 and not (tmp_path / "bundle.json").exists()


def test_a_long_paragraph_is_quoted_at_the_window_that_matches_the_question() -> None:
    background = "General background about metabolic disease and its burden worldwide. " * 30
    result = "Semaglutide reduced body weight by 15.2% versus placebo at week 68. "
    text = "Intro paragraph.\r\n\r\n" + background + result + "Safety was acceptable." + "\r\n"
    terms = retrieval.question_terms("Does semaglutide reduce body weight versus placebo?")

    (excerpt,) = select_excerpts("doi:10.1/x", text, terms, limit=1, max_chars=300)

    assert "Semaglutide reduced body weight" in excerpt.text
    assert len(excerpt.text) <= 300 and excerpt.text.endswith(".")
    assert excerpt.char_start is not None and excerpt.char_end is not None
    assert text[excerpt.char_start : excerpt.char_end] == excerpt.text  # exact offsets, CRLF intact
    assert excerpt.char_start > len(background) - 300  # not the paragraph head


def test_a_long_paragraph_without_a_better_window_keeps_its_head() -> None:
    sentence = "Weight fell by a large and clinically meaningful amount in every group. "
    text = sentence * 20
    terms = retrieval.question_terms("weight fell")

    (excerpt,) = select_excerpts("doi:10.1/x", text, terms, limit=1, max_chars=200)

    assert excerpt.char_start == 0 and len(excerpt.text) <= 200


def test_the_watchdog_aborts_a_header_read_that_the_socket_timeout_cannot_bound() -> None:
    class Blocking(FakeConnections):
        """getresponse() stands in for a header read that trickles forever."""

        def __init__(self) -> None:
            super().__init__({})
            self.aborted = threading.Event()

        def getresponse(self) -> FakeResponse:
            self.aborted.wait(timeout=5.0)  # a real read would still be receiving bytes
            raise http.client.RemoteDisconnected("socket shut down")  # what an aborted read does

        def abort(self) -> None:
            self.aborted.set()

    connections = Blocking()
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=0.2), resolver=resolver, connection_factory=connections
    )

    started = time.monotonic()
    with pytest.raises(RetrievalFailure, match="timed out") as caught:
        fetcher.fetch("https://example.org/a")

    assert caught.value.status is RetrievalStatus.FAILED
    assert connections.aborted.is_set() and time.monotonic() - started < 2.0
    assert connections.closed == 1


def test_a_clean_eof_after_the_deadline_abort_is_not_mistaken_for_a_complete_body() -> None:
    clock = _Clock()

    class Truncated(FakeResponse):
        def read1(self, amt: int) -> bytes:
            return b""  # an aborted socket reads as EOF

    connections = FakeConnections({"https://example.org/a": Truncated(body=b"partial")})
    fetcher = SafeHttpsFetcher(
        limits(timeout_seconds=5.0), resolver=resolver, connection_factory=connections, clock=clock
    )
    original = fetcher._finish

    def finish_after_expiry(
        url: str,
        response: object,
        connection: object,
        deadline: float,
        expired: threading.Event,
    ) -> FetchedPage:
        expired.set()  # the watchdog fired while the body was being read
        return original(url, response, connection, deadline, expired)  # type: ignore[arg-type]

    fetcher._finish = finish_after_expiry  # type: ignore[method-assign]

    with pytest.raises(RetrievalFailure, match="timed out"):
        fetcher.fetch("https://example.org/a")
