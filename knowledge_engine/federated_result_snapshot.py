"""Public, JSON-ready snapshot contract for one federated discovery run.

This module joins a live ``FederatedSearchResult`` to the deterministic public
``SearchCoverageReport`` persisted for the same run.  It deliberately does not
serialize internal ledger context, credentials, transport state, or
provider-native raw responses.
"""

from __future__ import annotations

import json
from typing import Any, cast

from knowledge_engine.federated_discovery import FederatedSearchResult
from knowledge_engine.federated_search_ledger import SearchCoverageReport
from knowledge_engine.provider_disagreement import build_provider_disagreement_report


def build_public_federated_result_payload(
    result: FederatedSearchResult,
    coverage: SearchCoverageReport,
) -> dict[str, Any]:
    """Return the programmatic discovery snapshot consumed across repo boundaries.

    The coverage record must describe the supplied result.  Rejecting mismatched
    provenance is safer than attaching a valid search-run ID to the wrong query,
    filters, limit, completeness state, or candidate set.
    """

    mismatches: list[str] = []
    if coverage.query_text != result.query.normalized_text:
        mismatches.append("query_text")
    if coverage.year_from != result.query.year_from:
        mismatches.append("year_from")
    if coverage.year_to != result.query.year_to:
        mismatches.append("year_to")
    if coverage.limit_per_provider != result.query.limit_per_provider:
        mismatches.append("limit_per_provider")
    if coverage.completeness != result.completeness.value:
        mismatches.append("completeness")
    expected_raw_observation_count = sum(
        status.result_count for status in result.provider_statuses if status.attempted
    )
    if coverage.raw_observation_count != expected_raw_observation_count:
        mismatches.append("raw_observation_count")
    if coverage.candidate_count != len(result.candidates):
        mismatches.append("candidate_count")

    if mismatches:
        joined = ", ".join(mismatches)
        raise ValueError(f"Federated result does not match its coverage record: {joined}.")

    payload = cast(dict[str, Any], json.loads(result.to_json()))
    payload["search_run_id"] = coverage.search_run_id
    payload["coverage"] = coverage.to_dict()
    payload["provider_disagreements"] = build_provider_disagreement_report(result).to_dict()
    return payload
