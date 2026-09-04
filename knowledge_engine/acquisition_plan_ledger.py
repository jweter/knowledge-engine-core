"""Durable local ledger for General Question acquisition-plan funnel counts.

`general_question_acquisition.build_acquisition_plan` resolves one bounded
acquisition request into a `GeneralQuestionAcquisitionPlan` -- issue #433's
"candidate funnel" (discovered -> deduplicated -> already indexed ->
acquisition eligible -> acquired full text -> metadata only/unavailable) --
but previously only returned it from one CLI invocation with nothing kept
for later inspection, unlike the discovery-stage funnel counts
`federated_search_ledger.py` already persists durably alongside a search
run. This module closes that gap the same way `citation_snowball_ledger.py`
persists citation-snowball runs: one write-once local JSON record per
planning call, keyed by its own UUID and looked up by the `search_run_id`
it was resolved against.

Only deterministic funnel counts, timing, and provenance IDs are persisted
-- never per-item candidate detail, license/OA state, or acquisition
routes, which remain the caller's own `GeneralQuestionAcquisitionPlan`
output (`--output`), not this durable record's concern.
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

from knowledge_engine.general_question_acquisition import GeneralQuestionAcquisitionPlan

LEDGER_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AcquisitionPlanRunRecord:
    """Immutable durable record of one acquisition-plan funnel outcome."""

    schema_version: int
    acquisition_plan_id: str
    created_at: str
    search_run_id: str
    research_question_id: str
    query_text: str
    requested_candidate_count: int
    resolved_candidate_count: int
    already_indexed_count: int
    full_text_selected_count: int
    metadata_only_count: int
    skipped_budget_count: int
    missing_candidate_count: int
    provider_failures: tuple[str, ...]
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provider_failures"] = list(self.provider_failures)
        return payload


class AcquisitionPlanLedger:
    """Persist General Question acquisition-plan funnel counts as write-once local JSON records."""

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

    def record(self, plan: GeneralQuestionAcquisitionPlan) -> AcquisitionPlanRunRecord:
        """Persist one already-computed plan's funnel counts and return its durable record."""

        created_at = self._clock()
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            raise ValueError("Acquisition plan ledger clock must return a timezone-aware datetime.")

        record = AcquisitionPlanRunRecord(
            schema_version=LEDGER_SCHEMA_VERSION,
            acquisition_plan_id=str(self._id_factory()),
            created_at=created_at.astimezone(UTC).isoformat(),
            search_run_id=plan.search_run_id,
            research_question_id=plan.research_question_id,
            query_text=plan.query_text,
            requested_candidate_count=plan.requested_candidate_count,
            resolved_candidate_count=plan.resolved_candidate_count,
            already_indexed_count=plan.already_indexed_count,
            full_text_selected_count=plan.full_text_selected_count,
            metadata_only_count=plan.metadata_only_count,
            skipped_budget_count=plan.skipped_budget_count,
            missing_candidate_count=plan.missing_candidate_count,
            provider_failures=plan.provider_failures,
            duration_ms=plan.duration_ms,
        )
        self._write_once(record)
        return record

    def load(self, acquisition_plan_id: str) -> AcquisitionPlanRunRecord:
        """Load one persisted plan record by UUID."""

        normalized_id = str(UUID(acquisition_plan_id))
        path = self._record_path(normalized_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Acquisition plan record is malformed.") from exc
        return _record_from_payload(payload, expected_id=normalized_id)

    def list_by_search_run_id(self, search_run_id: str) -> tuple[AcquisitionPlanRunRecord, ...]:
        """List every persisted plan resolved against `search_run_id`, newest first.

        Scans every `*.json` record under this ledger's root (each written
        exactly once by `record`); a root that does not exist yet returns
        an empty tuple rather than raising, matching "no acquisition plans
        recorded for this run yet."
        """

        normalized = search_run_id.strip()
        if not normalized:
            raise ValueError("Acquisition plan history requires a non-blank search_run_id.")
        if not self._root.exists():
            return ()

        matches = [
            record
            for record in (self.load(path.stem) for path in sorted(self._root.glob("*.json")))
            if record.search_run_id == normalized
        ]
        matches.sort(
            key=lambda record: (record.created_at, record.acquisition_plan_id), reverse=True
        )
        return tuple(matches)

    def _write_once(self, record: AcquisitionPlanRunRecord) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._record_path(record.acquisition_plan_id)
        if target.exists():
            raise FileExistsError(
                f"Acquisition plan record already exists: {record.acquisition_plan_id}"
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
                    f"Acquisition plan record already exists: {record.acquisition_plan_id}"
                )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _record_path(self, acquisition_plan_id: str) -> Path:
        return self._root / f"{acquisition_plan_id}.json"


def _record_from_payload(payload: object, *, expected_id: str) -> AcquisitionPlanRunRecord:
    if not isinstance(payload, dict):
        raise ValueError("Acquisition plan record must be a JSON object.")
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise ValueError("Unsupported acquisition plan ledger schema version.")
    if payload.get("acquisition_plan_id") != expected_id:
        raise ValueError("Acquisition plan ID does not match its filename.")

    return AcquisitionPlanRunRecord(
        schema_version=LEDGER_SCHEMA_VERSION,
        acquisition_plan_id=expected_id,
        created_at=_required_string(payload, "created_at"),
        search_run_id=_required_string(payload, "search_run_id"),
        research_question_id=_required_string(payload, "research_question_id"),
        query_text=_required_string(payload, "query_text"),
        requested_candidate_count=_nonnegative_int(payload, "requested_candidate_count"),
        resolved_candidate_count=_nonnegative_int(payload, "resolved_candidate_count"),
        already_indexed_count=_nonnegative_int(payload, "already_indexed_count"),
        full_text_selected_count=_nonnegative_int(payload, "full_text_selected_count"),
        metadata_only_count=_nonnegative_int(payload, "metadata_only_count"),
        skipped_budget_count=_nonnegative_int(payload, "skipped_budget_count"),
        missing_candidate_count=_nonnegative_int(payload, "missing_candidate_count"),
        provider_failures=_string_tuple(payload, "provider_failures"),
        duration_ms=_nonnegative_int(payload, "duration_ms"),
    )


def _string_tuple(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    value = payload.get(field)
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"Acquisition plan field {field} must be a JSON array of text.")
    return tuple(value)


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Acquisition plan field {field} must be non-empty text.")
    return value


def _nonnegative_int(payload: dict[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Acquisition plan field {field} must be non-negative.")
    return value


__all__ = [
    "LEDGER_SCHEMA_VERSION",
    "AcquisitionPlanLedger",
    "AcquisitionPlanRunRecord",
]
