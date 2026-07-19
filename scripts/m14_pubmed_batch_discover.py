#!/usr/bin/env python3
"""Run a bounded multi-page PubMed/PMC candidate discovery intake."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import cast

from knowledge_engine.ncbi_http import UrllibNcbiTransport
from knowledge_engine.pubmed_batch_discovery import discover_candidate_batch
from knowledge_engine.pubmed_discovery import GetTransport, NcbiDiscoveryError, PubmedPmcDiscoveryService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and deduplicate a large review-only PubMed/PMC candidate intake. "
            "No PDFs are downloaded and no manifest rows are promoted."
        )
    )
    parser.add_argument("--query", required=True, help="PubMed search expression.")
    parser.add_argument("--limit", required=True, type=int, help="Requested unique candidate count.")
    parser.add_argument("--retstart", type=int, default=0, help="Initial PubMed result offset.")
    parser.add_argument("--page-size", type=int, default=100, help="Bounded page size, maximum 100.")
    parser.add_argument("--output", required=True, type=Path, help="Review-only JSON output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser


def _validate_output(path: Path, *, force: bool) -> None:
    if path.is_symlink():
        raise ValueError("Output must not be a symbolic link.")
    if path.exists() and not force:
        raise ValueError("Output file already exists. Use --force to overwrite.")


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, path)
    except OSError as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise ValueError("Output file could not be written.") from exc


def main() -> int:
    args = _parser().parse_args()
    try:
        _validate_output(args.output, force=args.force)
        service = PubmedPmcDiscoveryService(cast(GetTransport, UrllibNcbiTransport()))
        result = discover_candidate_batch(
            service,
            args.query,
            total_limit=args.limit,
            retstart=args.retstart,
            page_size=args.page_size,
        )
        _write_atomic(args.output, result.to_json())
    except (ValueError, NcbiDiscoveryError) as exc:
        print(f"M14 batch discovery failed: {exc}")
        return 1

    verified = sum(candidate.open_access for candidate in result.candidates)
    print(
        f"Wrote {len(result.candidates)} unique candidates across "
        f"{result.fetched_page_count} page(s); {verified} PMC OA verified; "
        f"{result.duplicate_pmids_removed} duplicate PMID(s) removed."
    )
    print("Review required; no PDFs were downloaded and no manifest rows were promoted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
