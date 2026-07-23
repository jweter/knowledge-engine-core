"""Backfill missing `paper_pages` rows for papers imported before M15.

A paper imported before M15's migration has zero `PaperPage` rows and
cannot be extracted by `ke extraction-review-generate` at all. A genuine
backfill is possible -- re-parse the paper's original local PDF, since
`PyMuPDFParser`'s per-page normalization is deterministic -- but only as
long as that PDF file is still present, since local PDFs are treated as
ephemeral working files throughout this project, not permanent storage.

Before trusting a re-parse, the freshly computed `content_hash` must match
the `Paper` row's already-persisted `content_hash`: the file at
`source_path` today is not guaranteed to be the same file that was
originally imported, so a mismatch is reported, never silently backfilled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from knowledge_engine.models import Paper
from knowledge_engine.parser import DocumentParseError, DocumentParser, ParsedPaper

PAPER_PAGES_BACKFILL_RULES_VERSION = "m22-paper-pages-backfill-v1"

_STATUS_BACKFILLED = "backfilled"
_STATUS_MISSING_SOURCE_FILE = "missing_source_file"
_STATUS_HASH_MISMATCH = "hash_mismatch"
_STATUS_PARSE_FAILED = "parse_failed"


@dataclass(frozen=True)
class BackfillOutcome:
    """The result of attempting to backfill one paper's pages."""

    paper_id: int
    title: str
    status: str
    detail: str | None = None


def decide_backfill(paper: Paper, parsed: ParsedPaper) -> BackfillOutcome:
    """Pure decision: is a fresh parse trustworthy enough to persist?

    The sole correctness gate is content-hash equality -- this function
    never inspects page content itself, since a matching hash already
    proves the re-parse is byte-for-byte the same source PyMuPDFParser
    normalized at import time.
    """

    if parsed.content_hash != paper.content_hash:
        return BackfillOutcome(
            paper_id=paper.id,
            title=paper.title,
            status=_STATUS_HASH_MISMATCH,
            detail=(
                f"Re-parsed content hash {parsed.content_hash} does not match "
                f"the persisted hash {paper.content_hash}; the file at "
                f"{paper.source_path} may have changed since import."
            ),
        )
    return BackfillOutcome(paper_id=paper.id, title=paper.title, status=_STATUS_BACKFILLED)


def backfill_paper(
    paper: Paper, parser: DocumentParser
) -> tuple[BackfillOutcome, ParsedPaper | None]:
    """Attempt to re-parse one paper's source file for backfill.

    Returns the outcome and, only when its status is "backfilled", the
    parsed result whose `.pages` the caller should persist. A missing
    source file or parse failure is reported per-paper, never raised, so a
    batch run can continue past any one paper's failure.
    """

    source_path = Path(paper.source_path)
    if not source_path.exists():
        return (
            BackfillOutcome(
                paper_id=paper.id,
                title=paper.title,
                status=_STATUS_MISSING_SOURCE_FILE,
                detail=f"Source file not found: {paper.source_path}",
            ),
            None,
        )

    try:
        parsed = parser.parse(source_path)
    except (DocumentParseError, OSError) as exc:
        return (
            BackfillOutcome(
                paper_id=paper.id,
                title=paper.title,
                status=_STATUS_PARSE_FAILED,
                detail=str(exc),
            ),
            None,
        )

    outcome = decide_backfill(paper, parsed)
    if outcome.status != _STATUS_BACKFILLED:
        return outcome, None
    return outcome, parsed
