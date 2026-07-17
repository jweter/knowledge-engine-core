"""Pure comparison of provider candidates with protected local metadata evidence."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from knowledge_engine.metadata_enrichment import (
    CandidateDisposition,
    MetadataCandidate,
    MetadataField,
    classify_candidate,
)

ProtectedMetadataSource = Literal["curated_manifest", "parser", "preferred"]


@dataclass(frozen=True)
class ProtectedMetadataValue:
    """One local value whose ownership must remain visible during enrichment."""

    source: ProtectedMetadataSource
    field: MetadataField
    value: str


@dataclass(frozen=True)
class CandidateComparison:
    """One explicit comparison between provider evidence and local ownership."""

    candidate: MetadataCandidate
    disposition: CandidateDisposition
    protected_source: ProtectedMetadataSource | None
    protected_value: str | None


def compare_candidates(
    candidates: Sequence[MetadataCandidate],
    protected_values: Sequence[ProtectedMetadataValue],
) -> tuple[CandidateComparison, ...]:
    """Compare candidates without selecting, promoting, or overwriting any value."""

    comparisons: list[CandidateComparison] = []
    for candidate in candidates:
        matching_values = [
            protected for protected in protected_values if protected.field == candidate.field
        ]
        if not matching_values:
            comparisons.append(
                CandidateComparison(
                    candidate=candidate,
                    disposition="fills_missing",
                    protected_source=None,
                    protected_value=None,
                )
            )
            continue

        for protected in matching_values:
            comparisons.append(
                CandidateComparison(
                    candidate=candidate,
                    disposition=classify_candidate(
                        field=candidate.field,
                        protected_value=protected.value,
                        candidate_value=candidate.value,
                    ),
                    protected_source=protected.source,
                    protected_value=protected.value,
                )
            )

    return tuple(comparisons)
