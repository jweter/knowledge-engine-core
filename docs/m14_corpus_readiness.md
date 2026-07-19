# M14 Corpus Readiness Reconciliation

This offline gate proves that the curated manifest, approved acquisition receipts, and local PDFs agree before the controlled 500-paper import begins.

## Command

```bash
python -m knowledge_engine.corpus_readiness_cli validate \
  --manifest data/corpora/glp1_weight_loss/sources.csv \
  --receipt work/m14/acquisition-000.json \
  --receipt work/m14/acquisition-001.json \
  --papers-dir papers/corpora/glp1_weight_loss \
  --expected-count 500 \
  --output work/m14/corpus-readiness.json
```

Repeat `--receipt` for every acquisition batch.

## Required manifest evidence

Every accepted row must contain:

- a unique `source_id`;
- a unique PMID;
- a unique PMCID in `other_identifier`;
- a safe PDF filename in `local_path`;
- an explicit `license_type`;
- `usage_status` equal to `approved_open_access` or `public_domain`;
- `inclusion_status` equal to `included`.

## Exact reconciliation

The validator requires:

1. exactly the requested number of accepted manifest rows;
2. exactly the same number of unique acquisition receipt items;
3. an exact PMID and PMCID match for every row;
4. matching local filenames;
5. matching byte counts and SHA-256 values;
6. no missing, extra, absolute, traversing, or symbolic-link paths;
7. no unexpected PDF files in the corpus directory.

Any mismatch fails the gate. The command performs no network access and does not modify the manifest or PDFs.

## Output

The readiness report contains only sanitized identifiers, filenames, byte counts, hashes, the manifest hash, and reconciled counts. It contains no usernames, home directories, or private absolute paths.

## Repository boundaries

- Do not commit PDFs, acquisition receipts, readiness reports, databases, or extracted full text.
- Do not infer a license or legal approval from file availability.
- Do not proceed to the fresh M14 import unless the report has `ready: true` and all counts equal 500.

## Remaining M14 work

After readiness passes:

1. preserve the exact manifest and readiness-report hashes;
2. record the external database size before import;
3. execute the fresh 500-paper import;
4. reconcile every source to one terminal outcome;
5. execute the linked resume against the unchanged manifest;
6. verify paper, text, FTS, and lineage idempotency;
7. produce the sanitized evidence report;
8. record `PROCEED`, `HOLD`, or `STOPPED`.
