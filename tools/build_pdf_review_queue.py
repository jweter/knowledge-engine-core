"""Build deterministic local review batches from gitignored scientific PDFs.

This utility intentionally performs mechanical extraction only. It does not classify
scientific truth, promote Evidence Records, call a network service, or use an LLM.

Example:
    poetry run python tools/build_pdf_review_queue.py \
        papers/corpora/glp1_weight_loss \
        --output work/pdf_review_queue \
        --batch-size 25
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from knowledge_engine.parser import DocumentParseError, ParsedPaper, PyMuPDFParser

SECTION_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("abstract", ("abstract",)),
    ("introduction", ("introduction", "background")),
    (
        "methods",
        (
            "methods",
            "materials and methods",
            "patients and methods",
            "subjects and methods",
            "study design and methods",
            "methodology",
        ),
    ),
    (
        "statistical_methods",
        (
            "statistical analysis",
            "statistical analyses",
            "statistics",
            "data analysis",
        ),
    ),
    ("results", ("results", "findings")),
    ("discussion", ("discussion",)),
    ("conclusions", ("conclusion", "conclusions")),
    ("limitations", ("limitations", "study limitations")),
    ("references", ("references", "bibliography", "literature cited")),
)

HEADING_NUMBER_PREFIX = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s+)?", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")


@dataclass(frozen=True)
class SectionOccurrence:
    section_type: str
    source_heading: str
    page_number: int
    line_index: int


@dataclass(frozen=True)
class PaperBundle:
    review_id: str
    relative_pdf_path: str
    metadata: dict[str, object]
    review_text: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build deterministic review batches from a directory of scientific PDFs."
    )
    parser.add_argument("pdf_root", type=Path, help="Directory containing PDFs to inventory.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("work/pdf_review_queue"),
        help="Output directory. Defaults to work/pdf_review_queue.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of successfully parsed papers per review batch. Defaults to 25.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Delete and rebuild an existing output directory.",
    )
    return parser.parse_args()


def _normalize_heading(line: str) -> str:
    value = HEADING_NUMBER_PREFIX.sub("", line).strip().strip(":.-").casefold()
    return re.sub(r"\s+", " ", value)


def _match_section_heading(line: str) -> str | None:
    normalized = _normalize_heading(line)
    if not normalized or len(normalized) > 80:
        return None
    for section_type, aliases in SECTION_ALIASES:
        if normalized in aliases:
            return section_type
    return None


def _find_sections(paper: ParsedPaper) -> list[SectionOccurrence]:
    occurrences: list[SectionOccurrence] = []
    for page in paper.pages:
        for line_index, line in enumerate(page.text.splitlines()):
            section_type = _match_section_heading(line)
            if section_type is not None:
                occurrences.append(
                    SectionOccurrence(
                        section_type=section_type,
                        source_heading=line.strip(),
                        page_number=page.page_number,
                        line_index=line_index,
                    )
                )
    return occurrences


def _section_presence(occurrences: Iterable[SectionOccurrence]) -> dict[str, bool]:
    found = {occurrence.section_type for occurrence in occurrences}
    return {section_type: section_type in found for section_type, _ in SECTION_ALIASES}


def _page_range_for_section(
    occurrence: SectionOccurrence,
    later_occurrences: list[SectionOccurrence],
    page_count: int,
) -> tuple[int, int]:
    later = [item for item in later_occurrences if item.page_number >= occurrence.page_number]
    if not later:
        return occurrence.page_number, page_count
    next_occurrence = later[0]
    end_page = max(occurrence.page_number, next_occurrence.page_number)
    return occurrence.page_number, end_page


def _build_section_locators(
    occurrences: list[SectionOccurrence], page_count: int
) -> list[dict[str, object]]:
    locators: list[dict[str, object]] = []
    for index, occurrence in enumerate(occurrences):
        start_page, end_page = _page_range_for_section(
            occurrence, occurrences[index + 1 :], page_count
        )
        locators.append(
            {
                "section_type": occurrence.section_type,
                "source_heading": occurrence.source_heading,
                "page_start": start_page,
                "page_end": end_page,
            }
        )
    return locators


def _publication_year(paper: ParsedPaper) -> int | None:
    identity_text = "\n".join(page.text for page in paper.pages[:2])
    years = [int(value) for value in YEAR_PATTERN.findall(identity_text)]
    plausible = [year for year in years if 1900 <= year <= 2100]
    return plausible[0] if plausible else None


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:80] or "paper"


def _review_id(paper: ParsedPaper) -> str:
    return f"{paper.content_hash[:12]}-{_slug(paper.title)[:48]}"


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _build_review_text(paper: ParsedPaper, relative_pdf_path: str) -> str:
    lines = [
        f"# {paper.title}",
        "",
        f"- Source PDF: `{relative_pdf_path}`",
        f"- DOI: `{paper.doi or 'not detected'}`",
        f"- Authors from PDF metadata: {', '.join(paper.authors) if paper.authors else 'not detected'}",
        f"- Pages: {paper.page_count}",
        f"- Words: {paper.word_count}",
        f"- SHA-256: `{paper.content_hash}`",
        "",
        "## Abstract detected by parser",
        "",
        paper.abstract or "No abstract was reliably detected.",
        "",
        "## Page text",
        "",
    ]
    for page in paper.pages:
        lines.extend(
            [
                f"### PDF page {page.page_number}",
                "",
                page.text or "[No extractable text on this page]",
                "",
            ]
        )
        if page.table_text:
            lines.extend(
                [
                    f"#### Detected table-region text, page {page.page_number}",
                    "",
                    page.table_text,
                    "",
                ]
            )
    return "\n".join(lines).rstrip() + "\n"


def _bundle_paper(pdf_path: Path, root: Path, parser: PyMuPDFParser) -> PaperBundle:
    paper = parser.parse(pdf_path)
    occurrences = _find_sections(paper)
    relative_pdf_path = _relative_path(pdf_path, root)
    review_id = _review_id(paper)
    metadata: dict[str, object] = {
        "review_id": review_id,
        "relative_pdf_path": relative_pdf_path,
        "sha256": paper.content_hash,
        "title": paper.title,
        "authors": paper.authors,
        "doi": paper.doi,
        "publication_year_candidate": _publication_year(paper),
        "page_count": paper.page_count,
        "word_count": paper.word_count,
        "abstract_detected": paper.abstract is not None,
        "section_presence": _section_presence(occurrences),
        "section_locators": _build_section_locators(occurrences, paper.page_count),
        "text_quality": {
            "has_extractable_text": bool(paper.raw_text.strip()),
            "low_text_warning": paper.word_count < 250,
            "ocr_performed": False,
        },
        "review_status": "mechanically_extracted_not_scientifically_reviewed",
    }
    return PaperBundle(
        review_id=review_id,
        relative_pdf_path=relative_pdf_path,
        metadata=metadata,
        review_text=_build_review_text(paper, relative_pdf_path),
    )


def _write_batch(output_root: Path, batch_number: int, bundles: list[PaperBundle]) -> None:
    batch_dir = output_root / f"batch_{batch_number:04d}"
    text_dir = batch_dir / "papers"
    text_dir.mkdir(parents=True, exist_ok=True)

    with (batch_dir / "papers.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for bundle in bundles:
            handle.write(json.dumps(bundle.metadata, ensure_ascii=False, sort_keys=True) + "\n")
            (text_dir / f"{bundle.review_id}.md").write_text(
                bundle.review_text, encoding="utf-8", newline="\n"
            )

    summary = {
        "batch_number": batch_number,
        "paper_count": len(bundles),
        "review_ids": [bundle.review_id for bundle in bundles],
        "status": "ready_for_scientific_review",
    }
    (batch_dir / "batch_manifest.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_review_queue(pdf_root: Path, output_root: Path, batch_size: int) -> dict[str, object]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    root = pdf_root.expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"PDF root does not exist or is not a directory: {root}")

    pdf_paths = sorted(
        (path for path in root.rglob("*.pdf") if path.is_file()),
        key=lambda path: path.as_posix().casefold(),
    )
    parser = PyMuPDFParser()
    successes: list[PaperBundle] = []
    failures: list[dict[str, str]] = []

    for pdf_path in pdf_paths:
        try:
            successes.append(_bundle_paper(pdf_path, root, parser))
        except (DocumentParseError, OSError, ValueError) as exc:
            failures.append(
                {
                    "relative_pdf_path": _relative_path(pdf_path, root),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    for batch_index, start in enumerate(range(0, len(successes), batch_size), start=1):
        _write_batch(output_root, batch_index, successes[start : start + batch_size])

    duplicate_hash_groups: dict[str, list[str]] = {}
    for bundle in successes:
        paths = duplicate_hash_groups.setdefault(str(bundle.metadata["sha256"]), [])
        paths.append(bundle.relative_pdf_path)
    duplicates = {
        sha256: paths for sha256, paths in duplicate_hash_groups.items() if len(paths) > 1
    }

    return {
        "schema_version": 1,
        "pdf_root": root.as_posix(),
        "pdf_count": len(pdf_paths),
        "parsed_count": len(successes),
        "failed_count": len(failures),
        "batch_size": batch_size,
        "batch_count": (len(successes) + batch_size - 1) // batch_size,
        "duplicate_content_groups": duplicates,
        "failures": failures,
        "review_boundary": (
            "Mechanical extraction only. No scientific result, Evidence Record, or review status "
            "is approved by this queue builder."
        ),
    }


def main() -> int:
    args = _parse_args()
    output_root = args.output.expanduser().resolve()
    if output_root.exists():
        if not args.overwrite:
            raise SystemExit(
                f"Output already exists: {output_root}. Use --overwrite to rebuild it."
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = build_review_queue(args.pdf_root, output_root, args.batch_size)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
