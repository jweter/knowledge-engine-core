"""Adapt the mature Crossref DOI lookup provider to the FRD contract."""

from __future__ import annotations

import re
from typing import Protocol

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.metadata_enrichment import (
    MetadataCandidate,
    MetadataProviderResult,
    MetadataQuery,
    PublicationStatusSignal,
)
from knowledge_engine.utils import normalize_doi

_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class CrossrefMetadataProvider(Protocol):
    """Structural subset of the existing Crossref provider used by FRD."""

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        """Return bounded metadata candidates for one DOI."""


class CrossrefFederatedAdapter:
    """Expose exact-DOI Crossref lookup through the provider-neutral FRD contract.

    Crossref's existing provider is intentionally a DOI metadata lookup, not a
    general text-search implementation. This adapter preserves that boundary:
    exact DOI queries are supported, while free-text and year-filtered searches
    fail explicitly instead of silently widening or ignoring the request.
    """

    def __init__(self, provider: CrossrefMetadataProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return "crossref"

    def search(self, query: DiscoveryQuery) -> FederatedSearchResult:
        if query.year_from is not None or query.year_to is not None:
            return _failure_result(query, ProviderOutcome.FAILED, "unsupported_filter")

        doi = normalize_doi(query.normalized_text)
        if not _DOI_PATTERN.fullmatch(doi):
            return _failure_result(query, ProviderOutcome.FAILED, "unsupported_query")

        result = self._provider.lookup(MetadataQuery(doi=doi))
        if result.candidates and result.diagnostics:
            return _failure_result(query, ProviderOutcome.FAILED, "provider_result_mismatch")

        if result.diagnostics:
            if len(result.diagnostics) != 1:
                return _failure_result(query, ProviderOutcome.FAILED, "provider_result_mismatch")
            diagnostic = result.diagnostics[0]
            if diagnostic.provider.strip().lower() != "crossref":
                return _failure_result(query, ProviderOutcome.FAILED, "provider_result_mismatch")
            return _diagnostic_result(query, diagnostic.code)

        if not result.candidates:
            return _failure_result(query, ProviderOutcome.FAILED, "candidate_contract_mismatch")

        try:
            candidate = _to_federated_candidate(
                result.candidates,
                queried_doi=doi,
                publication_status=result.publication_status,
            )
        except (TypeError, ValueError):
            return _failure_result(query, ProviderOutcome.FAILED, "candidate_contract_mismatch")

        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider="crossref",
                    outcome=ProviderOutcome.SUCCESS,
                    attempted=True,
                    result_count=1,
                ),
            ),
            candidates=(candidate,),
        )


def _diagnostic_result(query: DiscoveryQuery, code: str) -> FederatedSearchResult:
    if code == "no_match":
        return FederatedSearchResult(
            query=query,
            provider_statuses=(
                ProviderStatus(
                    provider="crossref",
                    outcome=ProviderOutcome.EMPTY,
                    attempted=True,
                ),
            ),
        )
    if code == "rate_limited":
        return _failure_result(query, ProviderOutcome.RATE_LIMITED, "rate_limited")
    if code in {"provider_unavailable", "timeout", "transport_error"}:
        return _failure_result(query, ProviderOutcome.UNAVAILABLE, code)
    if code in {"malformed_response", "oversized_response"}:
        return _failure_result(query, ProviderOutcome.FAILED, code)
    return _failure_result(query, ProviderOutcome.FAILED, "provider_error")


def _to_federated_candidate(
    candidates: tuple[MetadataCandidate, ...],
    *,
    queried_doi: str,
    publication_status: PublicationStatusSignal | None = None,
) -> FederatedCandidate:
    provider_ids: set[str] = set()
    retrieved_at_values: set[str] = set()
    singular: dict[str, str] = {}
    authors: list[str] = []

    for candidate in candidates:
        if candidate.provider.strip().lower() != "crossref":
            raise ValueError("Unexpected candidate provider.")
        if normalize_doi(candidate.queried_identifier) != queried_doi:
            raise ValueError("Crossref candidate query does not match the requested DOI.")
        if not candidate.provider_record_id:
            raise ValueError("Crossref candidate is missing its provider record ID.")

        provider_id = normalize_doi(candidate.provider_record_id)
        if provider_id != queried_doi:
            raise ValueError("Crossref provider record ID does not match the requested DOI.")
        provider_ids.add(provider_id)
        retrieved_at_values.add(candidate.retrieved_at.isoformat())

        if candidate.field == "author":
            authors.append(candidate.value)
            continue
        if candidate.field in {"doi", "title", "journal", "publication_year"}:
            previous = singular.get(candidate.field)
            if previous is not None and previous != candidate.value:
                raise ValueError("Crossref returned conflicting values for one field.")
            singular[candidate.field] = candidate.value

    if provider_ids != {queried_doi} or len(retrieved_at_values) != 1:
        raise ValueError("Crossref candidate provenance is inconsistent.")

    returned_doi = singular.get("doi")
    if returned_doi is not None and normalize_doi(returned_doi) != queried_doi:
        raise ValueError("Crossref returned a different DOI than requested.")

    title = singular.get("title")
    if title is None or not title.strip():
        raise ValueError("Crossref result is missing a title.")

    publication_year: int | None = None
    year_text = singular.get("publication_year")
    if year_text is not None:
        publication_year = int(year_text)
        if not 1000 <= publication_year <= 9999:
            raise ValueError("Crossref publication year is invalid.")

    retrieved_at = next(iter(retrieved_at_values))
    if publication_status is not None:
        if publication_status.provider.strip().lower() != "crossref":
            raise ValueError("Crossref publication status provider does not match.")
        status = publication_status
    else:
        status = PublicationStatusSignal(provider="crossref")
    observation = ProviderObservation(
        provider="crossref",
        provider_id=queried_doi,
        title=title,
        authors=tuple(authors),
        publication_year=publication_year,
        venue=singular.get("journal"),
        doi=queried_doi,
        metadata_source="crossref",
        retrieved_at=retrieved_at,
        retracted=status.retracted,
        corrected=status.corrected,
        expression_of_concern=status.expression_of_concern,
        withdrawn=status.withdrawn,
    )
    return FederatedCandidate(
        canonical_id=f"crossref:{queried_doi}",
        title=title,
        observations=(observation,),
        doi=queried_doi,
        publication_year=publication_year,
    )


def _failure_result(
    query: DiscoveryQuery,
    outcome: ProviderOutcome,
    reason: str,
) -> FederatedSearchResult:
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="crossref",
                outcome=outcome,
                attempted=True,
                reason=reason,
            ),
        ),
    )
