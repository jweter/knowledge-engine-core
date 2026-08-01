"""Automated discovery-cycle orchestration (M55).

Every corpus-growth batch through M53 was driven by hand: run `ke
pubmed-candidate-discover` for the next `retstart` page, prepare an
adjudication worksheet, manually cross-check against
`data/corpora/glp1_weight_loss/README.md`'s prose exclusion history (the
gap M53's ledger now closes structurally), and manually track which
`retstart` offset came next. This module automates everything mechanical
in that loop -- discovery, adjudication, ledger cross-checking, and
pagination state -- into one repeatable, schedulable cycle.

It deliberately stops *before* acquisition. M14's deterministic scope
adjudication (`knowledge_engine.candidate_review.prepare_candidate_review`)
has a measured, real residual false-accept rate: this project's own
growth-batch history documents roughly a fifth of deterministically
"accepted" candidates in several real batches still being off-topic on a
human/AI title read (busulfan pharmacokinetics, off-target primary
diseases, diagnostic-only studies, and so on -- see the README's
`retstart=3000`/`retstart=3250` corrections). That is a materially
different risk than M52's evidence-direction classification: an
admitted-then-extracted wrong paper contaminates the corpus in a way
that is expensive to find and reverse (this project has already run a
full fresh reimport twice to correct it), not just one record's
directional label. So each cycle's output is a bounded "ready for
review" worksheet of net-new, deterministically-accepted candidates,
for a human or agent to give the same final scope screen this project
has always required -- `ke pmc-oa-acquire` remains a separate, explicit
step this module never triggers itself.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from knowledge_engine.candidate_review import CandidateReviewItem

DISCOVERY_CYCLE_RULES_VERSION = "m55-discovery-cycle-v1"


class DiscoveryCycleError(RuntimeError):
    """Sanitized discovery-cycle failure."""


@dataclass(frozen=True)
class DiscoveryCycleState:
    """Persisted pagination progress for one query's discovery cycle."""

    query: str
    next_retstart: int
    limit: int
    cycles_run: int
    updated_at: str


def load_discovery_cycle_state(path: Path, *, query: str, limit: int) -> DiscoveryCycleState:
    """Load persisted pagination state, or start fresh at `retstart=0`.

    Raises `DiscoveryCycleError` if a persisted state file's `query`
    does not match `query` -- a state file only ever tracks one query's
    pagination progress; silently reusing it for a different query
    would skip or duplicate results. Point `--state` at a different
    file to track a new query.
    """

    if not path.exists():
        return DiscoveryCycleState(
            query=query, next_retstart=0, limit=limit, cycles_run=0, updated_at=""
        )

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiscoveryCycleError(f"State file {path} is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise DiscoveryCycleError(f"State file {path} must contain a JSON object.")

    stored_query = payload.get("query")
    if stored_query != query:
        raise DiscoveryCycleError(
            f"State file {path} tracks query {stored_query!r}, not {query!r}. "
            "Use a different --state path to track a different query."
        )

    return DiscoveryCycleState(
        query=query,
        next_retstart=int(payload.get("next_retstart", 0)),
        limit=limit,
        cycles_run=int(payload.get("cycles_run", 0)),
        updated_at=str(payload.get("updated_at", "")),
    )


def save_discovery_cycle_state(path: Path, state: DiscoveryCycleState) -> None:
    """Persist pagination state as JSON."""

    import json

    payload = {
        "query": state.query,
        "next_retstart": state.next_retstart,
        "limit": state.limit,
        "cycles_run": state.cycles_run,
        "updated_at": state.updated_at,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def advance_discovery_cycle_state(state: DiscoveryCycleState) -> DiscoveryCycleState:
    """Return the next cycle's state: `retstart` advanced by one page, cycle count incremented."""

    return DiscoveryCycleState(
        query=state.query,
        next_retstart=state.next_retstart + state.limit,
        limit=state.limit,
        cycles_run=state.cycles_run + 1,
        updated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def candidate_review_item_to_dict(item: CandidateReviewItem) -> dict[str, object]:
    """Convert one `CandidateReviewItem` dataclass to a plain dict (for ledger checks/JSON)."""

    return asdict(item)
