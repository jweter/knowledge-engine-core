"""Deterministically detect whether a downloaded PDF's own printed article-type
label marks it as a commentary/editorial/letter/correction rather than
primary or synthesized research -- a class of false positive that title-only
screening (`discovery_scope_prescreen.py`,
`knowledge_engine.scientific_scope`'s `_NON_PRIMARY_TITLE_PREFIXES`) cannot
catch, because the signal often does not exist in the title at all.

Real near-miss this session: "PACIFIC-5 Trial: Refining Patient Selection
for Consolidation Durvalumab in Unresectable Stage III NSCLC" reads exactly
like a primary trial report -- no title-level marker of any kind. Only the
downloaded PDF's own first page carries the signal: journals print a short,
standalone, ALL-CAPS article-type label near the top of page 1 (here,
literally the line "COMMENTARY"), a printed fact about the document, not an
inference this tool has to make. This tool checks for that exact,
already-published label instead of guessing content type from prose.

This only runs on an already-acquired PDF -- it is a later pipeline stage
than scope-prescreen (title-only, pre-download) and complements rather than
replaces it. A match here is still a proposal, not an automated
rejection: the same human/AI judgment this project has always required
before citing a source as evidence still applies -- see
`discovery_scope_prescreen.py`'s docstring for the identical framing.

Example:
    poetry run python tools/detect_non_primary_article.py \\
        --evidence data/corpora/oncology_nsclc_checkpoint_inhibitors/evidence_records.jsonl \\
        --review-status reviewed
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import fitz

Verdict = Literal["primary_or_unknown", "non_primary_article_type"]

# Exact-line labels journals print as a standalone article-type marker near
# the top of page 1. Deliberately excludes ambiguous types that sometimes
# carry real primary data under an unusual label (e.g. "Research Letter,"
# used by several journals for short original-research reports) -- only
# types that are never primary or synthesized research belong here.
_NON_PRIMARY_ARTICLE_TYPE_LABELS = frozenset(
    {
        "commentary",
        "invited commentary",
        "editorial",
        "editorial comment",
        "letter",
        "letter to the editor",
        "correspondence",
        "perspective",
        "viewpoint",
        "news",
        "erratum",
        "retraction",
        "correction",
    }
)

# A recognizable body-text opening convention for correspondence/letters,
# checked separately from the exact-line label scan since it appears as a
# paragraph opener, not a standalone line.
_CORRESPONDENCE_OPENING_PATTERN = re.compile(r"^(to the editor|dear editor)[,:]?\s*$")

_MAX_HEADER_LINES = 15
"""Only the first N lines of page 1 are checked for a standalone label --
deep in the body, these words can legitimately appear in a citation,
reference list entry, or discussion of a cited correspondence, which is not
evidence about *this* document's own type."""


@dataclass(frozen=True)
class ArticleTypeCheckResult:
    pdf_path: str
    verdict: Verdict
    matched_label: str | None
    matched_line: str | None

    def to_json(self) -> dict[str, object]:
        return {
            "pdf_path": self.pdf_path,
            "verdict": self.verdict,
            "matched_label": self.matched_label,
            "matched_line": self.matched_line,
        }


def detect_non_primary_article_type(pdf_path: Path) -> ArticleTypeCheckResult:
    """Check one local PDF's own first page for a printed non-primary
    article-type label.

    Never guesses from prose content or title wording -- only matches an
    exact, standalone line the PDF itself already prints, or the
    "To the Editor,"/"Dear Editor," body-text opening convention. A PDF
    that cannot be opened or has no extractable page-1 text returns
    `primary_or_unknown`, never a false claim of a match.
    """

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return ArticleTypeCheckResult(str(pdf_path), "primary_or_unknown", None, None)

    if doc.page_count == 0:
        return ArticleTypeCheckResult(str(pdf_path), "primary_or_unknown", None, None)

    page_text = doc[0].get_text()
    lines = page_text.splitlines()

    for line in lines[:_MAX_HEADER_LINES]:
        normalized = " ".join(line.strip().casefold().split())
        if normalized in _NON_PRIMARY_ARTICLE_TYPE_LABELS:
            return ArticleTypeCheckResult(
                str(pdf_path), "non_primary_article_type", normalized, line.strip()
            )

    for line in lines:
        normalized = " ".join(line.strip().casefold().split())
        if _CORRESPONDENCE_OPENING_PATTERN.match(normalized):
            return ArticleTypeCheckResult(
                str(pdf_path),
                "non_primary_article_type",
                "correspondence_opening",
                line.strip(),
            )

    return ArticleTypeCheckResult(str(pdf_path), "primary_or_unknown", None, None)


def _iter_evidence_pdf_paths(
    evidence_path: Path, *, review_status: str | None
) -> list[tuple[str, Path]]:
    """Yield (evidence_record_id, local_pdf_path) for each evidence record's
    source_span, deduplicated by path, filtered to review_status when given."""

    seen: dict[str, str] = {}
    for line in evidence_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        if review_status is not None and record.get("review_status") != review_status:
            continue
        source_span = record.get("source_span") or {}
        local_pdf_path = source_span.get("local_pdf_path")
        if not local_pdf_path:
            continue
        seen.setdefault(local_pdf_path, record.get("evidence_record_id", "?"))

    return [(evidence_record_id, Path(path)) for path, evidence_record_id in seen.items()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True, help="Evidence records JSONL file")
    parser.add_argument(
        "--review-status",
        default=None,
        help="Only check records with this review_status (e.g. 'reviewed'). "
        "Omit to check every record's PDF.",
    )
    args = parser.parse_args()

    pairs = _iter_evidence_pdf_paths(args.evidence, review_status=args.review_status)
    if not pairs:
        print("No evidence records with a source_span.local_pdf_path found.")
        return 0

    flagged: list[tuple[str, ArticleTypeCheckResult]] = []
    checked = 0
    for evidence_record_id, pdf_path in pairs:
        resolved = pdf_path if pdf_path.is_absolute() else Path.cwd() / pdf_path
        result = detect_non_primary_article_type(resolved)
        checked += 1
        if result.verdict == "non_primary_article_type":
            flagged.append((evidence_record_id, result))

    print(f"Checked {checked} distinct source PDF(s).")
    if not flagged:
        print("No non-primary article-type labels found.")
        return 0

    print(f"{len(flagged)} PDF(s) flagged -- review before treating as primary evidence:")
    for evidence_record_id, result in flagged:
        print(f"  {evidence_record_id}: {result.matched_label!r} ({result.pdf_path})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
