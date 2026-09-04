from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from knowledge_engine.acquisition_plan_ledger import AcquisitionPlanLedger
from knowledge_engine.federated_discovery import (
    DiscoveryQuery,
    FederatedCandidate,
    FederatedSearchResult,
    ProviderObservation,
    ProviderOutcome,
    ProviderStatus,
)
from knowledge_engine.federated_search_ledger import FederatedSearchLedger
from knowledge_engine.research_runtime import (
    RESEARCH_RUNTIME_CONTRACT_VERSION,
    RESEARCH_RUNTIME_REQUIRED_COMMANDS,
    app,
    research_runtime_capability_payload,
)

runner = CliRunner()


def test_capability_payload_covers_the_complete_research_manifest() -> None:
    payload = research_runtime_capability_payload()

    required = set(cast(list[str], payload["required_commands"]))
    available = set(cast(list[str], payload["available_commands"]))
    missing = set(cast(list[str], payload["missing_commands"]))

    assert payload["schema_version"] == RESEARCH_RUNTIME_CONTRACT_VERSION == 1
    assert payload["surface"] == "ke-research"
    assert required == set(RESEARCH_RUNTIME_REQUIRED_COMMANDS)
    assert available == required
    assert missing == set()
    assert payload["complete"] is True


def test_capability_command_emits_machine_readable_json() -> None:
    result = runner.invoke(app, ["research-runtime-capabilities"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == research_runtime_capability_payload()


def test_every_required_research_command_is_cli_reachable_without_execution() -> None:
    for command in RESEARCH_RUNTIME_REQUIRED_COMMANDS:
        result = runner.invoke(app, [command, "--help"])
        assert result.exit_code == 0, f"{command}: {result.stdout}"


def test_slim_runtime_import_does_not_require_phase3_vector_modules() -> None:
    """Guard the dependency seam before package slimming begins.

    Run in a fresh interpreter and poison the heavy Phase 3 module names. If
    the research runtime or one of its command modules starts importing them,
    this subprocess fails immediately even though the dev environment has the
    real packages installed.
    """

    blocked = (
        "faiss",
        "torch",
        "sentence_transformers",
        "qdrant_client",
        "knowledge_engine.vector_search",
    )
    script = "\n".join(
        [
            "import json, sys",
            f"blocked = {blocked!r}",
            "for name in blocked: sys.modules[name] = None",
            "import knowledge_engine.research_runtime",
            "for forbidden in ("
            "'knowledge_engine.entrypoint', 'knowledge_engine.command_surface'"
            "): ",
            "    assert forbidden not in sys.modules, forbidden",
            "print(json.dumps({'ok': True}))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True}


def test_poetry_exposes_additive_ke_research_entrypoint() -> None:
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")

    assert 'ke = "knowledge_engine.command_surface:app"' in pyproject
    assert 'ke-research = "knowledge_engine.research_runtime:app"' in pyproject


def test_acquisition_plan_command_durably_persists_funnel_counts(tmp_path: Path) -> None:
    """The ke-research slim surface's `general-question-acquisition-plan` is the
    command knowledge-engine-ai actually invokes; it must durably persist
    candidate-funnel counts the same way the full `ke` CLI does (issue #433
    item 3), not just the full production surface."""

    ledger_root = tmp_path / "ledger"
    candidate = FederatedCandidate(
        canonical_id="doi:10.1000/slim",
        title="Slim surface acquisition plan candidate",
        doi="10.1000/slim",
        observations=(
            ProviderObservation(
                provider="crossref",
                provider_id="10.1000/slim",
                title="Slim surface acquisition plan candidate",
                doi="10.1000/slim",
            ),
        ),
    )
    result = FederatedSearchResult(
        query=DiscoveryQuery(text="slim surface acquisition", limit_per_provider=10),
        candidates=(candidate,),
        provider_statuses=(
            ProviderStatus(
                provider="crossref",
                outcome=ProviderOutcome.SUCCESS,
                attempted=True,
                result_count=1,
            ),
        ),
    )
    run_id = (
        FederatedSearchLedger(ledger_root)
        .record(result, research_question_id="rq-slim")
        .search_run_id
    )

    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "search_run_id": run_id,
                "research_question_id": "rq-slim",
                "candidate_ids": ["doi:10.1000/slim"],
            }
        ),
        encoding="utf-8",
    )

    result_cli = runner.invoke(
        app,
        [
            "general-question-acquisition-plan",
            str(request_path),
            "--ledger-root",
            str(ledger_root),
            "--no-database",
        ],
    )

    assert result_cli.exit_code == 0, result_cli.output

    records = AcquisitionPlanLedger(ledger_root / "acquisition_plans").list_by_search_run_id(run_id)
    assert len(records) == 1
    assert records[0].research_question_id == "rq-slim"
    assert records[0].metadata_only_count == 1
