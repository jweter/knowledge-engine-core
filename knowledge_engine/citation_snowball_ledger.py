"""Durable local ledger for replayable citation-snowball discovery.

The ledger stores only deterministic plan, traversal outcome, candidate identity,
and citation-edge provenance. Provider credentials, request headers, raw provider
responses, and model context remain outside this persistence boundary.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from knowledge_engine.citation_snowball import CitationSnowballResult

LEDGER_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class CitationTraversalRecord:
    """Persisted outcome of one provider traversal inside a snowball run."""

    seed_identifier: str
    direction: str
    outcome: str
    attempted: bool
    result_count: int
    reason: str | None


@dataclass(frozen=True)
class CitationEdgeRecord:
    """Persisted provider assertion explaining one discovery edge."""

    provider: str
    seed_identifier: str
    related_provider_id: str
    direction: str
    retrieved_at: str


@dataclass(frozen=True)
class CitationSnowballRunRecord:
    """Immutable replay metadata for one bounded citation-snowball run."""

    schema_version: int
    snowball_run_id: str
    created_at: str
    provider: str
    seed_identifiers: tuple[str, ...]
    directions: tuple[str, ...]
    max_depth: int
    limit_per_traversal: int
    max_candidates: int
    completeness: str
    truncated: bool
    candidate_ids: tuple[str, ...]
    traversals: tuple[CitationTraversalRecord, ...]
    edges: tuple[CitationEdgeRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seed_identifiers"] = list(self.seed_identifiers)
        payload["directions"] = list(self.directions)
        payload["candidate_ids"] = list(self.candidate_ids)
        payload["traversals"] = [asdict(item) for item in self.traversals]
        payload["edges"] = [asdict(item) for item in self.edges]
        return payload


class CitationSnowballLedger:
    """Persist citation-snowball runs as write-once local JSON records."""

    def __init__(
        self,
        root: Path,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self._root = root
        self._clock = clock or (lambda: datetime.now(UTC))
        self._id_factory = id_factory or uuid4

    def record(self, result: CitationSnowballResult) -> CitationSnowballRunRecord:
        """Persist one deterministic snowball result and return its run record."""

        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("Citation snowball ledger clock must be timezone-aware.")

        record = CitationSnowballRunRecord(
            schema_version=LEDGER_SCHEMA_VERSION,
            snowball_run_id=str(self._id_factory()),
            created_at=created_at.astimezone(UTC).isoformat(),
            provider=result.provider,
            seed_identifiers=result.plan.normalized_seed_identifiers,
            directions=tuple(direction.value for direction in result.plan.directions),
            max_depth=result.plan.max_depth,
            limit_per_traversal=result.plan.limit_per_traversal,
            max_candidates=result.plan.max_candidates,
            completeness=result.completeness.value,
            truncated=result.truncated,
            candidate_ids=tuple(candidate.canonical_id for candidate in result.candidates),
            traversals=tuple(
                CitationTraversalRecord(
                    seed_identifier=item.query.normalized_seed_identifier,
                    direction=item.query.direction.value,
                    outcome=item.provider_status.outcome.value,
                    attempted=item.provider_status.attempted,
                    result_count=item.provider_status.result_count,
                    reason=item.provider_status.reason,
                )
                for item in result.traversals
            ),
            edges=tuple(
                CitationEdgeRecord(
                    provider=edge.provider,
                    seed_identifier=edge.seed_identifier,
                    related_provider_id=edge.related_provider_id,
                    direction=edge.direction.value,
                    retrieved_at=edge.retrieved_at,
                )
                for edge in result.edges
            ),
        )
        self._write_once(record)
        return record

    def load(self, snowball_run_id: str) -> CitationSnowballRunRecord:
        """Load one persisted run by UUID and validate its durable shape."""

        normalized_id = str(UUID(snowball_run_id))
        path = self._root / f"{normalized_id}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Citation snowball run record is malformed.") from exc
        return _record_from_payload(payload, expected_run_id=normalized_id)

    def _write_once(self, record: CitationSnowballRunRecord) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{record.snowball_run_id}.json"
        if target.exists():
            raise FileExistsError(
                f"Citation snowball run record already exists: {record.snowball_run_id}"
            )

        temporary = target.with_suffix(".json.tmp")
        payload = json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n"
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists():
                raise FileExistsError(
                    f"Citation snowball run record already exists: {record.snowball_run_id}"
                )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)


def _record_from_payload(
    payload: object,
    *,
    expected_run_id: str,
) -> CitationSnowballRunRecord:
    if not isinstance(payload, dict):
        raise ValueError("Citation snowball run record must be a JSON object.")
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise ValueError("Unsupported citation snowball ledger schema version.")
    if payload.get("snowball_run_id") != expected_run_id:
        raise ValueError("Citation snowball run ID does not match its filename.")

    return CitationSnowballRunRecord(
        schema_version=LEDGER_SCHEMA_VERSION,
        snowball_run_id=expected_run_id,
        created_at=_required_string(payload, "created_at"),
        provider=_required_string(payload, "provider"),
        seed_identifiers=_string_tuple(payload, "seed_identifiers"),
        directions=_string_tuple(payload, "directions"),
        max_depth=_positive_int(payload, "max_depth"),
        limit_per_traversal=_positive_int(payload, "limit_per_traversal"),
        max_candidates=_positive_int(payload, "max_candidates"),
        completeness=_required_string(payload, "completeness"),
        truncated=_required_bool(payload, "truncated"),
        candidate_ids=_string_tuple(payload, "candidate_ids", allow_empty=True),
        traversals=_traversal_tuple(payload.get("traversals")),
        edges=_edge_tuple(payload.get("edges")),
    )


def _traversal_tuple(payload: object) -> tuple[CitationTraversalRecord, ...]:
    if not isinstance(payload, list):
        raise ValueError("Citation snowball traversals must be a JSON array.")
    records: list[CitationTraversalRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Citation snowball traversal must be a JSON object.")
        records.append(
            CitationTraversalRecord(
                seed_identifier=_required_string(item, "seed_identifier"),
                direction=_required_string(item, "direction"),
                outcome=_required_string(item, "outcome"),
                attempted=_required_bool(item, "attempted"),
                result_count=_nonnegative_int(item, "result_count"),
                reason=_optional_string(item, "reason"),
            )
        )
    return tuple(records)


def _edge_tuple(payload: object) -> tuple[CitationEdgeRecord, ...]:
    if not isinstance(payload, list):
        raise ValueError("Citation snowball edges must be a JSON array.")
    records: list[CitationEdgeRecord] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Citation snowball edge must be a JSON object.")
        records.append(
            CitationEdgeRecord(
                provider=_required_string(item, "provider"),
                seed_identifier=_required_string(item, "seed_identifier"),
                related_provider_id=_required_string(item, "related_provider_id"),
                direction=_required_string(item, "direction"),
                retrieved_at=_required_string(item, "retrieved_at"),
            )
        )
    return tuple(records)


def _string_tuple(
    payload: dict[str, Any],
    field: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"Citation snowball field {field} must be a JSON array of text.")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"Citation snowball field {field} contains invalid text.")
    return tuple(value)


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Citation snowball field {field} must be non-empty text.")
    return value


def _optional_string(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Citation snowball field {field} must be null or non-empty text.")
    return value


def _required_bool(payload: dict[str, Any], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"Citation snowball field {field} must be boolean.")
    return value


def _positive_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"Citation snowball field {field} must be a positive integer.")
    return value


def _nonnegative_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Citation snowball field {field} must be non-negative.")
    return value
