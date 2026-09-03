"""Durable local ledger for reproducible federated discovery coverage.

FRD-6 starts by preserving the facts needed to answer what was searched and
whether coverage degraded. The ledger stores query/run/provider facts and
(as of the FRD-6 candidate-snapshot follow-up) each run's own deduplicated
candidate list with per-provider observations -- the same public shape
`federated-discover --output` already serializes at request time, now also
durable and re-fetchable after the fact via `SearchRunRecord.candidates`.
Provider credentials, transport headers, and provider-native raw responses
remain outside this boundary.
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
    ProviderObservation,
    ProviderOutcome,
    SearchCompleteness,
)

LEDGER_SCHEMA_VERSION = 1
_SUCCESSFUL_OUTCOMES = {ProviderOutcome.SUCCESS, ProviderOutcome.EMPTY}


@dataclass(frozen=True)
class ProviderCoverageRecord:
    """Persisted coverage facts for one requested provider.

    ``retry_attempt_count``/``rate_limited_observed`` postdate this record's
    original field set (issue #433 item 2's federated provider
    latency/degradation follow-up), added the same additive way `candidates`
    itself postdated `LEDGER_SCHEMA_VERSION` 1's original shape: a run
    persisted before these fields existed simply omits the keys, and the
    loader defaults them to ``0``/``False`` -- the honest "no retry happened"
    state for every adapter that did not yet implement retries when the run
    was recorded -- so no schema-version bump was needed.
    """

    provider: str
    outcome: str
    attempted: bool
    result_count: int
    latency_ms: int | None
    reason: str | None
    retry_attempt_count: int = 0
    rate_limited_observed: bool = False


@dataclass(frozen=True)
class CandidateObservationRecord:
    """One provider's persisted observation of one candidate, for later replay.

    Mirrors `federated_discovery.ProviderObservation` field-for-field: the
    same public shape `federated-discover --output` already serializes at
    request time, now also durable in the ledger. `corrected`/
    `expression_of_concern`/`withdrawn` postdate this record's original
    field set (FRD-5 publication-status follow-up), added the same way
    `candidates` itself postdated `LEDGER_SCHEMA_VERSION` 1's original shape:
    a run persisted before these fields existed simply omits the keys, and
    `_optional_bool` already loads a missing key as `None` -- an honest
    "not recorded" rather than a fabricated `False` -- so no schema-version
    bump or special-cased loader branch was needed.
    """

    provider: str
    provider_id: str
    title: str
    authors: tuple[str, ...] = ()
    publication_year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    landing_url: str | None = None
    full_text_url: str | None = None
    xml_url: str | None = None
    license: str | None = None
    metadata_source: str | None = None
    pmcid_source: str | None = None
    open_access_source: str | None = None
    citation_count: int | None = None
    open_access: bool | None = None
    retracted: bool | None = None
    preprint: bool | None = None
    preprint_version: int | None = None
    related_journal_doi: str | None = None
    related_journal_reference: str | None = None
    retrieved_at: str | None = None
    corrected: bool | None = None
    expression_of_concern: bool | None = None
    withdrawn: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["authors"] = list(self.authors)
        return payload


@dataclass(frozen=True)
class CandidateRecord:
    """One persisted deduplicated candidate, with every provider's observation.

    Mirrors `federated_discovery.FederatedCandidate` field-for-field.
    """

    canonical_id: str
    title: str
    observations: tuple[CandidateObservationRecord, ...]
    doi: str | None = None
    publication_year: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_id": self.canonical_id,
            "title": self.title,
            "observations": [observation.to_dict() for observation in self.observations],
            "doi": self.doi,
            "publication_year": self.publication_year,
        }


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
    candidates: tuple[CandidateRecord, ...] = ()

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
            if provider.attempted
            and provider.outcome in {outcome.value for outcome in _SUCCESSFUL_OUTCOMES}
        )

    @property
    def providers_failed(self) -> tuple[str, ...]:
        return tuple(
            provider.provider
            for provider in self.providers
            if provider.attempted
            and provider.outcome not in {outcome.value for outcome in _SUCCESSFUL_OUTCOMES}
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["providers"] = [asdict(provider) for provider in self.providers]
        payload["candidates"] = [candidate.to_dict() for candidate in self.candidates]
        return payload


@dataclass(frozen=True)
class SearchCoverageReport:
    """Deterministic public coverage/provenance view for later AI/Web rendering.

    ``raw_observation_count`` and ``candidate_count`` together answer issue
    #433's "candidate funnel" bottleneck-instrumentation ask for this run's
    discovery stage: ``raw_observation_count`` is the sum of every attempted
    provider's own ``result_count`` (the total scholarly-work observations
    providers returned, before cross-provider deduplication), and
    ``candidate_count`` is how many distinct canonical candidates survived
    deduplication into ``FederatedCandidate``s. The gap between the two is
    exactly how much a run's raw provider results were narrowed by
    deduplication -- previously only reconstructible by re-loading the full
    ``SearchRunRecord`` and summing ``providers[].result_count`` by hand.

    ``total_retry_attempts``/``providers_rate_limited`` answer issue #433
    item 2's "federated provider latency/degradation" ask the same way:
    ``total_retry_attempts`` is the sum of every attempted provider's own
    ``retry_attempt_count`` (how many bounded retries providers needed across
    this run), and ``providers_rate_limited`` names every attempted provider
    that observed an HTTP 429 rate-limit response at least once, even if a
    later retry ultimately succeeded. Both derive at read time from
    already-persisted per-provider facts, so a run recorded before any
    adapter implemented retries reports them correctly as ``0``/``()``
    without a backfill.
    """

    search_run_id: str
    created_at: str
    query_text: str
    year_from: int | None
    year_to: int | None
    limit_per_provider: int
    completeness: str
    raw_observation_count: int
    total_retry_attempts: int
    candidate_count: int
    providers_requested: tuple[str, ...]
    providers_attempted: tuple[str, ...]
    providers_completed: tuple[str, ...]
    providers_failed: tuple[str, ...]
    providers_rate_limited: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return the public coverage contract as JSON-ready primitives.

        This intentionally serializes only fields already exposed by the
        public coverage view. Internal run context such as ``initiated_by``,
        project IDs, research-question IDs, credentials, transport state, and
        provider-native responses never enter this payload.
        """

        return {
            "search_run_id": self.search_run_id,
            "created_at": self.created_at,
            "query_text": self.query_text,
            "year_from": self.year_from,
            "year_to": self.year_to,
            "limit_per_provider": self.limit_per_provider,
            "completeness": self.completeness,
            "raw_observation_count": self.raw_observation_count,
            "total_retry_attempts": self.total_retry_attempts,
            "candidate_count": self.candidate_count,
            "providers_requested": list(self.providers_requested),
            "providers_attempted": list(self.providers_attempted),
            "providers_completed": list(self.providers_completed),
            "providers_failed": list(self.providers_failed),
            "providers_rate_limited": list(self.providers_rate_limited),
        }


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
                retry_attempt_count=status.retry_attempt_count,
                rate_limited_observed=status.rate_limited_observed,
            )
            for status in result.provider_statuses
        )
        candidates = tuple(
            CandidateRecord(
                canonical_id=candidate.canonical_id,
                title=candidate.title,
                observations=tuple(
                    _observation_record_from_domain(observation)
                    for observation in candidate.observations
                ),
                doi=candidate.doi,
                publication_year=candidate.publication_year,
            )
            for candidate in result.candidates
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
            candidates=candidates,
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

    def list_by_research_question_id(
        self, research_question_id: str
    ) -> tuple[SearchRunRecord, ...]:
        """List every persisted run tagged with `research_question_id`, newest first.

        `load`/`coverage_report` above are point lookups by exact
        `search_run_id`; this is the first ledger read that discovers which
        runs exist for a given tracked question at all -- the capability
        `knowledge-engine-web`'s WEB-FRD-5 freshness-history design depends
        on (`docs/roadmap/federated_research_discovery_adoption.md`'s FRD-6
        section). Scans every `*.json` record under this ledger's root
        (each written exactly once by `record`); a root that does not exist
        yet returns an empty tuple rather than raising, matching "no runs
        recorded for this question yet." Ordered by `created_at` descending
        (newest first); identical timestamps break deterministically by
        `search_run_id` so repeated calls return a stable order.
        """

        normalized = research_question_id.strip()
        if not normalized:
            raise ValueError(
                "Federated search-run history requires a non-blank research_question_id."
            )
        if not self._root.exists():
            return ()

        matches = [
            record
            for record in (self.load(path.stem) for path in sorted(self._root.glob("*.json")))
            if record.research_question_id == normalized
        ]
        matches.sort(key=lambda record: (record.created_at, record.search_run_id), reverse=True)
        return tuple(matches)

    def coverage_report(self, search_run_id: str) -> SearchCoverageReport:
        """Return deterministic coverage and search-method facts without inference."""

        return build_search_coverage_report(self.load(search_run_id))

    def _write_once(self, record: SearchRunRecord) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._record_path(record.search_run_id)
        if target.exists():
            raise FileExistsError(
                f"Federated search-run record already exists: {record.search_run_id}"
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
                    f"Federated search-run record already exists: {record.search_run_id}"
                )
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _record_path(self, search_run_id: str) -> Path:
        return self._root / f"{search_run_id}.json"


def build_search_coverage_report(record: SearchRunRecord) -> SearchCoverageReport:
    """Derive the deterministic public coverage view from an already-loaded record.

    Exposed at module level (not just as `FederatedSearchLedger.coverage_report`'s
    internal step) so a caller that already holds a `SearchRunRecord` -- e.g. to
    also read its `candidates` -- can derive coverage without a second ledger read.
    """

    return SearchCoverageReport(
        search_run_id=record.search_run_id,
        created_at=record.created_at,
        query_text=record.query_text,
        year_from=record.year_from,
        year_to=record.year_to,
        limit_per_provider=record.limit_per_provider,
        completeness=record.completeness,
        raw_observation_count=sum(
            provider.result_count for provider in record.providers if provider.attempted
        ),
        total_retry_attempts=sum(
            provider.retry_attempt_count for provider in record.providers if provider.attempted
        ),
        candidate_count=record.candidate_count,
        providers_requested=record.providers_requested,
        providers_attempted=record.providers_attempted,
        providers_completed=record.providers_completed,
        providers_failed=record.providers_failed,
        providers_rate_limited=tuple(
            provider.provider
            for provider in record.providers
            if provider.attempted and provider.rate_limited_observed
        ),
    )


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

    # `candidates` postdates schema_version 1's original shape: records written
    # before this field existed simply omit the key. Defaulting to an empty
    # tuple keeps every previously persisted run readable rather than
    # rejecting it -- coverage facts (candidate_count included) still load
    # correctly either way; only the candidate-level snapshot is unavailable
    # for runs recorded before this capability existed.
    candidates_payload = payload.get("candidates", [])
    if not isinstance(candidates_payload, list):
        raise ValueError("Federated search-run candidates must be a JSON array.")
    candidates = tuple(_candidate_from_payload(item) for item in candidates_payload)

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
        candidates=candidates,
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

    # `retry_attempt_count`/`rate_limited_observed` postdate this record's
    # original field set (issue #433 item 2). A run persisted before these
    # fields existed simply omits the keys; defaulting to `0`/`False` is the
    # honest "no retry happened" state for an adapter that made exactly one
    # attempt, which was true for every provider before this change.
    retry_attempt_count = payload.get("retry_attempt_count", 0)
    if (
        isinstance(retry_attempt_count, bool)
        or not isinstance(retry_attempt_count, int)
        or retry_attempt_count < 0
    ):
        raise ValueError("Federated search-run field retry_attempt_count is invalid.")
    rate_limited_observed = payload.get("rate_limited_observed", False)
    if not isinstance(rate_limited_observed, bool):
        raise ValueError("Federated search-run field rate_limited_observed is invalid.")

    return ProviderCoverageRecord(
        provider=_required_string(payload, "provider"),
        outcome=outcome,
        attempted=attempted,
        result_count=_required_nonnegative_int(payload, "result_count"),
        latency_ms=_optional_nonnegative_int(payload, "latency_ms"),
        reason=_payload_optional_string(payload, "reason"),
        retry_attempt_count=retry_attempt_count,
        rate_limited_observed=rate_limited_observed,
    )


def _observation_record_from_domain(observation: ProviderObservation) -> CandidateObservationRecord:
    return CandidateObservationRecord(
        provider=observation.provider,
        provider_id=observation.provider_id,
        title=observation.title,
        authors=observation.authors,
        publication_year=observation.publication_year,
        venue=observation.venue,
        abstract=observation.abstract,
        doi=observation.doi,
        pmid=observation.pmid,
        pmcid=observation.pmcid,
        arxiv_id=observation.arxiv_id,
        openalex_id=observation.openalex_id,
        semantic_scholar_id=observation.semantic_scholar_id,
        landing_url=observation.landing_url,
        full_text_url=observation.full_text_url,
        xml_url=observation.xml_url,
        license=observation.license,
        metadata_source=observation.metadata_source,
        pmcid_source=observation.pmcid_source,
        open_access_source=observation.open_access_source,
        citation_count=observation.citation_count,
        open_access=observation.open_access,
        retracted=observation.retracted,
        corrected=observation.corrected,
        expression_of_concern=observation.expression_of_concern,
        withdrawn=observation.withdrawn,
        preprint=observation.preprint,
        preprint_version=observation.preprint_version,
        related_journal_doi=observation.related_journal_doi,
        related_journal_reference=observation.related_journal_reference,
        retrieved_at=observation.retrieved_at,
    )


def _candidate_from_payload(payload: object) -> CandidateRecord:
    if not isinstance(payload, dict):
        raise ValueError("Federated search-run candidate must be a JSON object.")
    observations_payload = payload.get("observations")
    if not isinstance(observations_payload, list) or not observations_payload:
        raise ValueError("Federated search-run candidate observations must be a non-empty array.")
    observations = tuple(_candidate_observation_from_payload(item) for item in observations_payload)
    return CandidateRecord(
        canonical_id=_required_string(payload, "canonical_id"),
        title=_required_string(payload, "title"),
        observations=observations,
        doi=_payload_optional_string(payload, "doi"),
        publication_year=_optional_int(payload, "publication_year"),
    )


def _candidate_observation_from_payload(payload: object) -> CandidateObservationRecord:
    if not isinstance(payload, dict):
        raise ValueError("Federated search-run candidate observation must be a JSON object.")
    authors_payload = payload.get("authors", [])
    if not isinstance(authors_payload, list) or not all(
        isinstance(author, str) for author in authors_payload
    ):
        raise ValueError("Federated search-run candidate authors must be a JSON array of strings.")

    return CandidateObservationRecord(
        provider=_required_string(payload, "provider"),
        provider_id=_required_string(payload, "provider_id"),
        title=_required_string(payload, "title"),
        authors=tuple(authors_payload),
        publication_year=_optional_int(payload, "publication_year"),
        venue=_payload_optional_string(payload, "venue"),
        abstract=_payload_optional_string(payload, "abstract"),
        doi=_payload_optional_string(payload, "doi"),
        pmid=_payload_optional_string(payload, "pmid"),
        pmcid=_payload_optional_string(payload, "pmcid"),
        arxiv_id=_payload_optional_string(payload, "arxiv_id"),
        openalex_id=_payload_optional_string(payload, "openalex_id"),
        semantic_scholar_id=_payload_optional_string(payload, "semantic_scholar_id"),
        landing_url=_payload_optional_string(payload, "landing_url"),
        full_text_url=_payload_optional_string(payload, "full_text_url"),
        xml_url=_payload_optional_string(payload, "xml_url"),
        license=_payload_optional_string(payload, "license"),
        metadata_source=_payload_optional_string(payload, "metadata_source"),
        pmcid_source=_payload_optional_string(payload, "pmcid_source"),
        open_access_source=_payload_optional_string(payload, "open_access_source"),
        citation_count=_optional_nonnegative_int(payload, "citation_count"),
        open_access=_optional_bool(payload, "open_access"),
        retracted=_optional_bool(payload, "retracted"),
        corrected=_optional_bool(payload, "corrected"),
        expression_of_concern=_optional_bool(payload, "expression_of_concern"),
        withdrawn=_optional_bool(payload, "withdrawn"),
        preprint=_optional_bool(payload, "preprint"),
        preprint_version=_optional_int(payload, "preprint_version"),
        related_journal_doi=_payload_optional_string(payload, "related_journal_doi"),
        related_journal_reference=_payload_optional_string(payload, "related_journal_reference"),
        retrieved_at=_payload_optional_string(payload, "retrieved_at"),
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


def _required_nonnegative_int(payload: dict[str, Any], field: str, *, minimum: int = 0) -> int:
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


def _optional_bool(payload: dict[str, Any], field: str) -> bool | None:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValueError(f"Federated search-run field {field} is invalid.")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Federated search-run context values must not be blank.")
    return normalized
