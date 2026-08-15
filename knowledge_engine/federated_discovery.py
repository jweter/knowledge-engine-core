"""Provider-neutral contracts for federated scholarly discovery.

FRD-1 deliberately defines representation before orchestration. Existing
provider implementations keep their current behavior until explicit adapters and
parity tests are added. These types make partial provider failure, provider-native
identity, provenance, and missing metadata representable without letting a
provider-specific object become a public Knowledge Engine contract.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class ProviderOutcome(StrEnum):
    """Deterministic outcome of one provider attempt."""

    SUCCESS = "success"
    EMPTY = "empty"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


class SearchCompleteness(StrEnum):
    """Run-level status derived only from provider facts."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class DiscoveryQuery:
    """Normalized provider-neutral scholarly-search request."""

    text: str
    year_from: int | None = None
    year_to: int | None = None
    limit_per_provider: int = 20

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("Discovery query text must not be empty.")
        if self.limit_per_provider < 1:
            raise ValueError("Discovery limit must be positive.")
        if self.year_from is not None and not 1000 <= self.year_from <= 9999:
            raise ValueError("year_from must be a four-digit year.")
        if self.year_to is not None and not 1000 <= self.year_to <= 9999:
            raise ValueError("year_to must be a four-digit year.")
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from must not be after year_to.")

    @property
    def normalized_text(self) -> str:
        return " ".join(self.text.split())


@dataclass(frozen=True)
class ProviderObservation:
    """One provider's observation of one scholarly work.

    Missing provider fields remain ``None``. Provider-generated summaries are
    intentionally not part of this scientific-evidence contract.
    """

    provider: str
    provider_id: str
    title: str
    authors: tuple[str, ...] = ()
    publication_year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    landing_url: str | None = None
    full_text_url: str | None = None
    citation_count: int | None = None
    open_access: bool | None = None
    retracted: bool | None = None
    retrieved_at: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Provider name must not be empty.")
        if not self.provider_id.strip():
            raise ValueError("Provider-native ID must not be empty.")
        if not self.title.strip():
            raise ValueError("Candidate title must not be empty.")
        if self.publication_year is not None and not 1000 <= self.publication_year <= 9999:
            raise ValueError("publication_year must be a four-digit year.")
        if self.citation_count is not None and self.citation_count < 0:
            raise ValueError("citation_count must not be negative.")

    @property
    def normalized_provider(self) -> str:
        return self.provider.strip().lower().replace(" ", "_")


@dataclass(frozen=True)
class FederatedCandidate:
    """Canonical candidate representation with preserved provider observations.

    ``canonical_id`` is an internal run identity, not proof that every provider
    observation has been definitively deduplicated into one scholarly work.
    Deduplication policy is a later FRD milestone.
    """

    canonical_id: str
    title: str
    observations: tuple[ProviderObservation, ...]
    doi: str | None = None
    publication_year: int | None = None

    def __post_init__(self) -> None:
        if not self.canonical_id.strip():
            raise ValueError("Canonical candidate ID must not be empty.")
        if not self.title.strip():
            raise ValueError("Canonical candidate title must not be empty.")
        if not self.observations:
            raise ValueError("A federated candidate requires at least one observation.")

    @property
    def providers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(obs.normalized_provider for obs in self.observations))


@dataclass(frozen=True)
class ProviderStatus:
    """One provider's recorded outcome for one federated search run."""

    provider: str
    outcome: ProviderOutcome
    attempted: bool
    result_count: int = 0
    latency_ms: int | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Provider name must not be empty.")
        if self.result_count < 0:
            raise ValueError("Provider result_count must not be negative.")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("Provider latency must not be negative.")
        if self.outcome in {ProviderOutcome.SKIPPED, ProviderOutcome.DISABLED} and self.attempted:
            raise ValueError("Skipped or disabled providers must not be marked attempted.")
        if (
            self.outcome not in {ProviderOutcome.SKIPPED, ProviderOutcome.DISABLED}
            and not self.attempted
        ):
            raise ValueError("Non-skipped provider outcomes must be marked attempted.")
        if self.outcome in {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY} and self.reason:
            raise ValueError("Successful/empty provider outcomes must not carry a failure reason.")
        if self.outcome == ProviderOutcome.EMPTY and self.result_count != 0:
            raise ValueError("An empty provider result must have result_count == 0.")


@dataclass(frozen=True)
class FederatedSearchResult:
    """Stable result contract for a complete or degraded federated search."""

    query: DiscoveryQuery
    provider_statuses: tuple[ProviderStatus, ...]
    candidates: tuple[FederatedCandidate, ...] = ()

    def __post_init__(self) -> None:
        providers = [status.provider.strip().lower() for status in self.provider_statuses]
        if len(providers) != len(set(providers)):
            raise ValueError("Provider statuses must contain each provider at most once.")

    @property
    def completeness(self) -> SearchCompleteness:
        attempted = [status for status in self.provider_statuses if status.attempted]
        if not attempted:
            return SearchCompleteness.FAILED
        successful = {
            ProviderOutcome.SUCCESS,
            ProviderOutcome.EMPTY,
        }
        success_count = sum(status.outcome in successful for status in attempted)
        if success_count == len(attempted):
            return SearchCompleteness.COMPLETE
        if success_count > 0:
            return SearchCompleteness.PARTIAL
        return SearchCompleteness.FAILED

    @property
    def failed_providers(self) -> tuple[str, ...]:
        accepted = {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY}
        return tuple(
            status.provider
            for status in self.provider_statuses
            if status.attempted and status.outcome not in accepted
        )

    def to_json(self) -> str:
        payload = asdict(self)
        payload["query"]["text"] = self.query.normalized_text
        payload["completeness"] = self.completeness.value
        payload["failed_providers"] = list(self.failed_providers)
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
