"""Provider-neutral contracts for bounded citation and reference traversal."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from knowledge_engine.federated_discovery import FederatedCandidate, ProviderOutcome, ProviderStatus


class CitationDirection(StrEnum):
    """Direction of one citation-graph expansion from a seed work."""

    REFERENCES = "references"
    CITATIONS = "citations"


@dataclass(frozen=True)
class CitationTraversalQuery:
    """Replayable bounded request for one page of citation-graph expansion."""

    seed_identifier: str
    direction: CitationDirection
    limit: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        if not self.seed_identifier.strip():
            raise ValueError("Citation traversal seed identifier must not be blank.")
        if self.limit < 1 or self.limit > 1000:
            raise ValueError("Citation traversal limit must be between 1 and 1000.")
        if self.offset < 0:
            raise ValueError("Citation traversal offset must not be negative.")

    @property
    def normalized_seed_identifier(self) -> str:
        return self.seed_identifier.strip()


@dataclass(frozen=True)
class CitationEdge:
    """Provider assertion explaining why one candidate was discovered from a seed."""

    provider: str
    seed_identifier: str
    related_provider_id: str
    direction: CitationDirection
    retrieved_at: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Citation edge provider must not be blank.")
        if not self.seed_identifier.strip():
            raise ValueError("Citation edge seed identifier must not be blank.")
        if not self.related_provider_id.strip():
            raise ValueError("Citation edge related provider ID must not be blank.")
        if not self.retrieved_at.strip():
            raise ValueError("Citation edge retrieval timestamp must not be blank.")


@dataclass(frozen=True)
class CitationTraversalResult:
    """One provider's bounded citation page with candidates and edge provenance."""

    query: CitationTraversalQuery
    provider_status: ProviderStatus
    candidates: tuple[FederatedCandidate, ...] = ()
    edges: tuple[CitationEdge, ...] = ()
    next_offset: int | None = None

    def __post_init__(self) -> None:
        if len(self.candidates) != len(self.edges):
            raise ValueError("Citation traversal requires one provenance edge per candidate.")
        if self.provider_status.result_count != len(self.candidates):
            raise ValueError("Citation traversal result_count must match candidate count.")
        if self.next_offset is not None and self.next_offset < 0:
            raise ValueError("Citation traversal next_offset must not be negative.")
        if self.provider_status.outcome == ProviderOutcome.EMPTY and self.candidates:
            raise ValueError("Empty citation traversal cannot contain candidates.")

        normalized_provider = self.provider_status.provider.strip().lower().replace(" ", "_")
        for edge in self.edges:
            edge_provider = edge.provider.strip().lower().replace(" ", "_")
            if edge_provider != normalized_provider:
                raise ValueError("Citation edge provider must match traversal provider status.")
            if edge.direction is not self.query.direction:
                raise ValueError("Citation edge direction must match traversal query direction.")
