"""Provider-neutral metadata enrichment domain contracts.

This module intentionally has no database or network dependency. External providers
return bounded candidate values and diagnostics; orchestration decides whether and
how those candidates are displayed or persisted.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from knowledge_engine.utils import normalize_doi

MetadataField = Literal[
    "doi",
    "title",
    "publication_year",
    "journal",
    "author",
    "issn",
]
CandidateDisposition = Literal["corroborates", "fills_missing", "conflicts"]
DiagnosticCode = Literal[
    "no_match",
    "rate_limited",
    "provider_unavailable",
    "timeout",
    "transport_error",
    "malformed_response",
    "oversized_response",
]


@dataclass(frozen=True)
class MetadataQuery:
    """Narrow external metadata lookup request."""

    doi: str

    @property
    def normalized_doi(self) -> str:
        """Return the canonical DOI used for provider lookup and comparison."""

        return normalize_doi(self.doi)


@dataclass(frozen=True)
class MetadataCandidate:
    """One bounded provider-supplied value with reproducible provenance."""

    provider: str
    provider_record_id: str | None
    queried_identifier: str
    field: MetadataField
    value: str
    normalized_value: str
    retrieved_at: datetime


@dataclass(frozen=True)
class ProviderDiagnostic:
    """Sanitized provider outcome that is safe for CLI display or later persistence."""

    provider: str
    code: DiagnosticCode
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class MetadataProviderResult:
    """Candidates and diagnostics returned by one provider lookup."""

    candidates: tuple[MetadataCandidate, ...] = ()
    diagnostics: tuple[ProviderDiagnostic, ...] = ()


class MetadataProvider(Protocol):
    """External metadata provider boundary with no persistence dependency."""

    @property
    def name(self) -> str:
        """Return a stable provider identifier."""

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        """Return typed candidates and sanitized diagnostics for one query."""


def normalize_candidate_value(field: MetadataField, value: str) -> str:
    """Normalize a candidate value for deterministic comparison only."""

    compact = " ".join(value.split())
    if field == "doi":
        return normalize_doi(compact)
    if field in {"title", "journal", "author"}:
        return compact.casefold()
    if field in {"publication_year", "issn"}:
        return compact.casefold()
    raise ValueError(f"Unsupported metadata field: {field}")


def classify_candidate(
    *,
    field: MetadataField,
    protected_value: str | None,
    candidate_value: str,
) -> CandidateDisposition:
    """Classify a provider value without promoting or overwriting metadata."""

    candidate_normalized = normalize_candidate_value(field, candidate_value)
    if not candidate_normalized:
        raise ValueError("Candidate value must not be blank.")

    if protected_value is None or not protected_value.strip():
        return "fills_missing"

    protected_normalized = normalize_candidate_value(field, protected_value)
    if protected_normalized == candidate_normalized:
        return "corroborates"
    return "conflicts"


def validate_candidates(
    candidates: Sequence[MetadataCandidate],
) -> tuple[MetadataCandidate, ...]:
    """Validate basic size and provenance invariants for provider output."""

    validated: list[MetadataCandidate] = []
    for candidate in candidates:
        if not candidate.provider.strip():
            raise ValueError("Candidate provider must not be blank.")
        if not candidate.queried_identifier.strip():
            raise ValueError("Candidate queried identifier must not be blank.")
        if not candidate.value.strip():
            raise ValueError("Candidate value must not be blank.")
        if len(candidate.value) > 4096:
            raise ValueError("Candidate value exceeds the 4096-character limit.")
        expected_normalized = normalize_candidate_value(candidate.field, candidate.value)
        if candidate.normalized_value != expected_normalized:
            raise ValueError(
                "Candidate normalized value does not match deterministic normalization."
            )
        validated.append(candidate)
    return tuple(validated)
