#!/usr/bin/env python3
"""Run the deterministic extraction pipeline across the whole corpus and
report coverage in aggregate. Read-only: writes no extraction runs, no
draft evidence items, no EvidenceRecord rows -- see
`knowledge_engine.extraction_corpus_report` for what this measures and why.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from knowledge_engine.config import build_settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.extraction_corpus_report import build_extraction_corpus_report
from knowledge_engine.parser import ParsedPage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Report JSON output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.output.exists() and not args.force:
        print(f"Output already exists: {args.output}. Use --force to overwrite.")
        return 1

    database = Database(build_settings(Path.cwd()))
    database.initialize()
    with database.session() as session:
        papers = PaperRepository(session).list_papers()
        paper_pages = [
            (
                paper.id,
                [ParsedPage(page_number=page.page_number, text=page.text) for page in paper.pages],
            )
            for paper in papers
        ]

    report = build_extraction_corpus_report(paper_pages)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.to_json(), encoding="utf-8")

    print(
        f"Summarized {report.paper_count} paper(s) "
        f"({report.papers_with_zero_pages} with zero pages excluded)."
    )
    print(
        f"Zero sections detected: {report.papers_with_zero_sections}; "
        f"zero claim candidates: {report.papers_with_zero_candidates}."
    )
    print(f"Study type coverage: {report.study_type_coverage}")
    print(
        f"PICO coverage -- population: {report.population_coverage_count}, "
        f"intervention: {report.intervention_coverage_count}, "
        f"comparator: {report.comparator_coverage_count}, "
        f"outcome: {report.outcome_coverage_count}, "
        f"all four: {report.all_pico_fields_coverage_count}."
    )
    print(f"Limitations detected: {report.limitations_coverage_count}.")
    print(f"Full report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
