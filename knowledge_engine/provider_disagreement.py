"""Deterministic inspection of provider metadata disagreement.

Disagreement is descriptive metadata quality state, not evidence adjudication.
The functions in this module preserve every observed provider assertion and never
select a preferred provider value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from knowledge_engine.federated_discovery import FederatedCandidate, ProviderObservation
from knowledge_engine.utils import normalize_doi

ObservedValue: TypeAlias = str | int | bool


@dataclass(frozen=True)
class ProviderAssertion:
    """One provider-native assertion retained in a disagreement report."""

    provider: str
    provider_id: str
    value: ObservedValue


@dataclass(frozen=True)
class ProviderDisagreement:
    """Observed conflicting values for one metadata field."""

    field: str
    assertions: tuple[ProviderAssertion, ...]

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("Disagreement field must not be blank.")
        if len(self.assertions) < 2:
            raise ValueError("A provider disagreement requires at least two assertions.")


_FIELD_ORDER = (
    "title",
    "publication_year",
    "venue",
    "doi",
    "open_access",
    "retracted",
    "citation_count",
)


def inspect_provider_disagreements(candidate: FederatedCandidate) -> tuple[ProviderDisagreement, ...]:
    """Return deterministic disagreements without inferring which value is true.

    Missing values do not count as disagreement. Cosmetic title/venue whitespace
    and case differences are normalized for comparison while original provider
    values remain visible in the returned assertions. DOI comparison uses the
    project's canonical DOI normalization.
    """

    disagreements: list[ProviderDisagreement] = []
    for field in _FIELD_ORDER:
        assertions = _assertions_for_field(candidate.observations, field)
        if len(assertions) < 2:
            continue
        comparable_values = {_comparable_value(field, assertion.value) for assertion in assertions}
        if len(comparable_values) > 1:
            disagreements.append(ProviderDisagreement(field=field, assertions=assertions))
    return tuple(disagreements)


def _assertions_for_field(
    observations: tuple[ProviderObservation, ...],
    field: str,
) -> tuple[ProviderAssertion, ...]:
    assertions: list[ProviderAssertion] = []
    for observation in observations:
        value = _observed_value(observation, field)
        if value is None:
            continue
        assertions.append(
            ProviderAssertion(
                provider=observation.normalized_provider,
                provider_id=observation.provider_id,
                value=value,
            )
        )
    return tuple(assertions)


def _observed_value(observation: ProviderObservation, field: str) -> ObservedValue | None:
    value = getattr(observation, field)
    if isinstance(value, (str, int, bool)):
        return value
    return None


def _comparable_value(field: str, value: ObservedValue) -> ObservedValue:
    if isinstance(value, str):
        if field == "doi":
            return normalize_doi(value) or value.strip().casefold()
        if field in {"title", "venue"}:
            return " ".join(value.split()).casefold()
        return value.strip()
    return value
