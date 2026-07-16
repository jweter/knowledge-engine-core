"""Read authoritative advisory metadata from persisted manifest snapshots."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from knowledge_engine.models import ImportItem


@dataclass(frozen=True, slots=True)
class ManifestItemMetadata:
    """Curated metadata resolved for one stable source identity."""

    publication_year: int | None


def metadata_for_import_item(item: ImportItem) -> ManifestItemMetadata:
    """Resolve curated metadata from the immutable source CSV snapshot.

    Missing, ambiguous, or invalid advisory metadata is treated as unavailable.
    Duplicate safety must never depend on reparsing the current filesystem copy.
    """

    source_id = item.source_id
    source_csv_text = item.run.manifest_snapshot.source_csv_text
    if not source_id or not source_csv_text:
        return ManifestItemMetadata(publication_year=None)

    reader = csv.DictReader(io.StringIO(source_csv_text))
    matches = [row for row in reader if (row.get("source_id") or "").strip() == source_id]
    if len(matches) != 1:
        return ManifestItemMetadata(publication_year=None)

    raw_year = (
        matches[0].get("publication_year")
        or matches[0].get("year")
        or ""
    ).strip()
    try:
        publication_year = int(raw_year)
    except ValueError:
        publication_year = None
    if publication_year is not None and not 1000 <= publication_year <= 9999:
        publication_year = None
    return ManifestItemMetadata(publication_year=publication_year)
