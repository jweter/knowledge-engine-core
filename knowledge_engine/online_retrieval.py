"""Online source retrieval: question to evidence bundle, with no local corpus (KEC-3).

This is the first working step of the online Research Report pipeline. It builds on the
KEC-1 contract (``online_evidence``) and the existing federated discovery broker, and it
keeps no permanent corpus: retrieved text lives in a small, expiring, size-capped cache
whose files are named ``<content_sha256>.txt`` -- the layout ``ke online-evidence-validate
--contents-dir`` already reads.

Safety properties (each covered by tests):

* HTTPS only, no URL credentials, port 443 only.
* Every hostname is resolved first and every address must be globally routable; loopback,
  private, link-local, reserved and shared-address ranges (and IPv4-mapped forms of them)
  are refused. The connection then goes to the *validated address* with the original host
  name for TLS, so a DNS answer cannot change between the check and the connect.
* Redirects are followed manually, at most ``max_redirects`` hops, and every hop passes the
  same checks (a redirect to http, a private address or another port is refused).
* Response size, wall-clock timeout, cache size and cache lifetime are bounded; compressed
  responses are not requested, so there is no decompression expansion.
* Failures are recorded, never hidden: an unretrievable source becomes an ``OnlineSource``
  with a status and a reason, and can never be quoted.
* Excerpts are exact slices of the stored text chosen by plain term overlap with the
  question. Nothing is generated, so nothing can be fabricated, and the finished bundle is
  re-verified against the cache before it is returned.

The stored text is what is hashed. ``text/plain`` is stored exactly as decoded (no newline
translation); HTML/XML is reduced to text by one deterministic function, and that reduced
text is what offsets refer to. PDFs are not extracted in this slice and are reported as
unavailable.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import os
import re
import socket
import ssl
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
)
from knowledge_engine.online_evidence import (
    MAX_EXCERPT_CHARS,
    EvidenceExcerpt,
    OnlineEvidenceBundle,
    OnlineEvidenceError,
    OnlineSource,
    RetrievalStatus,
    verify_against_retrieved_content,
)
from knowledge_engine.utils import normalize_whitespace

USER_AGENT = "knowledge-engine-online-research/1 (+https://github.com/jweter/knowledge-engine-core)"
_CACHE_FILE = re.compile(r"^[0-9a-f]{64}\.txt$")
_TEXT_TYPES = {"text/plain"}
_MARKUP_TYPES = {"text/html", "application/xhtml+xml", "application/xml", "text/xml"}
_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "with",
        "that",
        "this",
        "from",
        "have",
        "has",
        "had",
        "not",
        "but",
        "can",
        "does",
        "did",
        "into",
        "than",
        "then",
        "their",
        "there",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "how",
        "about",
        "after",
        "before",
        "between",
        "during",
        "over",
        "under",
        "again",
        "further",
        "once",
        "only",
        "own",
        "same",
        "some",
        "such",
        "too",
        "very",
        "will",
        "would",
        "could",
        "should",
        "any",
        "all",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "its",
        "it's",
        "you",
        "your",
        "our",
        "out",
        "off",
        "per",
        "via",
    }
)


class UnsafeUrlError(ValueError):
    """A URL, redirect or resolved address that retrieval refuses to contact."""


class RetrievalFailure(Exception):
    """A source could not be retrieved; carries the status and reason to record."""

    def __init__(self, status: RetrievalStatus, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class RetrievalLimits:
    """Every bound on one online research run."""

    max_sources: int = 3
    max_response_bytes: int = 2_000_000
    timeout_seconds: float = 20.0
    max_redirects: int = 3
    max_excerpts_per_source: int = 3
    excerpt_chars: int = 600
    cache_max_bytes: int = 20_000_000
    cache_max_age_seconds: float = 3600.0

    def __post_init__(self) -> None:
        if min(self.max_sources, self.max_excerpts_per_source) < 1:
            raise ValueError("max_sources and max_excerpts_per_source must be positive.")
        if self.max_redirects < 0 or self.timeout_seconds <= 0:
            raise ValueError("max_redirects must not be negative and timeout must be positive.")
        if not 1 <= self.excerpt_chars <= MAX_EXCERPT_CHARS:
            raise ValueError(f"excerpt_chars must be between 1 and {MAX_EXCERPT_CHARS}.")
        if self.max_response_bytes < 1 or self.cache_max_bytes < self.max_response_bytes:
            raise ValueError("cache_max_bytes must be at least max_response_bytes.")
        if self.cache_max_age_seconds <= 0:
            raise ValueError("cache_max_age_seconds must be positive.")


# --- URL safety -------------------------------------------------------------------------


Resolver = Callable[[str, int], Sequence[str]]


def system_resolver(host: str, port: int) -> Sequence[str]:
    """Resolve ``host`` to every address the system would connect to."""

    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise OSError(f"cannot resolve {host}") from error
    return tuple(dict.fromkeys(str(info[4][0]) for info in infos))


def _is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def check_public_https_url(url: str, resolver: Resolver = system_resolver) -> tuple[str, str]:
    """Validate ``url`` and return ``(hostname, validated_ip)`` to connect to.

    Raises ``UnsafeUrlError`` for anything but a plain HTTPS URL whose host resolves
    only to globally routable addresses.
    """

    parts = urlsplit(url.strip())
    if parts.scheme != "https":
        raise UnsafeUrlError(f"only https URLs are retrieved, not {parts.scheme or 'none'!r}")
    host = parts.hostname
    if not host:
        raise UnsafeUrlError("URL has no host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeUrlError("URLs with credentials are refused")
    try:
        port = parts.port
    except ValueError as error:
        raise UnsafeUrlError("URL has an invalid port") from error
    if port not in (None, 443):
        raise UnsafeUrlError(f"port {port} is refused (only 443)")
    try:
        addresses = tuple(resolver(host, 443))
    except OSError as error:
        raise RetrievalFailure(RetrievalStatus.FAILED, f"cannot resolve {host}") from error
    if not addresses:
        raise RetrievalFailure(RetrievalStatus.FAILED, f"{host} resolved to no address")
    blocked = [address for address in addresses if not _is_public_address(address)]
    if blocked:
        raise UnsafeUrlError(f"{host} resolves to a non-public address ({blocked[0]})")
    return host, addresses[0]


# --- Fetching ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchedPage:
    final_url: str
    status: int
    content_type: str
    body: bytes


class Searcher(Protocol):
    """What the workflow needs from discovery (``FederatedDiscoveryBroker`` satisfies it)."""

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        """Run one provider-neutral search."""


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchedPage:
        """Fetch one URL under the retrieval limits, or raise ``RetrievalFailure``."""


class _Response(Protocol):
    status: int

    def getheader(self, name: str, default: str | None = None) -> str | None: ...

    def read(self, amt: int | None = None) -> bytes: ...


class _Connection(Protocol):
    def request(self, method: str, url: str, headers: dict[str, str]) -> None: ...

    def getresponse(self) -> _Response: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[[str, str, float], _Connection]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS to a pre-validated address, with TLS verified against the original host."""

    def __init__(self, host: str, address: str, timeout: float) -> None:
        super().__init__(host, port=443, timeout=timeout)
        self._address = address
        self._tls = ssl.create_default_context()

    def connect(self) -> None:
        sock = socket.create_connection((self._address, 443), self.timeout)
        self.sock = self._tls.wrap_socket(sock, server_hostname=self.host)


