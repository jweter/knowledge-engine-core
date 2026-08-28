"""Evidence Intelligence command for the slim ``ke-research`` runtime.

The computation is the same deterministic EvidenceRecord/graph calculation as
the production CLI, exposed here without importing ``entrypoint``. The JSON
shape is the public contract consumed by ``knowledge-engine-ai.ke_client``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, GraphRepository
from knowledge_engine.evidence_intelligence import (
    compute_claim_confidence,
    compute_evidence_consensus,
    compute_evidence_coverage,
    compute_evidence_quality,
    render_synthesis,
)

EvidenceOption = Annotated[
    Path,
    typer.Option("--evidence", exists=True, dir_okay=False, readable=True),
]
EvidenceRecordIdOption = Annotated[str, typer.Option("--evidence-record-id")]
OutputOption = Annotated[Path | None, typer.Option("--output")]
ForceOutputOption = Annotated[bool, typer.Option("--force")]
FormatOption = Annotated[str, typer.Option("--format")]


def register_research_intelligence_commands(app: typer.Typer) -> None:
    """Register Evidence Intelligence on the slim Research Copilot surface."""

    app.command("evidence-intelligence")(evidence_intelligence)


def evidence_intelligence(
    evidence: EvidenceOption,
    evidence_record_id: EvidenceRecordIdOption,
    output: OutputOption = None,
    force: ForceOutputOption = False,
    report_format: FormatOption = "markdown",
) -> None:
    """Compute deterministic quality, consensus, confidence, and coverage for one claim."""

    if report_format not in ("markdown", "json"):
        raise typer.BadParameter("--format must be 'markdown' or 'json'.")
    if output is not None:
        _validate_output(output, force=force)

    records = _read_jsonl(evidence)
    records_by_id = {
        str(record["evidence_record_id"]): record
        for record in records
        if isinstance(record.get("evidence_record_id"), str)
        and str(record["evidence_record_id"]).strip()
    }

    database = _local_database()
    database.initialize()
    with database.session() as session:
        graph = GraphRepository(session)
        payload = _build_payload(graph, records_by_id, evidence_record_id)

    if report_format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    else:
        rendered = _render_markdown(payload)

    if output is not None:
        _write_output(output, rendered)
        return
    if report_format == "json":
        sys.stdout.write(rendered)
    else:
        typer.echo(rendered)


def _build_payload(
    graph: GraphRepository,
    records_by_id: dict[str, dict[str, Any]],
    evidence_record_id: str,
) -> dict[str, Any]:
    record = records_by_id.get(evidence_record_id)
    if record is None:
        typer.echo(
            f"No evidence record found for evidence_record_id: {evidence_record_id}", err=True
        )
        raise typer.Exit(1)

    claim = graph.find_claim_by_evidence_id(evidence_record_id)
    if claim is None:
        # AI's subprocess wrapper treats this exact marker as the expected
        # "graph not built yet" state and returns None rather than failing.
        typer.echo(f"No graph claim found for evidence_record_id: {evidence_record_id}", err=True)
        raise typer.Exit(1)

    relationships = graph.relationships_for_claim(claim.id)
    relationship_types = [relationship.relationship_type for relationship in relationships]
    quality = compute_evidence_quality(record)
    consensus = compute_evidence_consensus(relationship_types)

    participating_qualities = [quality]
    seen_other_claim_ids: set[int] = set()
    for relationship in relationships:
        if relationship.relationship_type not in ("supports", "contradicts"):
            continue
        other_claim_id = (
            relationship.target_claim_id
            if relationship.source_claim_id == claim.id
            else relationship.source_claim_id
        )
        if other_claim_id == claim.id or other_claim_id in seen_other_claim_ids:
            continue
        seen_other_claim_ids.add(other_claim_id)
        other_claim = graph.get_claim(other_claim_id)
        other_record = records_by_id.get(other_claim.evidence_record_id) if other_claim else None
        if other_record is not None:
            participating_qualities.append(compute_evidence_quality(other_record))

    confidence = compute_claim_confidence(participating_qualities, consensus)
    graph_counts = graph.population_counts()
    coverage = compute_evidence_coverage(
        total_records=len(records_by_id),
        records_in_relationship=graph_counts["claims"] - len(graph.unconfirmed_claims()),
    )

    return {
        "schema_version": 1,
        "evidence_record_id": evidence_record_id,
        "claim_id": claim.id,
        "evidence_quality": {
            "score": quality.score,
            "study_design_tier": quality.study_design_tier,
            "manually_reviewed": quality.manually_reviewed,
            "extraction_tier": quality.extraction_tier,
        },
        "evidence_consensus": {
            "relationship_edge_count": consensus.relationship_edge_count,
            "supports_count": consensus.supports_count,
            "contradicts_count": consensus.contradicts_count,
            "agreement_total": consensus.agreement_total,
            "score": consensus.score,
            "reliability": consensus.reliability,
        },
        "claim_confidence": {
            "score": confidence.score,
            "reliability": confidence.reliability,
        },
        "evidence_coverage": {
            "records_in_relationship": coverage.records_in_relationship,
            "total_records": coverage.total_records,
            "percentage": coverage.percentage,
        },
        "synthesis": render_synthesis(
            consensus=consensus,
            quality=quality,
            confidence=confidence,
            coverage=coverage,
        ),
        "scope_note": (
            "Every number above is computed deterministically from already-stored "
            "EvidenceRecord/RelationshipRecord fields -- no LLM, nothing invented or "
            "inferred beyond what is already stored. evidence_quality, evidence_consensus, "
            "and claim_confidence are three separate numbers."
        ),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    quality = payload["evidence_quality"]
    consensus = payload["evidence_consensus"]
    confidence = payload["claim_confidence"]
    coverage = payload["evidence_coverage"]
    assert isinstance(quality, dict)
    assert isinstance(consensus, dict)
    assert isinstance(confidence, dict)
    assert isinstance(coverage, dict)
    return "\n".join(
        [
            "# Knowledge Engine Evidence Intelligence Report",
            "",
            f"Evidence record ID: {payload['evidence_record_id']}",
            f"Evidence Quality: {quality['score']}/100",
            f"Evidence Consensus: {consensus['score']}",
            f"Claim Confidence: {confidence['score']}",
            (
                "Evidence Coverage: "
                f"{coverage['records_in_relationship']} / {coverage['total_records']} "
                f"({coverage['percentage']}%)"
            ),
            "",
            str(payload["scope_note"]),
            "",
        ]
    )


def _local_database() -> Database:
    return Database(build_settings(Path.cwd()))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Line {line_number}: invalid JSON.") from exc
        if not isinstance(parsed, dict):
            raise typer.BadParameter(f"Line {line_number}: record must be a JSON object.")
        records.append(parsed)
    return records


def _validate_output(output: Path, *, force: bool) -> None:
    if output.is_symlink():
        raise typer.BadParameter("Output must not be a symbolic link.")
    if output.exists() and not force:
        raise typer.BadParameter("Output already exists. Use --force to overwrite.")


def _write_output(output: Path, content: str) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    except OSError:
        raise typer.BadParameter("Output file could not be written.") from None
