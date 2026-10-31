from __future__ import annotations

import json
import os
import socket
from datetime import UTC, datetime
from pathlib import Path

import pytest
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
        self._pos = 0
        self._headers = {
            "Content-Type": content_type,
            "Location": location,
            "Content-Length": content_length,
        }

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self._headers.get(name) or default

    def read(self, amt: int | None = None) -> bytes:
        end = len(self._body) if amt is None else self._pos + amt
        chunk = self._body[self._pos : end]
        self._pos += len(chunk)
        return chunk


class FakeConnections:
    """Connection factory that serves scripted responses and records every connect."""

    def __init__(self, routes: dict[str, FakeResponse | Exception]) -> None:
        self.routes = routes
        self.connects: list[tuple[str, str]] = []
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.closed = 0

    def __call__(self, host: str, address: str, _timeout: float) -> FakeConnections:
        self.connects.append((host, address))
        self._host = host
        return self

    def request(self, _method: str, target: str, headers: dict[str, str]) -> None:
        self.requests.append((target, headers))
        self._key = f"https://{self._host}{target}"

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
        "https://user:pass@example.org/a",
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
    assert target == "/a?x=1" and headers["Host"] == "example.org"
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
        connection.request("GET", "/", {})

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
        ],
    )

    assert result.exit_code == 2 and output.read_text(encoding="utf-8") == "keep me"


def test_slow_dribbling_response_hits_the_wall_clock_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The socket timeout bounds each read only; the fetch must bound total time."""

    import knowledge_engine.online_retrieval as module

    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])

    class Dribble(FakeResponse):
        def read(self, amt: int | None = None) -> bytes:
            clock[0] += 6.0  # each read "succeeds" within the socket timeout but is slow
            return b"x"

    fetcher, _ = fetcher_for({"https://example.org/a": Dribble()}, timeout_seconds=10.0)

    with pytest.raises(RetrievalFailure, match="timed out"):
        fetcher.fetch("https://example.org/a")
