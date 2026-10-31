"""Online evidence contract: traceable evidence from sources retrieved on demand (KEC-1).

The owner-approved research architecture (docs/OWNER_APPROVED_ROADMAP_2026-10-25.md)
retrieves sources online for each request instead of requiring a preloaded local
corpus. Today's Evidence Records locate their quotes through
``source_span.local_pdf_path``; this contract replaces that corpus dependency with a
retrieval record (URL, UTC retrieval time, content SHA-256), so every excerpt and
every citation stays traceable to what was actually retrieved.

The contract only represents and checks evidence; it never fetches, summarizes,
scores or decides whether a claim is true. Invariants:

* A source's ``source_id`` is derived from its strongest identifier (DOI, PMCID,
  PMID, arXiv ID, then the URL), so the same work gets the same ID in every run.
* A retrieved source records its content hash; an unavailable, refused or failed
  source records why, and can never be cited.
* An excerpt's ``excerpt_id`` is derived from its source, text and offset, and
  ``verify_against_retrieved_content`` proves its text occurs in the retrieved
  content -- an excerpt that cannot be found there is reported, never trusted.
* A claim's status is computed from its citations: support and contradiction
  together are CONTESTED, and no usable citation is INSUFFICIENT_EVIDENCE.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from urllib.parse import urlsplit

from knowledge_engine.federated_discovery import ProviderObservation
from knowledge_engine.utils import (
    normalize_arxiv_id,
    normalize_doi,
    normalize_pmcid,
    normalize_pmid,
)

ONLINE_EVIDENCE_SCHEMA = "ke-online-evidence/v1"
MAX_EXCERPT_CHARS = 1200


class OnlineEvidenceError(ValueError):
    """An online evidence record or bundle violates the contract."""


class RetrievalStatus(StrEnum):
    """Outcome of retrieving one source for one research request."""

    RETRIEVED = "retrieved"
    UNAVAILABLE = "unavailable"  # not found, gone, or no accessible full text
    NOT_PERMITTED = "not_permitted"  # licence, paywall or robots policy forbids use
    FAILED = "failed"  # transport or parsing error


class EvidenceStance(StrEnum):
    """How one cited excerpt bears on one claim."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    INCONCLUSIVE = "inconclusive"


class ClaimStatus(StrEnum):
    """A claim's evidence state, computed from its citations (never asserted)."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    CONTESTED = "contested"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


def content_sha256(content: str) -> str:
    """The content hash recorded for a retrieved source (UTF-8 bytes of its text)."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def source_id_for(
    *,
    doi: str | None = None,
    pmcid: str | None = None,
    pmid: str | None = None,
    arxiv_id: str | None = None,
    url: str | None = None,
) -> str:
    """Stable source identity from the strongest available identifier."""

    for prefix, value, normalize in (
        ("doi", doi, normalize_doi),
        ("pmcid", pmcid, normalize_pmcid),
        ("pmid", pmid, normalize_pmid),
        ("arxiv", arxiv_id, normalize_arxiv_id),
    ):
        if value is not None and value.strip():
            return f"{prefix}:{normalize(value)}"
    if url is not None and url.strip():
        return f"url:{hashlib.sha256(_normalized_url(url).encode('utf-8')).hexdigest()[:16]}"
    raise OnlineEvidenceError("A source needs a DOI, PMCID, PMID, arXiv ID or URL.")


def excerpt_id_for(source_id: str, text: str, char_start: int | None) -> str:
    """Stable excerpt identity: the same quote at the same place gets the same ID."""

    material = f"{source_id}\n{char_start if char_start is not None else ''}\n{text}"
    return f"{source_id}#{hashlib.sha256(material.encode('utf-8')).hexdigest()[:12]}"


