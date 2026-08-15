"""Provider-neutral contracts for bounded scholarly citation traversal."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge_engine.federated_discovery import ProviderStatus


class CitationDirection(StrEnum):
    """Direction of one citation traversal from a seed scholarly work."""

    REFERENCES = "references"
    CITED_BY = "cited_by"


@dataclass(frozen=True)
class CitationEdge:
    """One provider-observed citation edge.

    ``source_id`` and ``target_id`` are provider-native work identifiers.  For
    ``references`` traversal, the seed is the source.  For ``cited_by`` traversal,
    the newly discovered work is the source and the seed is the target.
    """

    provider: str
    source_id: str
    target_id: str
    observed_at: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Citation edge provider must not be empty.")
        if not self.source_id.strip() or not self.target_id.strip():
            raise ValueError("Citation edge work IDs must not be empty.")
        if not self.observed_at.strip():
            raise ValueError("Citation edge observed_at must not be empty.")


@dataclass(frozen=True)
class CitationTraversalResult:
    """Deterministic result of one bounded provider citation traversal."""

    provider: str
    seed_id: str
    direction: CitationDirection
    requested_limit: int
    provider_status: ProviderStatus
    edges: tuple[CitationEdge, ...] = ()

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Citation traversal provider must not be empty.")
        if not self.seed_id.strip():
            raise ValueError("Citation traversal seed_id must not be empty.")
        if self.requested_limit < 1:
            raise ValueError("Citation traversal limit must be positive.")
        if self.provider_status.provider.strip().lower() != self.provider.strip().lower():
            raise ValueError("Citation traversal provider status must match provider.")
        if len(self.edges) > self.requested_limit:
            raise ValueError("Citation traversal returned more edges than requested.")

    @property
    def discovered_ids(self) -> tuple[str, ...]:
        """Return newly discovered provider-native IDs in deterministic order."""
        if self.direction == CitationDirection.REFERENCES:
            return tuple(edge.target_id for edge in self.edges)
        return tuple(edge.source_id for edge in self.edges)
