from pathlib import Path

import pytest

from knowledge_engine.discovery_cycle import (
    DISCOVERY_CYCLE_RULES_VERSION,
    DiscoveryCycleError,
    DiscoveryCycleState,
    advance_discovery_cycle_state,
    load_discovery_cycle_state,
    save_discovery_cycle_state,
)


def test_rules_version_is_stable() -> None:
    assert DISCOVERY_CYCLE_RULES_VERSION == "m55-discovery-cycle-v1"


def test_load_discovery_cycle_state_starts_fresh_when_missing(tmp_path: Path) -> None:
    state = load_discovery_cycle_state(tmp_path / "missing.json", query="q", limit=25)

    assert state == DiscoveryCycleState(
        query="q", next_retstart=0, limit=25, cycles_run=0, updated_at=""
    )


def test_save_and_load_discovery_cycle_state_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = DiscoveryCycleState(
        query="q", next_retstart=50, limit=25, cycles_run=2, updated_at="2026-08-01T00:00:00+00:00"
    )

    save_discovery_cycle_state(path, state)
    loaded = load_discovery_cycle_state(path, query="q", limit=25)

    assert loaded == state


def test_load_discovery_cycle_state_rejects_a_query_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    save_discovery_cycle_state(
        path,
        DiscoveryCycleState(
            query="first query", next_retstart=25, limit=25, cycles_run=1, updated_at=""
        ),
    )

    with pytest.raises(DiscoveryCycleError, match="first query"):
        load_discovery_cycle_state(path, query="a different query", limit=25)


def test_advance_discovery_cycle_state_moves_retstart_by_limit() -> None:
    state = DiscoveryCycleState(query="q", next_retstart=25, limit=25, cycles_run=1, updated_at="")

    advanced = advance_discovery_cycle_state(state)

    assert advanced.next_retstart == 50
    assert advanced.cycles_run == 2
    assert advanced.updated_at
