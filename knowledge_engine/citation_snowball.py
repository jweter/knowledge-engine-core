"""Bounded, replayable citation-snowball discovery orchestration.

FRD-7 expands known scholarly works through provider citation/reference edges
without introducing evidence interpretation. Core owns the deterministic plan,
bounds, provider outcomes, candidate identity preservation, and edge provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from knowledge_engine.citation_traversal import (
    CitationDirection,
    CitationEdge,
    CitationTraversalQuery,
    CitationTraversalResult,
)
from knowledge_engine.federated_discovery import (
    FederatedCandidate,
    ProviderOutcome,
    SearchCompleteness,
)

_SUCCESSFUL_OUTCOMES = {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY}


class CitationTraversalProvider(Protocol):
    """Provider-neutral citation capability required by snowball discovery."""

    @property
    def name(self) -> str:
        """Stable provider identity."""

    def traverse(self, query: CitationTraversalQuery) -> CitationTraversalResult:
        """Execute one bounded citation traversal."""


@dataclass(frozen=True)
class CitationSnowballPlan:
    """Replayable limits and traversal directions for one snowball run."""

    seed_identifiers: tuple[str, ...]
    directions: tuple[CitationDirection, ...] = (
        CitationDirection.REFERENCES,
        CitationDirection.CITATIONS,
    )
    max_depth: int = 1
    limit_per_traversal: int = 25
    max_candidates: int = 100

    def __post_init__(self) -> None:
        normalized = self.normalized_seed_identifiers
        if not normalized:
            raise ValueError("Citation snowball requires at least one seed identifier.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Citation snowball seed identifiers must be unique.")
        if not self.directions:
            raise ValueError("Citation snowball requires at least one traversal direction.")
        if len(self.directions) != len(set(self.directions)):
            raise ValueError("Citation snowball traversal directions must be unique.")
        if self.max_depth < 1 or self.max_depth > 3:
            raise ValueError("Citation snowball max_depth must be between 1 and 3.")
        if self.limit_per_traversal < 1 or self.limit_per_traversal > 1000:
            raise ValueError("Citation snowball limit_per_traversal must be between 1 and 1000.")
        if self.max_candidates < 1:
            raise ValueError("Citation snowball max_candidates must be positive.")

    @property
    def normalized_seed_identifiers(self) -> tuple[str, ...]:
        return tuple(seed.strip() for seed in self.seed_identifiers if seed.strip())


@dataclass(frozen=True)
class CitationSnowballResult:
    """Deterministic result of one bounded citation-snowball plan."""

    provider: str
    plan: CitationSnowballPlan
    traversals: tuple[CitationTraversalResult, ...]
    candidates: tuple[FederatedCandidate, ...]
    edges: tuple[CitationEdge, ...]
    truncated: bool

    @property
    def completeness(self) -> SearchCompleteness:
        attempted = [item for item in self.traversals if item.provider_status.attempted]
        if not attempted:
            return SearchCompleteness.FAILED
        success_count = sum(
            item.provider_status.outcome in _SUCCESSFUL_OUTCOMES for item in attempted
        )
        if success_count == len(attempted):
            return SearchCompleteness.COMPLETE
        if success_count:
            return SearchCompleteness.PARTIAL
        return SearchCompleteness.FAILED

    @property
    def failed_traversals(self) -> tuple[CitationTraversalResult, ...]:
        return tuple(
            item
            for item in self.traversals
            if item.provider_status.attempted
            and item.provider_status.outcome not in _SUCCESSFUL_OUTCOMES
        )


class CitationSnowballDiscovery:
    """Execute breadth-first citation expansion under explicit hard bounds."""

    def __init__(self, provider: CitationTraversalProvider) -> None:
        self._provider = provider

    def run(self, plan: CitationSnowballPlan) -> CitationSnowballResult:
        """Replay a bounded citation plan without inferring relevance or truth."""

        provider_name = self._provider.name.strip().lower().replace(" ", "_")
        if not provider_name:
            raise ValueError("Citation snowball provider name must not be blank.")

        traversals: list[CitationTraversalResult] = []
        candidates_by_id: dict[str, FederatedCandidate] = {}
        edges: list[CitationEdge] = []
        visited_seeds = set(plan.normalized_seed_identifiers)
        frontier = list(plan.normalized_seed_identifiers)
        truncated = False

        for _depth in range(plan.max_depth):
            next_frontier: list[str] = []
            for seed_identifier in frontier:
                for direction in plan.directions:
                    traversal = self._provider.traverse(
                        CitationTraversalQuery(
                            seed_identifier=seed_identifier,
                            direction=direction,
                            limit=plan.limit_per_traversal,
                        )
                    )
                    self._validate_provider(traversal, expected_provider=provider_name)
                    traversals.append(traversal)

                    if traversal.provider_status.outcome not in _SUCCESSFUL_OUTCOMES:
                        continue

                    for candidate, edge in zip(
                        traversal.candidates,
                        traversal.edges,
                        strict=True,
                    ):
                        if edge.related_provider_id not in visited_seeds:
                            visited_seeds.add(edge.related_provider_id)
                            next_frontier.append(edge.related_provider_id)

                        if candidate.canonical_id in candidates_by_id:
                            edges.append(edge)
                            continue
                        if len(candidates_by_id) >= plan.max_candidates:
                            truncated = True
                            break

                        candidates_by_id[candidate.canonical_id] = candidate
                        edges.append(edge)

                    if truncated:
                        break
                if truncated:
                    break
            if truncated or not next_frontier:
                break
            frontier = next_frontier

        return CitationSnowballResult(
            provider=provider_name,
            plan=plan,
            traversals=tuple(traversals),
            candidates=tuple(candidates_by_id.values()),
            edges=tuple(edges),
            truncated=truncated,
        )

    @staticmethod
    def _validate_provider(
        traversal: CitationTraversalResult,
        *,
        expected_provider: str,
    ) -> None:
        actual_provider = traversal.provider_status.provider.strip().lower().replace(" ", "_")
        if actual_provider != expected_provider:
            raise ValueError("Citation traversal provider identity changed during snowball run.")
