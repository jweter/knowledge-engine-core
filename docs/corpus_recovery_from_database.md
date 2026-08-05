# Corpus Recovery from Database Inventory

## Status

Pre-download recovery workflow for the gitignored scientific PDF corpus.

## Why this exists

The repository intentionally does not track corpus PDFs. A recovered Knowledge Engine SQLite database can still preserve the paper inventory, source filename, DOI, expected SHA-256, page count, word count, and stored text/pages.

The recovery process therefore starts from the database inventory instead of blindly re-searching the web.

## Current recovered database observation

The recovered full database backup inspected on 2026-08-04 contains 150 rows in `papers` and includes `paper_pages`, `paper_texts`, authors, journals, keywords, graph tables, and import/extraction history.

The first recovered records include the Gao semaglutide meta-analysis, STEP 5, SELECT, and PMC-sourced papers. This confirms the database contains real corpus identity and extraction metadata, even though the original PDF files are not present on the current laptop.

This 150-paper backup is the currently recovered corpus inventory. Do not describe it as the previously remembered ~1,000-paper corpus unless a newer database/snapshot is found.

## Phase A: build a deterministic recovery manifest

Run:

```powershell
python tools/build_corpus_recovery_manifest.py `
  --database "work\corpus-recovery\knowledge-engine.sqlite" `
  --target-dir "papers\corpora\glp1_weight_loss" `
  --output "work\corpus-recovery\recovery_manifest.jsonl"
```

The builder is standard-library only and does not require Poetry dependencies.

For every `papers` row it records:

- paper ID
- title
- DOI
- PMCID when safely recoverable from an existing `PMC########.pdf` source filename
- original source path
- expected filename
- expected SHA-256
- page/word counts
- target local path
- whether the file is already present
- duplicate-content-hash flag
- proposed recovery route
- recovery status
- review status

It also emits `recovery_manifest.summary.json`.

## Recovery routes

### `pmc_open_access_candidate`

The historical filename is an explicit PMCID PDF filename such as `PMC13313273.pdf`.

This is the strongest deterministic re-acquisition route. A later downloader should reuse the repository's existing PMC/Europe PMC acquisition boundary and open-access/license checks rather than constructing an unrestricted URL scraper.

### `doi_open_access_resolution_required`

The paper has a DOI but no explicit PMCID in the historical filename.

A later recovery stage must resolve a legally usable open-access source. DOI presence alone does not authorize downloading or redistribution.

### `manual_source_resolution_required`

Neither an explicit PMCID filename nor DOI is available.

Do not guess a source.

## Phase B: re-acquire in bounded batches

Do not attempt all records in one opaque run.

Recommended batch size: 20–25 papers.

For each pending record:

1. resolve an allowed source;
2. verify legal/open-access eligibility under existing acquisition rules;
3. download to a temporary path;
4. verify PDF structure;
5. parse source identity where possible;
6. compare the downloaded SHA-256 against the historical expected hash;
7. record whether the content is an exact historical match or a source-equivalent replacement;
8. move verified content to the ignored corpus target directory;
9. persist status before proceeding.

A changed publisher copy with a different SHA-256 is not automatically invalid, but it must not be silently called an exact restoration.

## Suggested recovery statuses

- `pending`
- `already_present`
- `downloaded_exact_hash`
- `downloaded_source_equivalent_hash_changed`
- `source_identity_mismatch`
- `not_open_access`
- `source_unresolved`
- `download_failed_retryable`
- `invalid_pdf`
- `duplicate_content`
- `needs_manual_source_resolution`

## Review pipeline after recovery

Recovered PDFs feed the separate PDF review-queue builder:

```text
recovered database inventory
        -> recovery manifest
        -> 20–25 legally reacquired PDFs
        -> PDF review queue builder
        -> mechanical paper packets
        -> scientific review
        -> Paper Record / Evidence candidate / statistical candidate decisions
```

Mechanical extraction never changes a paper to scientifically reviewed.

## Stored database text is useful before PDF recovery

The recovered database contains `paper_pages` and `paper_texts`. These can support corpus-wide triage and prioritization before every original PDF is restored.

However, final source-fidelity review of important numerical claims should use the reacquired source PDF when possible, especially for:

- tables
- figures
- footnotes
- denominators
- analysis populations
- missing-data methods
- statistical model details
- exact page/table/figure locators

## Trust boundaries

Do not:

- bypass paywalls;
- treat DOI resolution as proof of reusable licensing;
- infer missing numerical values;
- call a changed-hash download an exact restoration;
- overwrite database Evidence Records during recovery;
- mark papers scientifically reviewed from mechanical extraction alone;
- pool or synthesize studies as part of corpus recovery.

## Next implementation step

Add a resumable bounded downloader that consumes `recovery_manifest.jsonl` and reuses the existing PMC/Europe PMC acquisition and license-validation seams.

Before doing so, inspect the manifest route counts so implementation targets the dominant real acquisition route rather than guessing.
