"""Pure Crossref response parsing for metadata enrichment.

This module accepts already-decoded response data. It performs no network access and
has no persistence dependency, which keeps provider schema handling deterministic and
testable.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import cast

from knowledge_engine.metadata_enrichment import (
    MetadataCandidate,
    MetadataProviderResult,
    MetadataQuery,
    ProviderDiagnostic,
    normalize_candidate_value,
    validate_candidates,
)


def parse_crossref_work(
    payload: object,
    *,
    query: MetadataQuery,
    retrieved_at: datetime,
) -> MetadataProviderResult:
    """Convert one decoded Crossref work response into bounded candidates."""

    root = _mapping(payload)
    if root is None:
        return _malformed("Crossref response must be a JSON object.")

    message = _mapping(root.get("message"))
    if message is None:
        return _malformed("Crossref response is missing a work object.")

    provider_record_id = _text(message.get("DOI")) or query.normalized_doi
    candidate_values: list[tuple[str, str]] = []

    doi = _text(message.get("DOI"))
    if doi:
        candidate_values.append(("doi", doi))

    title = _first_text(message.get("title"))
    if title:
        candidate_values.append(("title", title))

    journal = _first_text(message.get("container-title"))
    if journal:
        candidate_values.append(("journal", journal))

    publication_year = _publication_year(message)
    if publication_year:
        candidate_values.append(("publication_year", publication_year))

    for author in _authors(message.get("author")):
        candidate_values.append(("author", author))

    for issn in _texts(message.get("ISSN")):
        candidate_values.append(("issn", issn))

    candidates = [
        MetadataCandidate(
            provider="crossref",
            provider_record_id=provider_record_id,
            queried_identifier=query.normalized_doi,
            field=cast("MetadataField", field),
            value=value,
            normalized_value=normalize_candidate_value(cast("MetadataField", field), value),
            retrieved_at=retrieved_at,
        )
        for field, value in candidate_values
    ]

    return MetadataProviderResult(candidates=validate_candidates(candidates))


def _mapping(value: object) -> Mapping[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    return cast(Mapping[str, object], value)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    compact = " ".join(value.split())
    return compact or None


def _first_text(value: object) -> str | None:
    values = _texts(value)
    return values[0] if values else None


def _texts(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    texts = tuple(text for item in value if (text := _text(item)) is not None)
    return texts[:32]


def _authors(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    names: list[str] = []
    for item in value[:64]:
        author = _mapping(item)
        if author is None:
            continue
        given = _text(author.get("given"))
        family = _text(author.get("family"))
        name = " ".join(part for part in (given, family) if part)
        if name:
            names.append(name)
    return tuple(names)


def _publication_year(message: Mapping[str, object]) -> str | None:
    for field in ("published-print", "published-online", "issued"):
        date = _mapping(message.get(field))
        if date is None:
            continue
        parts = date.get("date-parts")
        if not isinstance(parts, list) or not parts:
            continue
        first = parts[0]
        if not isinstance(first, list) or not first:
            continue
        year = first[0]
        if isinstance(year, int) and 1000 <= year <= 9999:
            return str(year)
    return None


def _malformed(message: str) -> MetadataProviderResult:
    return MetadataProviderResult(
        diagnostics=(
            ProviderDiagnostic(
                provider="crossref",
                code="malformed_response",
                message=message,
            ),
        )
    )
