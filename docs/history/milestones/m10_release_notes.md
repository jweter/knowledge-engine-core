# M10 Duplicate Detection and Resumability Release Notes

## Status

M10 is implemented on pull request #11. Persisted CLI reporting, the schema-v3 execution/review-status split, immutable linked ingestion, and the read-only Quality gate are included in the reviewed branch head.

## Added

- deterministic duplicate decisions before paper, paper-text, author, keyword, or FTS persistence;
- exact content-hash duplicate detection;
- normalized DOI duplicate and DOI/hash conflict handling;
- advisory title/publication-year matching from immutable manifest snapshots;
- explicit `skipped` and `needs_review` item outcomes;
- separate run execution status and review status domains;
- item-level duplicate evidence, matched paper identity, and matched import-item lineage;
- same-run duplicate detection;
- immutable fresh reruns;
- pure resume and retry-failed planning by stable `source_id`;
- immutable linked-run creation through `parent_import_run_id` and `run_mode`;
- linked corpus ingestion that parses only planner-selected `valid` items;
- CLI options `--resume-from` and `--retry-failed-from`;
- persisted CLI reporting for run mode, parent run, outcome counts, duplicate identity, and retry lineage;
- a parameterized run-status truth table covering success, failure, and partial success independently from review status.

## Tooling

- Ruff is the sole formatter and linter.
- CI runs `ruff format --check`, `ruff check`, strict mypy, pytest, and `git diff --check`.
- CI is read-only and rejects temporary review-status delivery artifacts.
- Black is no longer a project dependency or configuration source.

## Safety behavior

- `needs_review` creates no paper, paper-text, or FTS rows.
- Missing or contradictory identity evidence never causes an automatic merge.
- Title/year evidence is advisory only and always requires review.
- Resume and retry operations create new runs; parent runs and items remain unchanged.
- Retry-failed processes only failed parent items.
- Source reconciliation uses stable `source_id`, never CSV row order.
- No URLs are followed and no documents are downloaded.
- Database uniqueness constraints remain integrity backstops rather than the primary duplicate-decision mechanism.
- Internal exceptions are converted to deterministic, sanitized persisted issue messages.

## CLI examples

Fresh import:

```text
knowledge-engine corpus-import corpus.json
```

Resume from an earlier run:

```text
knowledge-engine corpus-import corpus.json --resume-from <run-id>
```

Retry only failed items from an earlier run:

```text
knowledge-engine corpus-import corpus.json --retry-failed-from <run-id>
```

The two parent-run options are mutually exclusive.

## Compatibility

- Existing schema-version-1 and schema-version-2 databases are upgraded additively to schema version 3.
- Existing M8 and M9 records are preserved and backfilled into the separated status domains.
- Fresh corpus import behavior remains available through the existing command and service.

## Verification

PR #11 is eligible to merge only when the final committed head passes Ruff formatting, Ruff linting, strict mypy, the complete pytest suite, diff hygiene, temporary-artifact rejection, and the final architecture/security review.