@dataclass(frozen=True)
class OnlineSource:
    """One source as retrieved (or not) for one research request."""

    source_id: str
    url: str
    retrieved_at: str
    status: RetrievalStatus
    provider: str
    title: str | None = None
    doi: str | None = None
    pmcid: str | None = None
    pmid: str | None = None
    arxiv_id: str | None = None
    content_sha256: str | None = None
    failure_reason: str | None = None
    license: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, RetrievalStatus):
            raise OnlineEvidenceError(f"Unknown retrieval status: {self.status!r}.")
        _require_http_url(self.url)
        _require_utc_timestamp(self.retrieved_at)
        if not self.provider.strip():
            raise OnlineEvidenceError("A source must name the provider it was retrieved from.")
        expected = source_id_for(
            doi=self.doi, pmcid=self.pmcid, pmid=self.pmid, arxiv_id=self.arxiv_id, url=self.url
        )
        if self.source_id != expected:
            raise OnlineEvidenceError(
                f"source_id {self.source_id!r} does not match its identifiers ({expected!r})."
            )
        if self.status is RetrievalStatus.RETRIEVED:
            if not _is_sha256(self.content_sha256):
                raise OnlineEvidenceError(
                    f"Retrieved source {self.source_id} needs the SHA-256 of its content."
                )
            if self.failure_reason is not None:
                raise OnlineEvidenceError(
                    f"Retrieved source {self.source_id} cannot carry a failure_reason."
                )
        else:
            if self.content_sha256 is not None:
                raise OnlineEvidenceError(
                    f"Source {self.source_id} was not retrieved and cannot carry a content hash."
                )
            if not (self.failure_reason or "").strip():
                raise OnlineEvidenceError(
                    f"Source {self.source_id} ({self.status.value}) must state why."
                )

    @classmethod
    def from_observation(
        cls,
        observation: ProviderObservation,
        *,
        url: str,
        retrieved_at: str,
        status: RetrievalStatus,
        content: str | None = None,
        failure_reason: str | None = None,
    ) -> OnlineSource:
        """Record the retrieval of a federated-discovery observation (FRD contract)."""

        if (status is RetrievalStatus.RETRIEVED) != (content is not None):
            raise OnlineEvidenceError("Content is required exactly when the source was retrieved.")
        identifiers = {
            "doi": observation.doi,
            "pmcid": observation.pmcid,
            "pmid": observation.pmid,
            "arxiv_id": observation.arxiv_id,
        }
        return cls(
            source_id=source_id_for(**identifiers, url=url),
            url=url,
            retrieved_at=retrieved_at,
            status=status,
            provider=observation.normalized_provider,
            title=observation.title,
            content_sha256=content_sha256(content) if content is not None else None,
            failure_reason=failure_reason,
            license=observation.license,
            **identifiers,
        )


@dataclass(frozen=True)
class EvidenceExcerpt:
    """A verbatim passage from one retrieved source."""

    excerpt_id: str
    source_id: str
    text: str
    char_start: int | None = None
    char_end: int | None = None
    locator: str | None = None  # human-readable place, e.g. "Results, paragraph 2"

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise OnlineEvidenceError("An excerpt must quote non-empty text.")
        if len(self.text) > MAX_EXCERPT_CHARS:
            raise OnlineEvidenceError(
                f"Excerpt {self.excerpt_id} exceeds {MAX_EXCERPT_CHARS} characters."
            )
        if (self.char_start is None) != (self.char_end is None):
            raise OnlineEvidenceError("char_start and char_end must be given together.")
        if (
            self.char_start is not None
            and self.char_end is not None
            and (self.char_start < 0 or self.char_end - self.char_start != len(self.text))
        ):
            raise OnlineEvidenceError(
                f"Excerpt {self.excerpt_id} offsets do not span exactly its text."
            )
        expected = excerpt_id_for(self.source_id, self.text, self.char_start)
        if self.excerpt_id != expected:
            raise OnlineEvidenceError(
                f"excerpt_id {self.excerpt_id!r} does not match its content ({expected!r})."
            )

    @classmethod
    def quote(
        cls,
        source_id: str,
        text: str,
        *,
        char_start: int | None = None,
        locator: str | None = None,
    ) -> EvidenceExcerpt:
        """Build an excerpt with its derived ID (and end offset, when a start is given)."""

        return cls(
            excerpt_id=excerpt_id_for(source_id, text, char_start),
            source_id=source_id,
            text=text,
            char_start=char_start,
            char_end=char_start + len(text) if char_start is not None else None,
            locator=locator,
        )


