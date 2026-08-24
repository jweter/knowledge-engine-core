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
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from knowledge_engine.duplicate_queries import DuplicateQueryRepository
from knowledge_engine.federated_search_ledger import (
    CandidateObservationRecord,
    CandidateRecord,
    FederatedSearchLedger,
    SearchRunRecord,
)
from knowledge_engine.license_rules import evaluate_license
from knowledge_engine.models import Paper

ACQUISITION_SCHEMA_VERSION = 1


class AcquisitionDisposition(StrEnum):
    """Stable pre-acquisition disposition for one selected candidate."""

    ALREADY_INDEXED = "already_indexed"
    ELIGIBLE_FULL_TEXT = "eligible_full_text"
    METADATA_ONLY = "metadata_only"
    SKIPPED_BUDGET = "skipped_budget"
    NOT_FOUND_IN_RUN = "not_found_in_run"


class AcquisitionRoute(StrEnum):
    """Supported, independently validated full-text acquisition mechanisms."""

    PMC_OA = "pmc_oa"
    EUROPE_PMC_OA = "europe_pmc_oa"
    CORE = "core"
    UNPAYWALL = "unpaywall"


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
    acquisition_route: str | None
    full_text_url: str | None
    xml_url: str | None
    license: str | None
    open_access: bool | None
    existing_paper_id: int | None
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
    already_indexed_count: int
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
    session: Session | None = None,
) -> GeneralQuestionAcquisitionPlan:
    """Resolve selected IDs strictly against one persisted federated-search run.

    ``session``, when provided, is used to detect candidates that already
    exist in Core's persisted corpus (by normalized DOI, then PMID, then
    arXiv ID -- whichever identity is both known for the candidate and
    persisted on an existing ``Paper``) so they are reported as
    ``already_indexed`` instead of being queued for reacquisition. This
    check happens before -- and is not bound by -- the acquisition budget:
    reusing an already-indexed source costs nothing to acquire, so it must
    never compete with genuinely new candidates for a budget slot. Omitting
    ``session`` preserves this function's prior snapshot-only behavior
    unchanged.
    """

    record = FederatedSearchLedger(ledger_root).load(request.search_run_id)
    _validate_request_against_run(request, record)
    by_id = {candidate.canonical_id: candidate for candidate in record.candidates}

    items: list[AcquisitionPlanItem] = []
    full_text_selected = 0
    resolved = 0
    already_indexed = 0
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
                    acquisition_route=None,
                    full_text_url=None,
                    xml_url=None,
                    license=None,
                    open_access=None,
                    existing_paper_id=None,
                    reason="candidate_not_present_in_persisted_search_snapshot",
                )
            )
            continue

        resolved += 1
        identity = _identity(candidate)
        existing_match = _find_existing_paper(session, identity) if session is not None else None
        if existing_match is not None:
            existing_paper, match_reason = existing_match
            already_indexed += 1
            items.append(
                AcquisitionPlanItem(
                    candidate_id=candidate.canonical_id,
                    title=candidate.title,
                    disposition=AcquisitionDisposition.ALREADY_INDEXED.value,
                    identity=identity,
                    selected_observation_provider=None,
                    full_text_url=None,
                    xml_url=None,
                    license=None,
                    open_access=None,
                    existing_paper_id=existing_paper.id,
                    reason=match_reason,
                )
            )
            continue

        if ordinal >= request.max_candidates:
            skipped += 1
            items.append(_budget_item(candidate, identity))
            continue

        routed_observation = _best_acquisition_observation(candidate)
        route, observation = (
            routed_observation if routed_observation is not None else (None, None)
        )
        full_text_allowed = (
            observation is not None
            and route is not None
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
                    route=route,
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
                    route=route,
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
                    route=None,
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
                    route=None,
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
        already_indexed_count=already_indexed,
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
) -> tuple[AcquisitionRoute, CandidateObservationRecord] | None:
    """Choose only observations backed by a supported acquisition mechanism."""

    routed = tuple(
        (route, observation)
        for observation in candidate.observations
        if (route := _acquisition_route(observation)) is not None
    )
    if not routed:
        return None
    route_priority = {route: ordinal for ordinal, route in enumerate(AcquisitionRoute)}
    return min(
        routed,
        key=lambda item: (
            route_priority[item[0]],
            0 if _observation_is_license_or_oa_eligible(item[1]) else 1,
            item[1].provider,
            item[1].provider_id,
        ),
    )


