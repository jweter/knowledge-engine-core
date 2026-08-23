"""Bounded, auditable acquisition planning for General Question Research Loop v1.

This module is deliberately deterministic. It resolves candidate selections only
against a persisted federated-search snapshot, applies explicit budgets, and
produces stable acquisition dispositions. It does not treat discovery candidates
as evidence and it does not download full text itself; provider-specific
acquisition services consume the eligible plan in the next pipeline stage.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from knowledge_engine.federated_search_ledger import (
    CandidateObservationRecord,
    CandidateRecord,
    FederatedSearchLedger,
    SearchRunRecord,
)
from knowledge_engine.license_rules import evaluate_license

ACQUISITION_SCHEMA_VERSION = 1


class AcquisitionDisposition(StrEnum):
    """Stable pre-acquisition disposition for one selected candidate."""

    ELIGIBLE_FULL_TEXT = "eligible_full_text"
    METADATA_ONLY = "metadata_only"
    SKIPPED_BUDGET = "skipped_budget"
    NOT_FOUND_IN_RUN = "not_found_in_run"


@dataclass(frozen=True)
class GeneralQuestionAcquisitionRequest:
    """Bounded request to resolve discovery leads into an acquisition queue."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    candidate_ids: tuple[str, ...]
    max_candidates: int = 10
    max_full_text_acquisitions: int = 5
    max_elapsed_seconds: int = 120
    allow_metadata_only: bool = True

    def __post_init__(self) -> None:
        if self.schema_version != ACQUISITION_SCHEMA_VERSION:
            raise ValueError("Unsupported general-question acquisition schema version.")
        if not self.search_run_id.strip():
            raise ValueError("search_run_id must be non-blank.")
        if not self.research_question_id.strip():
            raise ValueError("research_question_id must be non-blank.")
        if not self.candidate_ids:
            raise ValueError("candidate_ids must contain at least one candidate.")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError("candidate_ids must not contain duplicates.")
        if not 1 <= self.max_candidates <= 100:
            raise ValueError("max_candidates must be between 1 and 100.")
        if not 0 <= self.max_full_text_acquisitions <= self.max_candidates:
            raise ValueError("max_full_text_acquisitions must be between 0 and max_candidates.")
        if not 1 <= self.max_elapsed_seconds <= 3600:
            raise ValueError("max_elapsed_seconds must be between 1 and 3600.")

    @classmethod
    def from_json(cls, text: str) -> GeneralQuestionAcquisitionRequest:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Acquisition request must be a JSON object.")
        raw_ids = payload.get("candidate_ids")
        if not isinstance(raw_ids, list) or not all(isinstance(item, str) for item in raw_ids):
            raise ValueError("candidate_ids must be a JSON array of strings.")
        return cls(
            schema_version=_required_int(payload, "schema_version"),
            search_run_id=_required_str(payload, "search_run_id"),
            research_question_id=_required_str(payload, "research_question_id"),
            candidate_ids=tuple(item.strip() for item in raw_ids),
            max_candidates=_optional_int(payload, "max_candidates", 10),
            max_full_text_acquisitions=_optional_int(payload, "max_full_text_acquisitions", 5),
            max_elapsed_seconds=_optional_int(payload, "max_elapsed_seconds", 120),
            allow_metadata_only=_optional_bool(payload, "allow_metadata_only", True),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate_ids"] = list(self.candidate_ids)
        return payload


@dataclass(frozen=True)
class AcquisitionIdentity:
    """Provider-neutral identity facts preserved from the search snapshot."""

    canonical_id: str
    doi: str | None
    pmid: str | None
    pmcid: str | None
    arxiv_id: str | None
    openalex_id: str | None
    semantic_scholar_id: str | None


@dataclass(frozen=True)
class AcquisitionPlanItem:
    """One deterministic candidate-selection result."""

    candidate_id: str
    title: str | None
    disposition: str
    identity: AcquisitionIdentity | None
    selected_observation_provider: str | None
    full_text_url: str | None
    xml_url: str | None
    license: str | None
    open_access: bool | None
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GeneralQuestionAcquisitionPlan:
    """Stable acquisition plan with explicit budget reconciliation."""

    schema_version: int
    search_run_id: str
    research_question_id: str
    query_text: str
    requested_candidate_count: int
    resolved_candidate_count: int
    full_text_selected_count: int
    metadata_only_count: int
    skipped_budget_count: int
    missing_candidate_count: int
    provider_failures: tuple[str, ...]
    items: tuple[AcquisitionPlanItem, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["provider_failures"] = list(self.provider_failures)
        payload["items"] = [item.to_dict() for item in self.items]
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def build_acquisition_plan(
    request: GeneralQuestionAcquisitionRequest,
    *,
    ledger_root: Path,
) -> GeneralQuestionAcquisitionPlan:
    """Resolve selected IDs strictly against one persisted federated-search run."""

    record = FederatedSearchLedger(ledger_root).load(request.search_run_id)
    _validate_request_against_run(request, record)
    by_id = {candidate.canonical_id: candidate for candidate in record.candidates}

    items: list[AcquisitionPlanItem] = []
    full_text_selected = 0
    resolved = 0
    metadata_only = 0
    skipped = 0
    missing = 0

    for ordinal, candidate_id in enumerate(request.candidate_ids):
        candidate = by_id.get(candidate_id)
        if candidate is None:
            missing += 1
            items.append(
                AcquisitionPlanItem(
                    candidate_id=candidate_id,
                    title=None,
                    disposition=AcquisitionDisposition.NOT_FOUND_IN_RUN.value,
                    identity=None,
                    selected_observation_provider=None,
                    full_text_url=None,
                    xml_url=None,
                    license=None,
                    open_access=None,
                    reason="candidate_not_present_in_persisted_search_snapshot",
                )
            )
            continue

        resolved += 1
        if ordinal >= request.max_candidates:
            skipped += 1
            items.append(_budget_item(candidate))
            continue

        observation = _best_acquisition_observation(candidate)
        identity = _identity(candidate)
        has_full_text = observation is not None and bool(
            observation.full_text_url or observation.xml_url
        )
        full_text_allowed = (
            has_full_text
            and observation is not None
            and not _candidate_has_retraction_signal(candidate)
            and _observation_is_license_or_oa_eligible(observation)
        )

        if full_text_allowed and full_text_selected < request.max_full_text_acquisitions:
            full_text_selected += 1
            items.append(
                _item_from_observation(
                    candidate,
                    observation,
                    identity,
                    disposition=AcquisitionDisposition.ELIGIBLE_FULL_TEXT,
                    reason=None,
                )
            )
            continue

        if full_text_allowed:
            skipped += 1
            items.append(
                _item_from_observation(
                    candidate,
                    observation,
                    identity,
                    disposition=AcquisitionDisposition.SKIPPED_BUDGET,
                    reason="full_text_acquisition_budget_exhausted",
                )
            )
            continue

        if request.allow_metadata_only:
            metadata_only += 1
            items.append(
                _item_from_observation(
                    candidate,
                    observation,
                    identity,
                    disposition=AcquisitionDisposition.METADATA_ONLY,
                    reason="no_eligible_open_full_text_location",
                )
            )
        else:
            skipped += 1
            items.append(
                _item_from_observation(
                    candidate,
                    observation,
                    identity,
                    disposition=AcquisitionDisposition.SKIPPED_BUDGET,
                    reason="metadata_only_disabled",
                )
            )

    return GeneralQuestionAcquisitionPlan(
        schema_version=ACQUISITION_SCHEMA_VERSION,
        search_run_id=record.search_run_id,
        research_question_id=request.research_question_id,
        query_text=record.query_text,
        requested_candidate_count=len(request.candidate_ids),
        resolved_candidate_count=resolved,
        full_text_selected_count=full_text_selected,
        metadata_only_count=metadata_only,
        skipped_budget_count=skipped,
        missing_candidate_count=missing,
        provider_failures=record.providers_failed,
        items=tuple(items),
    )


def _validate_request_against_run(
    request: GeneralQuestionAcquisitionRequest, record: SearchRunRecord
) -> None:
    if record.research_question_id != request.research_question_id:
        # A run persisted with no bound research_question_id (None) must not
        # be silently annexed to whatever question the request names -- that
        # would let an acquisition plan attach an arbitrary question ID to an
        # unbound run, breaking evidence traceability back to its origin.
        raise ValueError(
            "Acquisition request research_question_id does not match the persisted search run."
        )
    if not record.candidates and record.candidate_count:
        raise ValueError(
            "Persisted search run predates candidate snapshots and cannot be acquired safely."
        )


def _best_acquisition_observation(
    candidate: CandidateRecord,
) -> CandidateObservationRecord | None:
    if not candidate.observations:
        return None
    return min(
        candidate.observations,
        key=lambda item: (
            0
            if _observation_is_license_or_oa_eligible(item) and (item.full_text_url or item.xml_url)
            else 1,
            0 if item.pmcid and (item.full_text_url or item.xml_url) else 1,
            0 if item.full_text_url or item.xml_url else 1,
            item.provider,
            item.provider_id,
        ),
    )


def _candidate_has_retraction_signal(candidate: CandidateRecord) -> bool:
    # Retraction/withdrawal is a fact about the underlying work, not about
    # which provider happened to be selected as the acquisition source, so
    # every provider's observation of this candidate must be checked -- not
    # just the one `_best_acquisition_observation` picked for its URL/license.
    return any(
        observation.retracted is True or observation.withdrawn is True
        for observation in candidate.observations
    )


def _observation_is_license_or_oa_eligible(observation: CandidateObservationRecord) -> bool:
    # Positive provider OA evidence or a reusable (e.g. CC BY/CC0) license is
    # required. Merely receiving a URL, or a non-blank but restrictive license
    # string such as "CC BY-NC-ND", is not sufficient authorization to acquire
    # full text -- reuse the same license policy the rest of the corpus does.
    if observation.open_access is True:
        return True
    return evaluate_license(observation.license) == "passed"


def _identity(candidate: CandidateRecord) -> AcquisitionIdentity:
    observations = candidate.observations
    return AcquisitionIdentity(
        canonical_id=candidate.canonical_id,
        doi=candidate.doi or _first_text(observations, "doi"),
        pmid=_first_text(observations, "pmid"),
        pmcid=_first_text(observations, "pmcid"),
        arxiv_id=_first_text(observations, "arxiv_id"),
        openalex_id=_first_text(observations, "openalex_id"),
        semantic_scholar_id=_first_text(observations, "semantic_scholar_id"),
    )


def _first_text(observations: tuple[CandidateObservationRecord, ...], field: str) -> str | None:
    for observation in observations:
        value = getattr(observation, field)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _budget_item(candidate: CandidateRecord) -> AcquisitionPlanItem:
    return AcquisitionPlanItem(
        candidate_id=candidate.canonical_id,
        title=candidate.title,
        disposition=AcquisitionDisposition.SKIPPED_BUDGET.value,
        identity=_identity(candidate),
        selected_observation_provider=None,
        full_text_url=None,
        xml_url=None,
        license=None,
        open_access=None,
        reason="candidate_budget_exhausted",
    )


def _item_from_observation(
    candidate: CandidateRecord,
    observation: CandidateObservationRecord | None,
    identity: AcquisitionIdentity,
    *,
    disposition: AcquisitionDisposition,
    reason: str | None,
) -> AcquisitionPlanItem:
    return AcquisitionPlanItem(
        candidate_id=candidate.canonical_id,
        title=candidate.title,
        disposition=disposition.value,
        identity=identity,
        selected_observation_provider=observation.provider if observation else None,
        full_text_url=observation.full_text_url if observation else None,
        xml_url=observation.xml_url if observation else None,
        license=observation.license if observation else None,
        open_access=observation.open_access if observation else None,
        reason=reason,
    )


def _required_str(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-blank string.")
    return value.strip()


def _required_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer.")
    return value


def _optional_int(payload: dict[str, object], key: str, default: int) -> int:
    if key not in payload:
        return default
    return _required_int(payload, key)


def _optional_bool(payload: dict[str, object], key: str, default: bool) -> bool:
    if key not in payload:
        return default
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean.")
    return value


__all__ = [
    "ACQUISITION_SCHEMA_VERSION",
    "AcquisitionDisposition",
    "AcquisitionIdentity",
    "AcquisitionPlanItem",
    "GeneralQuestionAcquisitionPlan",
    "GeneralQuestionAcquisitionRequest",
    "build_acquisition_plan",
]
