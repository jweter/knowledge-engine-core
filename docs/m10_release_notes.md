# M10 Duplicate Detection and Resumability Release Notes

## Status

M10 is implemented on draft pull request #11 and remains unmerged until the final acceptance checklist is complete.

## Added

- deterministic duplicate decisions before paper, paper-text, author, keyword, or FTS persistence;
- exact content-hash duplicate detection;
- normalized DOI duplicate and DOI/hash conflict handling;
- explicit `skipped` and `needs_review` outcomes;
- item-level duplicate evidence, matched paper identity, and matched import-item lineage;
- same-run duplicate detection;
- immutable fresh reruns;
- pure resume and retry-failed planning by stable `source_id`;
- immutable linked-run creation through `parent_import_run_id` and `run_mode`;
- linked corpus ingestion that parses only planner-selected `valid` items;
- CLI options `--resume-from` and `--retry-failed-from`;
- separate imported, failed, skipped, and needs-review counts.

## Safety behavior

- `needs_review` creates no paper, paper-text, or FTS rows.
- Missing or contradictory identity evidence never causes an automatic merge.
- Resume and retry operations create new runs; parent runs and items remain unchanged.
- Retry-failed processes only failed parent items.
- Source reconciliation uses stable `source_id`, never CSV row order.
- No URLs are followed and no documents are downloaded.
- Database uniqueness constraints remain integrity backstops rather than the primary duplicate-decision mechanism.

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

- Existing schema-version-1 databases are upgraded additively to schema version 2.
- Existing M8 and M9 records are preserved.
- Fresh corpus import behavior remains available through the existing command and service.

## Remaining acceptance work

Before PR #11 is marked ready and merged:

1. Complete title/year advisory matching from the authoritative persisted manifest snapshot.
2. Confirm deterministic CLI reporting for run mode, parent run, matched identity, and needs-review summaries.
3. Complete the final architectural and security-oriented diff review.
4. Run the full Quality gate on the final non-bot branch head.
5. Confirm the PR contains no temporary workflows, local databases, PDFs, generated artifacts, caches, secrets, or unrelated changes.
