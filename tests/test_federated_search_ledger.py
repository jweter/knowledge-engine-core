from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import (
    LEDGER_SCHEMA_VERSION,
    FederatedSearchLedger,
    build_search_coverage_report,
)

_RUN_ID = UUID("11111111-2222-3333-4444-555555555555")
_CREATED_AT = datetime(2026, 8, 16, 2, 45, tzinfo=UTC)


def _result() -> FederatedSearchResult:
    query = DiscoveryQuery(
        text="  protein   folding  ",
        year_from=2020,
        year_to=2026,
        limit_per_provider=25,
    )
    observation = ProviderObservation(
        provider="PubMed",
        provider_id="12345",
        title="A protein folding study",
        pmid="12345",
        retrieved_at="2026-08-16T02:44:00+00:00",
    )
    candidate = FederatedCandidate(
        canonical_id="pubmed:12345",
        title=observation.title,
        observations=(observation,),
    )
    return FederatedSearchResult(
        query=query,
        provider_statuses=(
            ProviderStatus(
                provider="PubMed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
                latency_ms=120,
            ),
            ProviderStatus(
                provider="OpenAlex",
                outcome=ProviderOutcome.RATE_LIMITED,
                attempted=True,
                latency_ms=80,
                reason="rate_limited",
            ),
            ProviderStatus(
                provider="Crossref",
                outcome=ProviderOutcome.SKIPPED,
                attempted=False,
                reason="unsupported_query",
            ),
        ),
        candidates=(candidate,),
    )


def _ledger(root: Path) -> FederatedSearchLedger:
    return FederatedSearchLedger(
        root,
        clock=lambda: _CREATED_AT,
        id_factory=lambda: _RUN_ID,
    )


def test_record_persists_reproducible_run_and_provider_facts(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "search-runs")

    record = ledger.record(
        _result(),
        initiated_by=" core-test ",
        project_id=" project-7 ",
        research_question_id=" rq-2 ",
    )

    assert record.schema_version == LEDGER_SCHEMA_VERSION
    assert record.search_run_id == str(_RUN_ID)
    assert record.created_at == "2026-08-16T02:45:00+00:00"
    assert record.query_text == "protein folding"
    assert record.year_from == 2020
    assert record.year_to == 2026
    assert record.limit_per_provider == 25
    assert record.completeness == "partial"
    assert record.candidate_count == 1
    assert record.initiated_by == "core-test"
    assert record.project_id == "project-7"
    assert record.research_question_id == "rq-2"
    assert record.providers_requested == ("pubmed", "openalex", "crossref")
    assert record.providers_attempted == ("pubmed", "openalex")
    assert record.providers_completed == ("pubmed",)
    assert record.providers_failed == ("openalex",)

    persisted = json.loads(
        (tmp_path / "search-runs" / f"{_RUN_ID}.json").read_text(encoding="utf-8")
    )
    assert persisted["query_text"] == "protein folding"
    assert persisted["providers"][1] == {
        "attempted": True,
        "latency_ms": 80,
        "outcome": "rate_limited",
        "provider": "openalex",
        "reason": "rate_limited",
        "result_count": 0,
        "retry_attempt_count": 0,
        # A RATE_LIMITED outcome is itself proof of rate-limiting, derived by
        # `ProviderStatus.__post_init__` regardless of which adapter produced
        # it (issue #433 item 2, Codex review finding 1) -- OpenAlex does not
        # go through Semantic Scholar's retry loop's own bookkeeping.
        "rate_limited_observed": True,
    }
    assert "api_key" not in persisted
    assert "headers" not in persisted


