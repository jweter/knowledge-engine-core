#!/usr/bin/env python3
"""Benchmark deterministic extraction against human-reviewed ground truth.

Read-only: writes no extraction runs, no draft evidence items, no
EvidenceRecord rows -- see `knowledge_engine.extraction_accuracy_benchmark`
for what this measures, how ground truth is selected, and why.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.extraction.evidence_items import PaperMetadata
from knowledge_engine.extraction_accuracy_benchmark import run_extraction_accuracy_benchmark
from knowledge_engine.parser import ParsedPage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence", required=True, type=Path, help="Validated evidence_records.jsonl path."
    )
    parser.add_argument("--output", required=True, type=Path, help="Report JSON output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    import json

    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> int:
    args = _parser().parse_args()
    if args.output.exists() and not args.force:
        print(f"Output already exists: {args.output}. Use --force to overwrite.")
        return 1

    evidence_records = _read_jsonl(args.evidence)

    database = Database(build_settings(Path.cwd()))
    database.initialize()
    with database.session() as session:
        papers_by_doi = {
            paper.doi.strip().lower(): paper
            for paper in PaperRepository(session).list_papers()
            if paper.doi
        }

        def resolve_paper(doi: str) -> tuple[PaperMetadata, list[ParsedPage]] | None:
            paper = papers_by_doi.get(doi.strip().lower())
            if paper is None:
                return None
            pages = [
                ParsedPage(page_number=page.page_number, text=page.text, table_text=page.table_text)
                for page in paper.pages
            ]
            return PaperMetadata(paper_id=paper.id, doi=paper.doi, title=paper.title), pages

        summary = run_extraction_accuracy_benchmark(evidence_records, resolve_paper)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(summary.to_json(), encoding="utf-8")

    print(f"Rules version: {summary.rules_version}")
    print(
        f"Ground-truth records considered: {summary.ground_truth_records_considered} "
        f"(benchmarked: {summary.records_benchmarked}, "
        f"skipped no paper match: {len(summary.records_skipped_no_paper_match)}, "
        f"skipped no pages: {len(summary.records_skipped_no_pages)})."
    )
    print(f"study_type exact-match rate: {summary.study_type_exact_match_rate}")
    print(f"limitations presence-match rate: {summary.limitations_presence_match_rate}")
    print(f"PICO presence-match rate: {summary.pico_presence_match_rate}")
    print(f"PICO mean token-overlap: {summary.pico_mean_overlap}")
    print(f"Full report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
