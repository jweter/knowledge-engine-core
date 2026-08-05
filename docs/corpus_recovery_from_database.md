# Corpus recovery from an existing database

## Purpose

Recover gitignored corpus PDFs that were previously ingested but are no longer present on the current machine.

The recovered SQLite database is the inventory. The recovery process does **not** insert papers into the database, infer new evidence, or treat reacquisition as scientific review.

## Current recovered corpus

The August 4 database backup contains 150 rows in `papers`, including the historical DOI, source path, content SHA-256, page count, and word count. The database also contains `paper_texts` and `paper_pages`.

This 150-paper backup is the currently recovered corpus inventory. Do not describe it as the previously remembered ~1,000-paper corpus unless a newer database or snapshot is found.

## Recovery policy

For each database paper:

1. Derive the historical filename from `papers.source_path`.
2. If that file exists locally and its SHA-256 matches `papers.content_hash`, skip it as `already_present_verified`.
3. If the local path exists but the hash differs, do not overwrite it by default.
4. Resolve the stored DOI through Europe PMC metadata.
5. When the exact DOI is in PMC and PMC Article Datasets Cloud marks it open access, use the official PMC OA PDF.
6. Otherwise accept only a PDF explicitly marked OA and hosted by Europe PMC itself.
7. Reject unresolved, non-OA, third-party-host-only, non-PDF, over-size, or identity-ambiguous results.
8. Download to a temporary file and atomically move it into the ignored corpus directory.
9. Compute the new SHA-256 and compare it with the historical hash.
10. Append a JSONL receipt for every processed paper.

A freshly acquired official OA PDF is not required to be byte-identical to the historical copy. Providers can replace or regenerate PDFs. When the bytes differ, the tool records `reacquired_hash_changed`; those files require later parser/source-identity review before being treated as equivalent to the historical artifact.

## Windows quick start

From the repository root, on branch `agent/pdf-corpus-review-queue`:

```powershell
# Five-paper source-resolution pilot. No PDF bytes are downloaded.
.\scripts\reacquire_corpus_pdfs.ps1 -Limit 5 -DryRun
```

If the pilot resolves as expected:

```powershell
# Reacquire the first five selected papers.
.\scripts\reacquire_corpus_pdfs.ps1 -Limit 5
```

Then run the full inventory:

```powershell
.\scripts\reacquire_corpus_pdfs.ps1
```

Defaults:

- database: `work\corpus-recovery\knowledge-engine.sqlite`
- target: `papers\corpora\glp1_weight_loss`
- receipts: `work\corpus-recovery\reacquisition_receipts.jsonl`

The Python tool uses only the standard library, so it does not require `poetry install`.

## Existing hash mismatch

The default is fail-closed:

```text
existing_hash_mismatch
```

Review the existing file first. If replacement is intentional:

```powershell
.\scripts\reacquire_corpus_pdfs.ps1 -ReplaceMismatch
```

The existing file is renamed to a quarantine-style filename containing its current hash before a replacement is attempted.

## Useful controls

```powershell
# Resume from a database paper ID.
.\scripts\reacquire_corpus_pdfs.ps1 -StartId 75

# Process 25 rows starting at paper 75.
.\scripts\reacquire_corpus_pdfs.ps1 -StartId 75 -Limit 25

# Resolve only, no downloads.
.\scripts\reacquire_corpus_pdfs.ps1 -StartId 75 -Limit 25 -DryRun
```

## Receipt statuses

Expected statuses include:

- `already_present_verified`
- `existing_hash_mismatch`
- `dry_run_resolved`
- `reacquired_verified`
- `reacquired_hash_changed`
- `unresolved_no_doi`
- `open_access_source_unresolved`
- `resolution_failed`
- `download_failed`
- `commit_failed`
- `blocked_existing_path`

The receipt log is append-only. Local-file/hash state remains the source of truth on the next run, so interrupted runs are naturally resumable.

## Review pipeline after recovery

```text
recovered database inventory
        -> legally reacquired PDFs
        -> PDF review queue builder
        -> mechanical paper packets
        -> scientific review
        -> Paper Record / Evidence candidate / statistical candidate decisions
```

The database's stored `paper_pages` and `paper_texts` can support corpus-wide triage before every source PDF is recovered, but final source-fidelity review of important numerical claims should use the recovered source PDF whenever possible.

## Boundaries

The recovery tool does not:

- mutate SQLite;
- download non-OA or paywalled content;
- scrape arbitrary publisher sites;
- follow third-party repository URLs;
- bypass access controls;
- run OCR;
- create or approve Evidence Records;
- change review status;
- perform statistical synthesis;
- claim a changed provider PDF is historically byte-identical.

After recovery, `tools/build_pdf_review_queue.py` is the next stage for deterministic extraction and scientific-review batching.