def test_load_round_trips_typed_record(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    recorded = ledger.record(_result())

    loaded = ledger.load(recorded.search_run_id)

    assert loaded == recorded


def test_coverage_report_is_deterministic_and_does_not_guess(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    recorded = ledger.record(_result())

    report = ledger.coverage_report(recorded.search_run_id)

    assert report.search_run_id == str(_RUN_ID)
    assert report.completeness == "partial"
    assert report.raw_observation_count == 1
    assert report.candidate_count == 1
    assert report.providers_requested == ("pubmed", "openalex", "crossref")
    assert report.providers_attempted == ("pubmed", "openalex")
    assert report.providers_completed == ("pubmed",)
    assert report.providers_failed == ("openalex",)


def test_raw_observation_count_exceeds_candidate_count_after_dedup(tmp_path: Path) -> None:
    """Issue #433's candidate-funnel ask: expose discovered vs deduplicated counts.

    Two providers each report one raw observation of the *same* underlying
    work, already deduplicated upstream into a single `FederatedCandidate`
    with two observations. `raw_observation_count` (sum of per-provider
    `result_count`) must reflect the two raw observations providers actually
    returned, while `candidate_count` reflects the one canonical candidate
    that survived deduplication -- the gap between them is exactly the
    funnel's dedup narrowing, previously only reconstructible by hand.
    """

    ledger = _ledger(tmp_path)
    shared_candidate = FederatedCandidate(
        canonical_id="doi:10.1/shared",
        title="A shared protein folding study",
        observations=(
            ProviderObservation(
                provider="PubMed", provider_id="1", title="A shared protein folding study"
            ),
            ProviderObservation(
                provider="OpenAlex", provider_id="W1", title="A shared protein folding study"
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="protein folding"),
        provider_statuses=(
            ProviderStatus(
                provider="PubMed", outcome=ProviderOutcome.SUCCESS, attempted=True, result_count=1
            ),
            ProviderStatus(
                provider="OpenAlex",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
        candidates=(shared_candidate,),
    )

    record = ledger.record(result)
    report = ledger.coverage_report(record.search_run_id)

    assert report.raw_observation_count == 2
    assert report.candidate_count == 1
    assert report.to_dict()["raw_observation_count"] == 2


def test_raw_observation_count_excludes_unattempted_providers(tmp_path: Path) -> None:
    """A skipped/disabled provider's own `result_count` must never count as discovered.

    `ProviderStatus`/`ProviderCoverageRecord` permit a `SKIPPED` or `DISABLED`
    record (`attempted=False`) to still carry a nonzero `result_count` --
    nothing in that type rules it out. `raw_observation_count` is documented
    as the sum over *attempted* providers only, so such a record must not
    inflate the funnel count with observations from a provider that was
    never actually queried.
    """

    ledger = _ledger(tmp_path)
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="protein folding"),
        provider_statuses=(
            ProviderStatus(
                provider="PubMed", outcome=ProviderOutcome.SUCCESS, attempted=True, result_count=2
            ),
            ProviderStatus(
                provider="Crossref",
                outcome=ProviderOutcome.SKIPPED,
                attempted=False,
                result_count=5,
                reason="unsupported_query",
            ),
        ),
    )

    record = ledger.record(result)
    report = ledger.coverage_report(record.search_run_id)

    assert report.raw_observation_count == 2


def test_total_retry_attempts_and_rate_limited_providers_are_derived_from_facts(
    tmp_path: Path,
) -> None:
    """Issue #433 item 2: retry/rate-limit facts must round-trip through the ledger.

    `total_retry_attempts` sums `retry_attempt_count` across attempted
    providers only (mirroring `raw_observation_count`'s own attempted-only
    contract); `providers_rate_limited` names every attempted provider that
    observed a 429 at least once, even one -- like Semantic Scholar here --
    whose retries ultimately succeeded.
    """

    ledger = _ledger(tmp_path)
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="protein folding"),
        provider_statuses=(
            ProviderStatus(
                provider="semantic_scholar",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=3,
                retry_attempt_count=2,
                rate_limited_observed=True,
            ),
            ProviderStatus(
                provider="PubMed",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
            ProviderStatus(
                provider="Crossref",
                outcome=ProviderOutcome.SKIPPED,
                attempted=False,
                reason="unsupported_query",
            ),
        ),
    )

    record = ledger.record(result)
    report = ledger.coverage_report(record.search_run_id)

    assert record.providers[0].retry_attempt_count == 2
    assert record.providers[0].rate_limited_observed is True
    assert report.total_retry_attempts == 2
    assert report.providers_rate_limited == ("semantic_scholar",)
    assert report.to_dict()["total_retry_attempts"] == 2
    assert report.to_dict()["providers_rate_limited"] == ["semantic_scholar"]


def test_unattempted_provider_never_reports_a_fabricated_retry_count(tmp_path: Path) -> None:
    """A skipped provider was never retried; it must not inflate the run total."""

    ledger = _ledger(tmp_path)
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="protein folding"),
        provider_statuses=(
            ProviderStatus(
                provider="PubMed", outcome=ProviderOutcome.SUCCESS, attempted=True, result_count=1
            ),
            ProviderStatus(
                provider="Crossref",
                outcome=ProviderOutcome.SKIPPED,
                attempted=False,
                reason="unsupported_query",
            ),
        ),
    )

    record = ledger.record(result)
    report = ledger.coverage_report(record.search_run_id)

    assert record.providers[1].retry_attempt_count == 0
    assert record.providers[1].rate_limited_observed is False
    assert report.total_retry_attempts == 0
    assert report.providers_rate_limited == ()