def _pinned_connection(host: str, address: str, timeout: float) -> _Connection:
    return _PinnedHTTPSConnection(host, address, timeout)  # type: ignore[return-value]


class SafeHttpsFetcher:
    """Bounded, redirect-checked, address-pinned HTTPS GET."""

    def __init__(
        self,
        limits: RetrievalLimits,
        *,
        resolver: Resolver = system_resolver,
        connection_factory: ConnectionFactory = _pinned_connection,
    ) -> None:
        self._limits = limits
        self._resolver = resolver
        self._connect = connection_factory

    def fetch(self, url: str) -> FetchedPage:
        current = url
        deadline = time.monotonic() + self._limits.timeout_seconds
        for _hop in range(self._limits.max_redirects + 1):
            try:
                host, address = check_public_https_url(current, self._resolver)
            except UnsafeUrlError as error:
                raise RetrievalFailure(
                    RetrievalStatus.NOT_PERMITTED, f"Unsafe URL: {error}"
                ) from error
            parts = urlsplit(current)
            target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
            connection = self._connect(host, address, self._limits.timeout_seconds)
            try:
                connection.request(
                    "GET",
                    target,
                    {
                        "Host": host,
                        "User-Agent": USER_AGENT,
                        "Accept": "text/html, text/plain, application/xml;q=0.9",
                        "Accept-Encoding": "identity",
                    },
                )
                response = connection.getresponse()
                location = response.getheader("Location")
                if 300 <= response.status < 400 and location:
                    current = urljoin(current, location)
                    continue
                return self._finish(current, response, deadline)
            except TimeoutError as error:
                raise RetrievalFailure(RetrievalStatus.FAILED, "Retrieval timed out.") from error
            except (OSError, http.client.HTTPException, ssl.SSLError) as error:
                raise RetrievalFailure(
                    RetrievalStatus.FAILED, f"Transport error: {type(error).__name__}"
                ) from error
            finally:
                connection.close()
        raise RetrievalFailure(
            RetrievalStatus.FAILED, f"More than {self._limits.max_redirects} redirects."
        )

    def _finish(self, url: str, response: _Response, deadline: float) -> FetchedPage:
        limit = self._limits.max_response_bytes
        declared = response.getheader("Content-Length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            raise RetrievalFailure(RetrievalStatus.FAILED, f"Response exceeds {limit} bytes.")
        chunks: list[bytes] = []
        total = 0
        while total <= limit:
            # The socket timeout only bounds each recv; enforce the wall-clock budget here
            # so a server dribbling bytes cannot hold a fetch open indefinitely.
            if time.monotonic() > deadline:
                raise RetrievalFailure(RetrievalStatus.FAILED, "Retrieval timed out.")
            chunk = response.read(min(65536, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        body = b"".join(chunks)
        if len(body) > limit:
            raise RetrievalFailure(RetrievalStatus.FAILED, f"Response exceeds {limit} bytes.")
        return FetchedPage(url, response.status, response.getheader("Content-Type") or "", body)


# --- Bounded temporary cache ------------------------------------------------------------


class CacheBudgetError(OSError):
    """A single text is larger than the whole cache budget."""


class BoundedTextCache:
    """Expiring, size-capped store of retrieved texts, named ``<content_sha256>.txt``.

    It owns one directory and only ever touches files matching that exact name pattern,
    so user documents placed anywhere (including next to it) are never deleted.
    """

    def __init__(
        self,
        directory: Path,
        *,
        max_bytes: int,
        max_age_seconds: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if directory.is_symlink():
            raise ValueError("The cache directory must not be a symbolic link.")
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.max_bytes = max_bytes
        self.max_age_seconds = max_age_seconds
        self._clock = clock

    def put(self, text: str) -> str:
        """Store ``text`` byte-exactly and return its SHA-256."""

        data = text.encode("utf-8")
        if len(data) > self.max_bytes:
            raise CacheBudgetError(f"Text of {len(data)} bytes exceeds the cache budget.")
        digest = hashlib.sha256(data).hexdigest()
        handle, temporary = tempfile.mkstemp(dir=self.directory, suffix=".partial")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            os.replace(temporary, self.directory / f"{digest}.txt")
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.prune(keep={digest})
        return digest

    def get(self, digest: str) -> str | None:
        """Return the cached text if present, unexpired and still matching its hash."""

        path = self.directory / f"{digest}.txt"
        if not _CACHE_FILE.match(path.name) or not path.is_file():
            return None
        if self._clock() - path.stat().st_mtime > self.max_age_seconds:
            return None
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            return None
        return data.decode("utf-8")

    def entries(self) -> list[Path]:
        return sorted(p for p in self.directory.iterdir() if _CACHE_FILE.match(p.name))

    def prune(self, keep: set[str] | None = None) -> list[str]:
        """Delete expired files, then the oldest ones until the budget holds."""

        protected = {f"{digest}.txt" for digest in keep or set()}
        removed: list[str] = []
        now = self._clock()
        for partial in self.directory.glob("*.partial"):  # left behind by an interrupted put
            if now - partial.stat().st_mtime > self.max_age_seconds:
                partial.unlink(missing_ok=True)
        live: list[tuple[float, Path, int]] = []
        for path in self.entries():
            stat = path.stat()
            if path.name not in protected and now - stat.st_mtime > self.max_age_seconds:
                path.unlink(missing_ok=True)
                removed.append(path.name)
            else:
                live.append((stat.st_mtime, path, stat.st_size))
        total = sum(size for _mtime, _path, size in live)
        for _mtime, path, size in sorted(live, key=lambda item: (item[0], item[1].name)):
            if total <= self.max_bytes:
                break
            if path.name in protected:
                continue
            path.unlink(missing_ok=True)
            removed.append(path.name)
            total -= size
        return removed

    def clear(self) -> None:
        for path in self.entries():
            path.unlink(missing_ok=True)


# --- Text extraction --------------------------------------------------------------------


class _TextExtractor(HTMLParser):
    _BLOCKS = frozenset(
        [
            "p",
            "div",
            "br",
            "li",
            "ul",
            "ol",
            "tr",
            "td",
            "th",
            "table",
            "section",
            "article",
            "header",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "title",
            "abstract",
            "sec",
            "body",
            "blockquote",
            "pre",
        ]
    )
    _SKIPPED = frozenset({"script", "style", "head", "noscript", "svg"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIPPED:
            self._skip_depth += 1
        elif tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIPPED:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in self._BLOCKS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._parts.append(data)

    def text(self) -> str:
        return normalize_whitespace("".join(self._parts))


def extract_text(page: FetchedPage) -> str:
    """Reduce a fetched page to the text that is stored, hashed and quoted."""

    media_type = page.content_type.split(";", 1)[0].strip().lower()
    if media_type not in _TEXT_TYPES | _MARKUP_TYPES:
        raise RetrievalFailure(
            RetrievalStatus.UNAVAILABLE,
            f"Unsupported content type {media_type or 'unknown'!r}; only text, HTML and XML "
            "are extracted in this version.",
        )
    message = Message()
    message["content-type"] = page.content_type
    charset = message.get_content_charset() or "utf-8"
    try:
        decoded = page.body.decode(charset)
    except (UnicodeDecodeError, LookupError) as error:
        raise RetrievalFailure(RetrievalStatus.FAILED, "Response is not decodable text.") from error
    if media_type in _TEXT_TYPES:
        text = decoded  # exactly as retrieved: no newline translation or trimming
    else:
        extractor = _TextExtractor()
        extractor.feed(decoded)
        extractor.close()
        text = extractor.text()
    if not text.strip():
        raise RetrievalFailure(RetrievalStatus.UNAVAILABLE, "The page contained no text.")
    return text


# --- Retrieval of one source ------------------------------------------------------------


def candidate_url(observation: ProviderObservation) -> str | None:
    """The URL to retrieve for an observation: full text first, then the landing page."""

    for url in (observation.full_text_url, observation.landing_url):
        if url and url.strip():
            return url.strip()
    return None


def retrieve_source(
    observation: ProviderObservation,
    url: str,
    *,
    fetcher: Fetcher,
    cache: BoundedTextCache,
    now: Callable[[], datetime],
) -> OnlineSource:
    """Retrieve one observation's text into the cache and record the outcome."""

    retrieved_at = now().astimezone(UTC).isoformat()

    def failed(status: RetrievalStatus, reason: str) -> OnlineSource:
        return OnlineSource.from_observation(
            observation,
            url=url,
            retrieved_at=retrieved_at,
            status=status,
            failure_reason=reason,
        )

    try:
        page = fetcher.fetch(url)
        if page.status != 200:
            raise RetrievalFailure(_status_for_http(page.status), f"HTTP {page.status}.")
        text = extract_text(page)
        cache.put(text)
    except RetrievalFailure as failure:
        return failed(failure.status, failure.reason)
    except CacheBudgetError as error:
        return failed(RetrievalStatus.FAILED, str(error))
    return OnlineSource.from_observation(
        observation,
        url=url,
        retrieved_at=retrieved_at,
        status=RetrievalStatus.RETRIEVED,
        content=text,
    )


def _status_for_http(status: int) -> RetrievalStatus:
    if status in (404, 410):
        return RetrievalStatus.UNAVAILABLE
    if status in (401, 402, 403, 451):
        return RetrievalStatus.NOT_PERMITTED
    return RetrievalStatus.FAILED


# --- Excerpt selection ------------------------------------------------------------------

_PARAGRAPH = re.compile(r"\S.*?(?=(?:\r\n|\r|\n)[ \t]*(?:\r\n|\r|\n)|\Z)", re.DOTALL)
_SENTENCE_END = re.compile(r"[.!?](?=\s)")


def question_terms(question: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9][a-z0-9'-]{2,}", question.lower())
    return frozenset(word for word in words if word not in _STOPWORDS)


def select_excerpts(
    source_id: str, text: str, terms: frozenset[str], *, limit: int, max_chars: int
) -> list[EvidenceExcerpt]:
    """The best-matching paragraphs of ``text`` as exact, offset-bearing excerpts."""

    scored: list[tuple[float, int, int, int]] = []
    for index, match in enumerate(_PARAGRAPH.finditer(text)):
        paragraph = match.group()
        found = {t for t in terms if t in paragraph.lower()}
        if found:
            scored.append((-len(found) / len(terms), index, match.start(), len(paragraph)))
    excerpts: list[EvidenceExcerpt] = []
    for _score, index, start, length in sorted(scored)[:limit]:
        end = start + min(length, max_chars)
        if length > max_chars:
            ends = [m.end() for m in _SENTENCE_END.finditer(text, start, end)]
            end = ends[-1] if ends else end
        excerpts.append(
            EvidenceExcerpt.quote(
                source_id, text[start:end], char_start=start, locator=f"paragraph {index + 1}"
            )
        )
    return excerpts


# --- The workflow -----------------------------------------------------------------------


@dataclass(frozen=True)
class OnlineResearchResult:
    """The evidence bundle plus what discovery and selection did, so nothing is hidden."""

    bundle: OnlineEvidenceBundle
    discovery: FederatedSearchResult
    skipped: tuple[tuple[str, str], ...]


def research_online(
    question: str,
    *,
    broker: Searcher,
    fetcher: Fetcher,
    cache: BoundedTextCache,
    limits: RetrievalLimits,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> OnlineResearchResult:
    """Run one question through discovery, retrieval and excerpt selection.

    Returns a valid ``OnlineEvidenceBundle`` with sources and excerpts but no claims:
    drawing claims from excerpts is analysis, which belongs to the report layer.
    """

    cache.prune()
    discovery = broker.search(
        DiscoveryQuery(text=question, limit_per_provider=max(5, limits.max_sources * 2))
    )
    terms = question_terms(question)
    sources: list[OnlineSource] = []
    excerpts: list[EvidenceExcerpt] = []
    skipped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate in discovery.candidates:
        if len(sources) >= limits.max_sources:
            break
        chosen = _first_retrievable(candidate)
        if chosen is None:
            skipped.append((candidate.canonical_id, "no retrievable URL"))
            continue
        observation, url = chosen
        source = retrieve_source(observation, url, fetcher=fetcher, cache=cache, now=now)
        if source.source_id in seen:
            skipped.append((candidate.canonical_id, f"duplicate source {source.source_id}"))
            continue
        seen.add(source.source_id)
        sources.append(source)
        if source.status is RetrievalStatus.RETRIEVED and source.content_sha256:
            text = cache.get(source.content_sha256)
            if text is not None and terms:
                excerpts.extend(
                    select_excerpts(
                        source.source_id,
                        text,
                        terms,
                        limit=limits.max_excerpts_per_source,
                        max_chars=limits.excerpt_chars,
                    )
                )
    bundle = OnlineEvidenceBundle(question, tuple(sources), tuple(excerpts))
    contents = {
        s.source_id: text
        for s in sources
        if s.content_sha256 and (text := cache.get(s.content_sha256)) is not None
    }
    problems = verify_against_retrieved_content(bundle, contents)
    if problems:
        raise OnlineEvidenceError("Internal verification failed: " + "; ".join(problems))
    cache.prune()
    return OnlineResearchResult(bundle, discovery, tuple(skipped))


def _first_retrievable(candidate: FederatedCandidate) -> tuple[ProviderObservation, str] | None:
    for observation in candidate.observations:
        url = candidate_url(observation)
        if url is not None:
            return observation, url
    return None


__all__ = [
    "BoundedTextCache",
    "CacheBudgetError",
    "FetchedPage",
    "Fetcher",
    "Searcher",
    "OnlineResearchResult",
    "RetrievalFailure",
    "RetrievalLimits",
    "SafeHttpsFetcher",
    "UnsafeUrlError",
    "candidate_url",
    "check_public_https_url",
    "extract_text",
    "question_terms",
    "research_online",
    "retrieve_source",
    "select_excerpts",
    "system_resolver",
]