@dataclass(frozen=True)
class Citation:
    """One excerpt cited for one claim, with its stance."""

    excerpt_id: str
    stance: EvidenceStance

    def __post_init__(self) -> None:
        if not isinstance(self.stance, EvidenceStance):
            raise OnlineEvidenceError(f"Unknown evidence stance: {self.stance!r}.")


@dataclass(frozen=True)
class EvidenceClaim:
    """A statement a report may make, with the citations behind it."""

    claim_id: str
    text: str
    citations: tuple[Citation, ...] = ()

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.text.strip():
            raise OnlineEvidenceError("A claim needs a claim_id and text.")

    @property
    def status(self) -> ClaimStatus:
        stances = {citation.stance for citation in self.citations}
        if EvidenceStance.SUPPORTS in stances and EvidenceStance.CONTRADICTS in stances:
            return ClaimStatus.CONTESTED
        if EvidenceStance.SUPPORTS in stances:
            return ClaimStatus.SUPPORTED
        if EvidenceStance.CONTRADICTS in stances:
            return ClaimStatus.CONTRADICTED
        return ClaimStatus.INSUFFICIENT_EVIDENCE


@dataclass(frozen=True)
class OnlineEvidenceBundle:
    """Every source, excerpt and claim gathered for one research question."""

    question: str
    sources: tuple[OnlineSource, ...]
    excerpts: tuple[EvidenceExcerpt, ...] = ()
    claims: tuple[EvidenceClaim, ...] = ()

    def __post_init__(self) -> None:
        problems: list[str] = []
        if not self.question.strip():
            problems.append("The research question must not be empty.")
        for kind, ids in (
            ("source_id", [s.source_id for s in self.sources]),
            ("excerpt_id", [e.excerpt_id for e in self.excerpts]),
            ("claim_id", [c.claim_id for c in self.claims]),
        ):
            problems.extend(
                f"Duplicate {kind}: {value}" for value, n in Counter(ids).items() if n > 1
            )
        sources = {source.source_id: source for source in self.sources}
        for excerpt in self.excerpts:
            source = sources.get(excerpt.source_id)
            if source is None:
                problems.append(f"Excerpt {excerpt.excerpt_id} cites unknown source.")
            elif source.status is not RetrievalStatus.RETRIEVED:
                problems.append(
                    f"Excerpt {excerpt.excerpt_id} quotes a source that was not retrieved "
                    f"({source.status.value})."
                )
        excerpt_ids = {excerpt.excerpt_id for excerpt in self.excerpts}
        for claim in self.claims:
            problems.extend(
                f"Claim {claim.claim_id} cites unknown excerpt {citation.excerpt_id}."
                for citation in claim.citations
                if citation.excerpt_id not in excerpt_ids
            )
        if problems:
            raise OnlineEvidenceError("; ".join(problems))

    @property
    def unavailable_sources(self) -> tuple[OnlineSource, ...]:
        return tuple(s for s in self.sources if s.status is not RetrievalStatus.RETRIEVED)

    def claims_with_status(self, status: ClaimStatus) -> tuple[EvidenceClaim, ...]:
        return tuple(claim for claim in self.claims if claim.status is status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ONLINE_EVIDENCE_SCHEMA,
            "question": self.question,
            "sources": [_source_dict(source) for source in self.sources],
            "excerpts": [
                {
                    "excerpt_id": e.excerpt_id,
                    "source_id": e.source_id,
                    "text": e.text,
                    "char_start": e.char_start,
                    "char_end": e.char_end,
                    "locator": e.locator,
                }
                for e in self.excerpts
            ],
            "claims": [
                {
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "status": c.status.value,
                    "citations": [
                        {"excerpt_id": x.excerpt_id, "stance": x.stance.value} for x in c.citations
                    ],
                }
                for c in self.claims
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OnlineEvidenceBundle:
        if payload.get("schema") != ONLINE_EVIDENCE_SCHEMA:
            raise OnlineEvidenceError(f"Expected schema {ONLINE_EVIDENCE_SCHEMA!r}.")
        try:
            return cls(
                question=payload["question"],
                sources=tuple(
                    OnlineSource(**{**raw, "status": RetrievalStatus(raw["status"])})
                    for raw in payload["sources"]
                ),
                excerpts=tuple(EvidenceExcerpt(**raw) for raw in payload.get("excerpts", [])),
                claims=tuple(
                    EvidenceClaim(
                        claim_id=raw["claim_id"],
                        text=raw["text"],
                        citations=tuple(
                            Citation(x["excerpt_id"], EvidenceStance(x["stance"]))
                            for x in raw.get("citations", [])
                        ),
                    )
                    for raw in payload.get("claims", [])
                ),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, OnlineEvidenceError):
                raise
            raise OnlineEvidenceError(f"Malformed online evidence bundle: {error}") from error


def verify_against_retrieved_content(
    bundle: OnlineEvidenceBundle, contents: Mapping[str, str]
) -> list[str]:
    """Check every excerpt against the content actually retrieved (keyed by source_id).

    Returns the problems found; an empty list means each cited excerpt was found
    verbatim (at its offsets, when given) in content whose hash matches the record.
    A retrieved source whose content is not supplied is reported as unverifiable.
    """

    problems: list[str] = []
    verified: dict[str, str] = {}
    for source in bundle.sources:
        if source.status is not RetrievalStatus.RETRIEVED:
            continue
        content = contents.get(source.source_id)
        if content is None:
            problems.append(f"Source {source.source_id}: retrieved content not supplied.")
        elif content_sha256(content) != source.content_sha256:
            problems.append(f"Source {source.source_id}: content does not match its SHA-256.")
        else:
            verified[source.source_id] = content
    for excerpt in bundle.excerpts:
        content = verified.get(excerpt.source_id)
        if content is None:
            continue
        if excerpt.char_start is not None:
            if content[excerpt.char_start : excerpt.char_end] != excerpt.text:
                problems.append(f"Excerpt {excerpt.excerpt_id}: text is not at its offsets.")
        elif excerpt.text not in content:
            problems.append(f"Excerpt {excerpt.excerpt_id}: text not found in its source.")
    return problems


def _source_dict(source: OnlineSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "url": source.url,
        "retrieved_at": source.retrieved_at,
        "status": source.status.value,
        "provider": source.provider,
        "title": source.title,
        "doi": source.doi,
        "pmcid": source.pmcid,
        "pmid": source.pmid,
        "arxiv_id": source.arxiv_id,
        "content_sha256": source.content_sha256,
        "failure_reason": source.failure_reason,
        "license": source.license,
    }


def _normalized_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return parts._replace(scheme=parts.scheme.lower(), netloc=parts.netloc.lower()).geturl()


def _require_http_url(url: str) -> None:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise OnlineEvidenceError(f"Source URL must be an http(s) URL: {url!r}.")


def _require_utc_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise OnlineEvidenceError(f"retrieved_at is not ISO-8601: {value!r}.") from error
    if parsed.utcoffset() != timedelta(0):
        raise OnlineEvidenceError(f"retrieved_at must be a UTC timestamp: {value!r}.")


def _is_sha256(value: str | None) -> bool:
    return (
        value is not None
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


__all__ = [
    "MAX_EXCERPT_CHARS",
    "ONLINE_EVIDENCE_SCHEMA",
    "Citation",
    "ClaimStatus",
    "EvidenceClaim",
    "EvidenceExcerpt",
    "EvidenceStance",
    "OnlineEvidenceBundle",
    "OnlineEvidenceError",
    "OnlineSource",
    "RetrievalStatus",
    "content_sha256",
    "excerpt_id_for",
    "source_id_for",
    "verify_against_retrieved_content",
]