def test_load_defaults_retry_fields_to_zero_for_pre_existing_records(tmp_path: Path) -> None:
    """Records persisted before retry tracking existed must remain loadable.

    Mirrors `test_load_defaults_candidates_to_empty_tuple_for_pre_existing_records`:
    a run recorded before `retry_attempt_count`/`rate_limited_observed` existed
    simply omits those keys, and must load with the honest "no retry
    happened" state (`0`/`False`) rather than fail to parse or fabricate a
    retry that was never recorded.
    """

    root = tmp_path / "search-runs"
    root.mkdir()
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "search_run_id": str(_RUN_ID),
        "created_at": "2026-08-16T02:45:00+00:00",
        "query_text": "protein folding",
        "year_from": 2020,
        "year_to": 2026,
        "limit_per_provider": 25,
        "completeness": "complete",
        "candidate_count": 0,
        "providers": [
            {
                "provider": "semantic_scholar",
                "outcome": "success",
                "attempted": True,
                "result_count": 1,
                "latency_ms": 120,
                "reason": None,
                # deliberately no "retry_attempt_count"/"rate_limited_observed"
                # keys -- pre-existing record shape
            }
        ],
        "initiated_by": None,
        "project_id": None,
        "research_question_id": None,
        "candidates": [],
    }
    (root / f"{_RUN_ID}.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = FederatedSearchLedger(root).load(str(_RUN_ID))

    assert loaded.providers[0].retry_attempt_count == 0
    assert loaded.providers[0].rate_limited_observed is False
    report = build_search_coverage_report(loaded)
    assert report.total_retry_attempts == 0
    assert report.providers_rate_limited == ()


def test_load_derives_rate_limited_observed_for_pre_existing_rate_limited_records(
    tmp_path: Path,
) -> None:
    """A pre-existing record whose own outcome is already "rate_limited" must
    not load as rate_limited_observed=False merely because that field
    postdates the record.

    Defaulting the missing key to False would fabricate an absence of
    rate-limiting the record's own `outcome` field already contradicts
    (issue #433 item 2, Codex review finding 4 -- the backward-compatible-
    loading counterpart to finding 1's forward-construction fix; both are
    derived by the same `ProviderCoverageRecord.__post_init__`).
    """

    root = tmp_path / "search-runs"
    root.mkdir()
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "search_run_id": str(_RUN_ID),
        "created_at": "2026-08-16T02:45:00+00:00",
        "query_text": "protein folding",
        "year_from": 2020,
        "year_to": 2026,
        "limit_per_provider": 25,
        "completeness": "partial",
        "candidate_count": 0,
        "providers": [
            {
                "provider": "openalex",
                "outcome": "rate_limited",
                "attempted": True,
                "result_count": 0,
                "latency_ms": 80,
                "reason": "rate_limited",
                # deliberately no "rate_limited_observed" key -- pre-existing
                # record shape, persisted before this field existed
            }
        ],
        "initiated_by": None,
        "project_id": None,
        "research_question_id": None,
        "candidates": [],
    }
    (root / f"{_RUN_ID}.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = FederatedSearchLedger(root).load(str(_RUN_ID))

    assert loaded.providers[0].rate_limited_observed is True
    report = build_search_coverage_report(loaded)
    assert report.providers_rate_limited == ("openalex",)


def test_record_is_immutable_and_refuses_overwrite(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    ledger.record(_result())

    with pytest.raises(FileExistsError, match="already exists"):
        ledger.record(_result())


def test_record_rejects_naive_clock(tmp_path: Path) -> None:
    ledger = FederatedSearchLedger(
        tmp_path,
        clock=lambda: datetime(2026, 8, 16, 2, 45),
        id_factory=lambda: _RUN_ID,
    )

    with pytest.raises(ValueError, match="timezone-aware"):
        ledger.record(_result())


def test_record_rejects_blank_optional_context(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError, match="must not be blank"):
        ledger.record(_result(), project_id="   ")


def test_load_rejects_path_traversal_as_invalid_uuid(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    with pytest.raises(ValueError):
        ledger.load("../outside")


def test_list_by_research_question_id_returns_matches_newest_first(tmp_path: Path) -> None:
    root = tmp_path / "search-runs"
    run_a_id = UUID("11111111-1111-1111-1111-111111111111")
    run_b_id = UUID("22222222-2222-2222-2222-222222222222")
    run_c_id = UUID("33333333-3333-3333-3333-333333333333")

    ledger_a = FederatedSearchLedger(
        root,
        clock=lambda: datetime(2026, 8, 1, tzinfo=UTC),
        id_factory=lambda: run_a_id,
    )
    ledger_a.record(_result(), research_question_id="rq-1")

    ledger_b = FederatedSearchLedger(
        root,
        clock=lambda: datetime(2026, 8, 16, tzinfo=UTC),
        id_factory=lambda: run_b_id,
    )
    ledger_b.record(_result(), research_question_id="rq-1")

    ledger_c = FederatedSearchLedger(
        root,
        clock=lambda: datetime(2026, 8, 10, tzinfo=UTC),
        id_factory=lambda: run_c_id,
    )
    ledger_c.record(_result(), research_question_id="rq-other")

    matches = FederatedSearchLedger(root).list_by_research_question_id("rq-1")

    assert [record.search_run_id for record in matches] == [str(run_b_id), str(run_a_id)]
    assert all(record.research_question_id == "rq-1" for record in matches)


def test_list_by_research_question_id_returns_empty_for_unknown_question(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "search-runs")
    ledger.record(_result(), research_question_id="rq-1")

    assert ledger.list_by_research_question_id("rq-does-not-exist") == ()


def test_list_by_research_question_id_returns_empty_for_missing_ledger_root(
    tmp_path: Path,
) -> None:
    ledger = FederatedSearchLedger(tmp_path / "never-created")

    assert ledger.list_by_research_question_id("rq-1") == ()


def test_list_by_research_question_id_rejects_blank_input(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "search-runs")

    with pytest.raises(ValueError, match="non-blank"):
        ledger.list_by_research_question_id("   ")


def test_record_persists_full_candidate_snapshot_with_provider_observations(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path / "search-runs")

    record = ledger.record(_result())

    assert len(record.candidates) == 1
    candidate = record.candidates[0]
    assert candidate.canonical_id == "pubmed:12345"
    assert candidate.title == "A protein folding study"
    assert candidate.doi is None
    assert len(candidate.observations) == 1
    observation = candidate.observations[0]
    assert observation.provider == "PubMed"
    assert observation.provider_id == "12345"
    assert observation.pmid == "12345"
    assert observation.retrieved_at == "2026-08-16T02:44:00+00:00"

    persisted = json.loads(
        (tmp_path / "search-runs" / f"{_RUN_ID}.json").read_text(encoding="utf-8")
    )
    assert persisted["candidates"][0]["canonical_id"] == "pubmed:12345"
    assert persisted["candidates"][0]["observations"][0]["provider"] == "PubMed"


def test_record_persists_publication_status_flags_on_observations(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path / "search-runs")
    observation = ProviderObservation(
        provider="Crossref",
        provider_id="10.1000/example",
        title="A retracted study",
        doi="10.1000/example",
        retracted=True,
        corrected=False,
        expression_of_concern=True,
        withdrawn=False,
        retrieved_at="2026-08-16T02:44:00+00:00",
    )
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/example",
        title=observation.title,
        doi="10.1000/example",
        observations=(observation,),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="publication status"),
        provider_statuses=(
            ProviderStatus(
                provider="Crossref", outcome=ProviderOutcome.SUCCESS, attempted=True, result_count=1
            ),
        ),
        candidates=(candidate,),
    )

    record = ledger.record(result)

    persisted_observation = record.candidates[0].observations[0]
    assert persisted_observation.retracted is True
    assert persisted_observation.corrected is False
    assert persisted_observation.expression_of_concern is True
    assert persisted_observation.withdrawn is False

    loaded = ledger.load(record.search_run_id)
    reloaded_observation = loaded.candidates[0].observations[0]
    assert reloaded_observation.retracted is True
    assert reloaded_observation.corrected is False
    assert reloaded_observation.expression_of_concern is True
    assert reloaded_observation.withdrawn is False


def test_load_defaults_publication_status_flags_to_none_for_pre_existing_records(
    tmp_path: Path,
) -> None:
    """Candidate observations persisted before these flags existed must stay loadable.

    Mirrors `test_load_defaults_candidates_to_empty_tuple_for_pre_existing_records`:
    a record written before `corrected`/`expression_of_concern`/`withdrawn` existed
    simply omits those keys, and must load with an honest `None` ("not recorded")
    rather than fail to parse or fabricate a `False`.
    """

    root = tmp_path / "search-runs"
    root.mkdir()
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "search_run_id": str(_RUN_ID),
        "created_at": "2026-08-16T02:45:00+00:00",
        "query_text": "protein folding",
        "year_from": None,
        "year_to": None,
        "limit_per_provider": 20,
        "completeness": "complete",
        "candidate_count": 1,
        "providers": [
            {
                "provider": "pubmed",
                "outcome": "success",
                "attempted": True,
                "result_count": 1,
                "latency_ms": None,
                "reason": None,
            }
        ],
        "initiated_by": None,
        "project_id": None,
        "research_question_id": None,
        "candidates": [
            {
                "canonical_id": "pubmed:12345",
                "title": "A protein folding study",
                "doi": None,
                "publication_year": None,
                "observations": [
                    {
                        "provider": "pubmed",
                        "provider_id": "12345",
                        "title": "A protein folding study",
                        "authors": [],
                        "publication_year": None,
                        "venue": None,
                        "abstract": None,
                        "doi": None,
                        "pmid": "12345",
                        "pmcid": None,
                        "arxiv_id": None,
                        "openalex_id": None,
                        "semantic_scholar_id": None,
                        "landing_url": None,
                        "full_text_url": None,
                        "xml_url": None,
                        "license": None,
                        "metadata_source": None,
                        "pmcid_source": None,
                        "open_access_source": None,
                        "citation_count": None,
                        "open_access": None,
                        "retracted": True,
                        "preprint": None,
                        "preprint_version": None,
                        "related_journal_doi": None,
                        "related_journal_reference": None,
                        "retrieved_at": None,
                        # deliberately no "corrected"/"expression_of_concern"/
                        # "withdrawn" keys -- pre-existing record shape
                    }
                ],
            }
        ],
    }
    (root / f"{_RUN_ID}.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = FederatedSearchLedger(root).load(str(_RUN_ID))

    observation = loaded.candidates[0].observations[0]
    assert observation.retracted is True
    assert observation.corrected is None
    assert observation.expression_of_concern is None
    assert observation.withdrawn is None


def test_load_defaults_candidates_to_empty_tuple_for_pre_existing_records(
    tmp_path: Path,
) -> None:
    """Records persisted before candidate-snapshot support must remain readable.

    The ledger is a durable, replayable record; a run recorded before this
    field existed must load with an honest empty candidate list rather than
    fail to parse or fabricate candidates that were never persisted.
    """

    root = tmp_path / "search-runs"
    root.mkdir()
    payload = {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "search_run_id": str(_RUN_ID),
        "created_at": "2026-08-16T02:45:00+00:00",
        "query_text": "protein folding",
        "year_from": 2020,
        "year_to": 2026,
        "limit_per_provider": 25,
        "completeness": "partial",
        "candidate_count": 1,
        "providers": [
            {
                "provider": "pubmed",
                "outcome": "success",
                "attempted": True,
                "result_count": 1,
                "latency_ms": 120,
                "reason": None,
            }
        ],
        "initiated_by": None,
        "project_id": None,
        "research_question_id": None,
        # deliberately no "candidates" key -- pre-existing record shape
    }
    (root / f"{_RUN_ID}.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = FederatedSearchLedger(root).load(str(_RUN_ID))

    assert loaded.candidates == ()
    assert loaded.candidate_count == 1


def test_load_rejects_malformed_or_wrong_schema_record(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    root.mkdir()
    path = root / f"{_RUN_ID}.json"
    path.write_text("not-json", encoding="utf-8")
    ledger = _ledger(root)

    with pytest.raises(ValueError, match="malformed"):
        ledger.load(str(_RUN_ID))

    path.write_text(
        json.dumps(
            {
                "schema_version": 999,
                "search_run_id": str(_RUN_ID),
                "providers": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema version"):
        ledger.load(str(_RUN_ID))