def _acquisition_route(observation: CandidateObservationRecord) -> AcquisitionRoute | None:
    """Map snapshot evidence to an existing, validation-gated acquisition path."""

    url = observation.full_text_url or observation.xml_url
    if not url:
        return None
    hostname = (urlsplit(url).hostname or "").lower()
    provider = observation.provider.lower().replace("-", "_")

    # A PMCID is routed back through the dedicated PMC OA service, which
    # independently verifies approval evidence and its official download host.
    if observation.pmcid and hostname in {
        "pmc.ncbi.nlm.nih.gov",
        "pmc-oa-opendata.s3.amazonaws.com",
    }:
        return AcquisitionRoute.PMC_OA
    if provider in {"europepmc", "europe_pmc"} and hostname == "europepmc.org":
        return AcquisitionRoute.EUROPE_PMC_OA
    if provider == "core" and hostname == "core.ac.uk":
        return AcquisitionRoute.CORE
    if provider == "unpaywall":
        return AcquisitionRoute.UNPAYWALL
    return None


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


def _budget_item(candidate: CandidateRecord, identity: AcquisitionIdentity) -> AcquisitionPlanItem:
    return AcquisitionPlanItem(
        candidate_id=candidate.canonical_id,
        title=candidate.title,
        disposition=AcquisitionDisposition.SKIPPED_BUDGET.value,
        identity=identity,
        selected_observation_provider=None,
        acquisition_route=None,
        full_text_url=None,
        xml_url=None,
        license=None,
        open_access=None,
        existing_paper_id=None,
        reason="candidate_budget_exhausted",
    )


def _item_from_observation(
    candidate: CandidateRecord,
    observation: CandidateObservationRecord | None,
    identity: AcquisitionIdentity,
    *,
    route: AcquisitionRoute | None,
    disposition: AcquisitionDisposition,
    reason: str | None,
) -> AcquisitionPlanItem:
    return AcquisitionPlanItem(
        candidate_id=candidate.canonical_id,
        title=candidate.title,
        disposition=disposition.value,
        identity=identity,
        selected_observation_provider=observation.provider if observation else None,
        acquisition_route=route.value if route is not None else None,
        full_text_url=observation.full_text_url if observation else None,
        xml_url=observation.xml_url if observation else None,
        license=observation.license if observation else None,
        open_access=observation.open_access if observation else None,
        existing_paper_id=None,
        reason=reason,
    )


def _find_existing_paper(
    session: Session, identity: AcquisitionIdentity
) -> tuple[Paper, str] | None:
    """Resolve stable identity against Core's already-persisted corpus.

    Checked in order -- DOI, then PMID, then arXiv ID -- against whichever
    of those columns ``Paper`` persists and indexes today; the first match
    wins and its reason string names which identity matched. PMCID-based
    reuse detection remains future work once an equivalent persisted
    column exists (see CORE-GQR-2 in docs/general_question_research_loop_v1.md).
    """
    repository = DuplicateQueryRepository(session)
    if identity.doi:
        paper = repository.paper_by_normalized_doi(identity.doi)
        if paper is not None:
            return paper, "candidate_doi_matches_existing_indexed_paper"
    if identity.pmid:
        paper = repository.paper_by_pmid(identity.pmid)
        if paper is not None:
            return paper, "candidate_pmid_matches_existing_indexed_paper"
    if identity.arxiv_id:
        paper = repository.paper_by_arxiv_id(identity.arxiv_id)
        if paper is not None:
            return paper, "candidate_arxiv_id_matches_existing_indexed_paper"
    return None


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
    "AcquisitionRoute",
    "AcquisitionPlanItem",
    "GeneralQuestionAcquisitionPlan",
    "GeneralQuestionAcquisitionRequest",
    "build_acquisition_plan",
]
