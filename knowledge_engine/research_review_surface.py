"""Extraction and grounding-review commands for the slim ``ke-research`` runtime.

These are the exact workflow steps `knowledge-engine-ai` uses after a paper has
been persisted. They are registered without importing the production
``entrypoint`` module, preserving the slim runtime's dependency boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, ExtractionRunRepository, PaperRepository
from knowledge_engine.evidence_review_automate import automate_review_for_record
from knowledge_engine.extraction import (
    CLAIM_CANDIDATE_RULES_VERSION,
    CLAIM_FRAMING_RULES_VERSION,
    DRAFT_EVIDENCE_ITEM_RULES_VERSION,
    EVIDENCE_CLASSIFICATION_RULES_VERSION,
    LLM_GROUNDED_PICO_RULES_VERSIONS,
    PICO_EXTRACTION_RULES_VERSION,
    SECTION_DETECTION_RULES_VERSION,
    STUDY_DESIGN_RULES_VERSION,
    build_automated_evidence_record,
)
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_review_batch import run_batch_extraction_review
from knowledge_engine.llm import LocalLLMError, OllamaLLM
from knowledge_engine.parser import ParsedPage

ExtractionReviewOutputOption = Annotated[Path, typer.Option("--output")]
ExtractionReviewPaperIdsOption = Annotated[list[int] | None, typer.Option("--paper-id")]
ExtractionReviewInputOption = Annotated[
    Path,
    typer.Option("--input", exists=True, dir_okay=False, readable=True),
]
ForceOutputOption = Annotated[bool, typer.Option("--force")]
EvidenceFileOption = Annotated[
    Path,
    typer.Option("--evidence", exists=True, dir_okay=False, readable=True),
]
EvidenceReviewLimitOption = Annotated[int, typer.Option("--limit", min=1, max=100)]
EvidenceReviewModelOption = Annotated[
    str | None,
    typer.Option("--model", envvar="KE_LLM_MODEL"),
]
EvidenceRecordIdOption = Annotated[str | None, typer.Option("--evidence-record-id")]
DryRunOption = Annotated[bool, typer.Option("--dry-run")]

_MANUAL_EXTRACTION_METHODS = frozenset({"manual_human_review", "manual"})


def register_research_review_commands(app: typer.Typer) -> None:
    """Register the extraction/grounding commands needed by Research Copilot."""

    app.command("extraction-review-batch-generate")(extraction_review_batch_generate)
    app.command("extraction-review-autoclassify")(extraction_review_autoclassify)
    app.command("evidence-review-automate")(evidence_review_automate)
    app.command("evidence-record-review-promote")(evidence_record_review_promote)


def extraction_review_batch_generate(
    output: ExtractionReviewOutputOption,
    paper_id: ExtractionReviewPaperIdsOption = None,
    force: ForceOutputOption = False,
) -> None:
    """Generate one deterministic draft-review queue across selected persisted papers."""

    _validate_output(output, force=force)
    database = _local_database()
    database.initialize()
    lines: list[str] = []
    recorded_paper_count = 0
    unrecorded_paper_ids: list[int] = []

    with database.session() as session:
        repository = PaperRepository(session)
        if paper_id:
            papers = repository.get_many(paper_id)
            missing_ids = sorted(set(paper_id) - {paper.id for paper in papers})
            if missing_ids:
                typer.echo(
                    "Unknown paper ID(s): " + ", ".join(str(value) for value in missing_ids),
                    err=True,
                )
                raise typer.Exit(1)
        else:
            papers = repository.list_papers()

        if not papers:
            _write_output(output, "")
            typer.echo("No papers found to process.")
            return

        paper_pages = [
            (
                PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title),
                [
                    ParsedPage(
                        page_number=page.page_number,
                        text=page.text,
                        table_text=page.table_text,
                    )
                    for page in paper.pages
                ],
            )
            for paper in sorted(papers, key=lambda item: item.id)
        ]
        summary = run_batch_extraction_review(paper_pages)

        run_repository = ExtractionRunRepository(session)
        for result in summary.results:
            try:
                with session.begin_nested():
                    run_repository.create(
                        paper_id=result.paper_id,
                        output_path=str(output),
                        page_count=result.page_count,
                        section_count=result.section_count,
                        candidate_count=result.candidate_count,
                        draft_item_count=len(result.draft_items),
                        section_detection_rules_version=SECTION_DETECTION_RULES_VERSION,
                        claim_candidate_rules_version=CLAIM_CANDIDATE_RULES_VERSION,
                        claim_framing_rules_version=CLAIM_FRAMING_RULES_VERSION,
                        draft_evidence_item_rules_version=DRAFT_EVIDENCE_ITEM_RULES_VERSION,
                        study_design_rules_version=STUDY_DESIGN_RULES_VERSION,
                        pico_extraction_rules_version=PICO_EXTRACTION_RULES_VERSION,
                    )
            except Exception:
                unrecorded_paper_ids.append(result.paper_id)
                continue
            recorded_paper_count += 1
            lines.extend(json.dumps(item.to_dict()) for item in result.draft_items)

        _write_output(output, "\n".join(lines) + ("\n" if lines else ""))

    if unrecorded_paper_ids:
        typer.echo(
            "Extraction runs could not be recorded for paper ID(s): "
            + ", ".join(str(value) for value in unrecorded_paper_ids),
            err=True,
        )
    typer.echo(
        f"draft_items={len(lines)} papers={recorded_paper_count} "
        f"skipped_no_pages={summary.papers_with_zero_pages} output={output}"
    )


def extraction_review_autoclassify(
    input_path: ExtractionReviewInputOption,
    output: ExtractionReviewOutputOption,
    force: ForceOutputOption = False,
) -> None:
    """Deterministically fill research_question/evidence_direction for eligible drafts."""

    _validate_output(output, force=force)
    items = _read_jsonl(input_path)
    classified: list[dict[str, Any]] = []
    for item in items:
        record = build_automated_evidence_record(item)
        if record is not None:
            classified.append(record)

    _write_output(
        output,
        "\n".join(json.dumps(record) for record in classified) + ("\n" if classified else ""),
    )
    typer.echo(
        f"classified={len(classified)} input={len(items)} "
        f"rules={EVIDENCE_CLASSIFICATION_RULES_VERSION} output={output}"
    )


def evidence_review_automate(
    evidence: EvidenceFileOption,
    limit: EvidenceReviewLimitOption = 5,
    model: EvidenceReviewModelOption = None,
    evidence_record_id: EvidenceRecordIdOption = None,
    dry_run: DryRunOption = False,
) -> None:
    """Run the grounding-verified local-LLM review pass over eligible records."""

    llm_model = model or build_settings(Path.cwd()).llm_model
    if not llm_model:
        typer.echo("No model given. Pass --model or set KE_LLM_MODEL.", err=True)
        raise typer.Exit(1)

    settings = build_settings(Path.cwd())
    llm = OllamaLLM(model=llm_model, host=settings.ollama_host)
    raw_lines = evidence.read_text(encoding="utf-8").splitlines()
    records = _parse_preserving_blank_lines(raw_lines)

    eligible_indices = [
        index
        for index, record in enumerate(records)
        if record is not None
        and not _is_already_reviewed(record)
        and (evidence_record_id is None or record.get("evidence_record_id") == evidence_record_id)
    ]
    if evidence_record_id is not None and not eligible_indices:
        typer.echo(
            f"No eligible record found for evidence_record_id {evidence_record_id!r}.", err=True
        )
        raise typer.Exit(1)

    batch_indices = eligible_indices[:limit]
    updated_ids: list[str] = []
    updated_indices: set[int] = set()
    page_text_cache: dict[tuple[int, int], str | None] = {}

    for index in batch_indices:
        record = records[index]
        assert record is not None
        record_id = str(record.get("evidence_record_id", f"line {index + 1}"))
        source_span = record.get("source_span") or {}
        paper_id = source_span.get("paper_id")
        page_number = source_span.get("page_number")

        page_text: str | None = None
        first_page_text: str | None = None
        if isinstance(paper_id, int) and isinstance(page_number, int):
            _populate_page_cache(paper_id, page_text_cache)
            page_text = page_text_cache.get((paper_id, page_number))
            if page_number != 1:
                first_page_text = page_text_cache.get((paper_id, 1))

        try:
            result = automate_review_for_record(
                llm,
                record,
                page_text,
                paper_first_page_text=first_page_text,
            )
        except LocalLLMError as exc:
            typer.echo(f"{record_id}: {exc}", err=True)
            raise typer.Exit(1) from exc

        if result.updated:
            updated_ids.append(record_id)
            updated_indices.add(index)

    if dry_run:
        typer.echo(f"Dry run: {len(updated_ids)} record(s) would be updated; nothing written.")
        return

    if updated_indices:
        _rewrite_selected_lines(evidence, raw_lines, records, updated_indices)
    typer.echo(
        f"updated={len(updated_ids)} eligible={len(eligible_indices)} "
        f"processed={len(batch_indices)}"
    )


def evidence_record_review_promote(
    evidence: EvidenceFileOption,
    dry_run: DryRunOption = False,
) -> None:
    """Promote already-grounded/manual records to review_status=reviewed in place."""

    raw_lines = evidence.read_text(encoding="utf-8").splitlines()
    records = _parse_preserving_blank_lines(raw_lines)
    eligible_indices = [
        index
        for index, record in enumerate(records)
        if record is not None
        and record.get("review_status") != "reviewed"
        and _is_already_reviewed(record)
    ]

    if dry_run:
        typer.echo(
            f"Dry run: {len(eligible_indices)} record(s) would be promoted; nothing written."
        )
        return

    for index in eligible_indices:
        record = records[index]
        assert record is not None
        record["review_status"] = "reviewed"
        existing_notes = record.get("review_notes")
        promotion_note = (
            "Automated promotion: review_status set to 'reviewed' from already-grounding-verified "
            "extraction or manual provenance; no new scientific judgment was introduced."
        )
        record["review_notes"] = (
            f"{existing_notes} {promotion_note}" if existing_notes else promotion_note
        )

    if eligible_indices:
        _rewrite_selected_lines(evidence, raw_lines, records, set(eligible_indices))
    typer.echo(f"promoted={len(eligible_indices)}")


def _is_already_reviewed(record: dict[str, Any]) -> bool:
    if record.get("extraction_method") in _MANUAL_EXTRACTION_METHODS:
        return True
    review_checklist = record.get("review_checklist")
    if isinstance(review_checklist, dict) and review_checklist.get("human_reviewed") is True:
        return True
    return (
        record.get("extraction_method") in LLM_GROUNDED_PICO_RULES_VERSIONS
        and isinstance(review_checklist, dict)
        and bool(review_checklist)
    )


def _local_database() -> Database:
    return Database(build_settings(Path.cwd()))


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


def _parse_preserving_blank_lines(raw_lines: list[str]) -> list[dict[str, Any] | None]:
    records: list[dict[str, Any] | None] = []
    for line_number, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            records.append(None)
            continue
        try:
            parsed: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            typer.echo(f"Line {line_number}: invalid JSON.", err=True)
            raise typer.Exit(1) from exc
        if not isinstance(parsed, dict):
            typer.echo(f"Line {line_number}: record must be a JSON object.", err=True)
            raise typer.Exit(1)
        records.append(parsed)
    return records


def _populate_page_cache(paper_id: int, cache: dict[tuple[int, int], str | None]) -> None:
    if any(key[0] == paper_id for key in cache):
        return
    database = _local_database()
    database.initialize()
    with database.session() as session:
        paper = PaperRepository(session).get(paper_id)
        if paper is None:
            return
        for page in paper.pages:
            cache[(paper_id, page.page_number)] = page.text


def _rewrite_selected_lines(
    path: Path,
    raw_lines: list[str],
    records: list[dict[str, Any] | None],
    selected_indices: set[int],
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for index, raw_line in enumerate(raw_lines):
            if index in selected_indices:
                record = records[index]
                assert record is not None
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")
            else:
                handle.write(raw_line + "\n")
