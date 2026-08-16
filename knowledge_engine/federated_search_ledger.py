"""Durable local ledger for reproducible federated discovery coverage.

FRD-6 starts by preserving the facts needed to answer what was searched and
whether coverage degraded. The ledger intentionally stores query/run/provider
facts only; provider credentials, transport headers, and provider-native raw
responses are outside this boundary.
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

from knowledge_engine.federated_discovery import (
    FederatedSearchResult,
    ProviderOutcome,
    SearchCompleteness,
)

LEDGER_SCHEMA_VERSION = 1
_SUCCESSFUL_OUTCOMES = {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY}


@dataclass(frozen=True)
class ProviderCoverageRecord:
    """Persisted coverage facts for one requested provider."""

    provider: str
    outcome: str
    attempted: bool
    result_count: int
    latency_ms: int | None
    reason: str | None


@dataclass(frozen=True)
class SearchRunRecord:
    """Immutable local record of one federated discovery run."""

    schema_version: int
    search_run_id: str
    created_at: str
    query_text: str
    year_from: int | None
    year_to: int | None
    limit_per_provider: int
    completeness: str
    candidate_count: int
    providers: tuple[ProviderCoverageRecord, ...]
    initiated_by: str | None = None
    project_id: str | None = None
    research_question_id: str | None = None

    @property
    def providers_requested(self) -> tuple[str, ...]:
        return tuple(provider.provider for provider in self.providers)

    @property
    def providers_attempted(self) -> tuple[str, ...]:
        return tuple(provider.provider for provider in self.providers if provider.attempted)

    @property
    def providers_completed(self) -> tuple[str, ...]:
        return tuple(
            provider.provider
            for provider in self.providers
            if provider.attempted and provider.outcome in {outcome.value for outcome in _SUCCESSFUL_OUTCOMES}
        )

    @property
    def providers_failed(self) -> tuple[str, ...]:
        return tuple(
            provider.provider
            for provider in self.providers
            if provider.attempted and provider.outcome not in {outcome.value for outcome in _SUCCESSFUL_OUTCOMES}
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["providers"] = [asdict(provider) for provider in self.providers]
        return payload


@dataclass(frozen=True)
class SearchCoverageReport:
    """Deterministic coverage view suitable for later AI/Web rendering."""

    search_run_id: str
    completeness: str
    candidate_count: int
    providers_requested: tuple[str, ...]
    providers_attempted: tuple[str, ...]
    providers_completed: tuple[str, ...]
    providers_failed: tuple[str, ...]


class FederatedSearchLedger:
    """Persist immutable federated search-run facts as local JSON records."""

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

    def record(
        self,
        result: FederatedSearchResult,
        *,
        initiated_by: str | None = None,
        project_id: str | None = None,
        research_question_id: str | None = None,
    ) -> SearchRunRecord:
        """Persist one run without retaining secrets or provider transport state."""

        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("Federated search ledger clock must return a timezone-aware datetime.")

        search_run_id = str(self._id_factory())
        providers = tuple(
            ProviderCoverageRecord(
                provider=status.provider.strip().lower().replace(" ", "_"),
                outcome=status.outcome.value,
                attempted=status.attempted,
                result_count=status.result_count,
                latency_ms=status.latency_ms,
                reason=status.reason,
            )
            for status in result.provider_statuses
        )
        record = SearchRunRecord(
            schema_version=LEDGER_SCHEMA_VERSION,
            search_run_id=search_run_id,
            created_at=created_at.astimezone(UTC).isoformat(),
            query_text=result.query.normalized_text,
            year_from=result.query.year_from,
            year_to=result.query.year_to,
            limit_per_provider=result.query.limit_per_provider,
            completeness=result.completeness.value,
            candidate_count=len(result.candidates),
            providers=providers,
            initiated_by=_optional_text(initiated_by),
            project_id=_optional_text(project_id),
            research_question_id=_optional_text(research_question_id),
        )
        self._write_once(record)
        return record

    def load(self, search_run_id: str) -> SearchRunRecord:
        """Load one previously persisted run by UUID."""

        normalized_id = str(UUID(search_run_id))
        path = self._record_path(normalized_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Federated search-run record is malformed.") from exc
        return _record_from_payload(payload, expected_run_id=normalized_id)

    def coverage_report(self, search_run_id: str) -> SearchCoverageReport:
        """Return deterministic coverage facts without inference or LLM involvement."""

        record = self.load(search_run_id)
        return SearchCoverageReport(
            search_run_id=record.search_run_id,
            completeness=record.completeness,
            candidate_count=record.candidate_count,
            providers_requested=record.providers_requested,
            providers_attempted=record.providers_attempted,
            providers_completed=record.providers_completed,
            providers_failed=record.providers_failed,
        )

    def _write_once(self, record: SearchRunRecord) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._record_path(record.search_run_id)
        if target.exists():
            raise FileExistsError(f"Federated search-run record already exists: {record.search_run_id}")

        temporary = target.with_suffix(".json.tmp")
        payload = json.dumps(record.to_dict(), indent=2, sort_keys=True) + "\n"
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            if target.exists():
                raise FileExistsError(
                    f"Federated search-run record already exists: {record.search_run_id}"
                )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _record_path(self, search_run_id: str) -> Path:
        return self._root / f"{search_run_id}.json"


def _record_from_payload(payload: object, *, expected_run_id: str) -> SearchRunRecord:
    if not isinstance(payload, dict):
        raise ValueError("Federated search-run record must be a JSON object.")
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise ValueError("Unsupported federated search-run ledger schema version.")
    if payload.get("search_run_id") != expected_run_id:
        raise ValueError("Federated search-run record ID does not match its filename.")

    providers_payload = payload.get("providers")
    if not isinstance(providers_payload, list):
        raise ValueError("Federated search-run providers must be a JSON array.")
    providers = tuple(_provider_from_payload(item) for item in providers_payload)

    completeness = payload.get("completeness")
    if completeness not in {item.value for item in SearchCompleteness}:
        raise ValueError("Federated search-run completeness is invalid.")

    return SearchRunRecord(
        schema_version=LEDGER_SCHEMA_VERSION,
        search_run_id=expected_run_id,
        created_at=_required_string(payload, "created_at"),
        query_text=_required_string(payload, "query_text"),
        year_from=_optional_int(payload, "year_from"),
        year_to=_optional_int(payload, "year_to"),
        limit_per_provider=_required_nonnegative_int(payload, "limit_per_provider", minimum=1),
        completeness=completeness,
        candidate_count=_required_nonnegative_int(payload, "candidate_count"),
        providers=providers,
        initiated_by=_payload_optional_string(payload, "initiated_by"),
        project_id=_payload_optional_string(payload, "project_id"),
        research_question_id=_payload_optional_string(payload, "research_question_id"),
    )


def _provider_from_payload(payload: object) -> ProviderCoverageRecord:
    if not isinstance(payload, dict):
        raise ValueError("Federated provider coverage must be a JSON object.")
    outcome = payload.get("outcome")
    if outcome not in {item.value for item in ProviderOutcome}:
        raise ValueError("Federated provider coverage outcome is invalid.")
    attempted = payload.get("attempted")
    if not isinstance(attempted, bool):
        raise ValueError("Federated provider coverage attempted must be boolean.")

    return ProviderCoverageRecord(
        provider=_required_string(payload, "provider"),
        outcome=outcome,
        attempted=attempted,
        result_count=_required_nonnegative_int(payload, "result_count"),
        latency_ms=_optional_nonnegative_int(payload, "latency_ms"),
        reason=_payload_optional_string(payload, "reason"),
    )


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Federated search-run field {field} must be a non-empty string.")
    return value


def _payload_optional_string(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Federated search-run field {field} must be null or non-empty text.")
    return value


def _required_nonnegative_int(
    payload: dict[str, Any], field: str, *, minimum: int = 0
) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Federated search-run field {field} is invalid.")
    return value


def _optional_nonnegative_int(payload: dict[str, Any], field: str) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Federated search-run field {field} is invalid.")
    return value


def _optional_int(payload: dict[str, Any], field: str) -> int | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Federated search-run field {field} is invalid.")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Federated search-run context values must not be blank.")
    return normalized
