# PDF Corpus Scientific Review Workflow

## Purpose

This workflow supports systematic review of a large local corpus of scientific PDFs without requiring a person to open and inspect every paper manually before triage.

The repository already ignores `papers/*.pdf` and `papers/**/*.pdf`, so the PDF files are intentionally not committed to Git. The queue builder operates only on the filesystem where those ignored PDFs actually exist.

Important distinction:

- a Git-tracked repository is visible on GitHub;
- a gitignored PDF is **not stored on GitHub merely because it sits inside a repository working tree**;
- therefore the queue builder must be run in the clone, workstation, server, container, or restored corpus location that physically contains the PDFs.

## Command

From the repository root:

```powershell
poetry run python tools/build_pdf_review_queue.py `
  papers `
  --output work/pdf_review_queue `
  --batch-size 25
```

Or target one corpus:

```powershell
poetry run python tools/build_pdf_review_queue.py `
  papers/corpora/glp1_weight_loss `
  --output work/glp1_pdf_review_queue `
  --batch-size 25
```

Rebuild an existing queue with:

```powershell
poetry run python tools/build_pdf_review_queue.py `
  papers `
  --output work/pdf_review_queue `
  --batch-size 25 `
  --overwrite
```

`work/` is already ignored by Git, so generated review batches are not accidentally committed.

## What the queue builder does

For each PDF it deterministically records:

- relative PDF path;
- SHA-256 content hash;
- best-effort title;
- best-effort authors from PDF metadata;
- best-effort DOI;
- candidate publication year;
- page count;
- word count;
- abstract-detection status;
- likely presence of standard scientific sections;
- page-level section locators;
- low-text/scanned-document warning;
- page text;
- best-effort table-region text already exposed by the repository parser.

The expected section families are:

- abstract;
- introduction/background;
- methods/materials and methods;
- statistical methods/statistical analysis;
- results/findings;
- discussion;
- conclusions;
- limitations;
- references/bibliography.

Section detection is deliberately conservative and heading-based. It is triage metadata, not a claim that the detected boundaries are semantically perfect.

## Output

The output directory contains:

```text
work/pdf_review_queue/
    manifest.json
    batch_0001/
        batch_manifest.json
        papers.jsonl
        papers/
            <review-id>.md
            ...
    batch_0002/
    ...
```

### `manifest.json`

Corpus-level mechanical inventory:

- number of PDFs found;
- successfully parsed count;
- failed count and failure reasons;
- batch count;
- duplicate files detected by identical SHA-256 content;
- explicit scientific-review boundary.

### `papers.jsonl`

One compact machine-readable metadata record per paper in the batch.

### `papers/<review-id>.md`

Human/AI-reviewable source packet containing:

- paper identity metadata;
- parser-detected abstract;
- complete extracted page text with explicit PDF page headings;
- detected table-region text where available.

The Markdown packet exists so a reviewer can inspect the paper source without repeatedly opening the PDF for every first-pass review. The PDF remains authoritative whenever extraction is ambiguous.

## Scientific review stage

Mechanical extraction is **not scientific review**.

Every generated paper begins with:

`mechanically_extracted_not_scientifically_reviewed`

A later scientific reviewer should assess, when supported by the source:

- title;
- authors;
- publication date;
- journal;
- DOI/source identity;
- abstract;
- introduction/background;
- methods;
- statistical methods;
- results;
- discussion;
- conclusions;
- limitations;
- references;
- study design;
- population;
- intervention;
- comparator;
- outcomes;
- numerical estimates and uncertainty;
- adverse events;
- missing-data handling;
- analysis population/estimand;
- source page/table/figure locators;
- overlap or duplicate-study concerns;
- relationship to existing reviewed evidence;
- suitability for Evidence Record promotion;
- suitability for deterministic statistical verification.

The reviewer must not invent a section or field that the paper does not provide.

## Recommended review decisions

Each paper can eventually receive one bounded workflow disposition such as:

- `reviewed_evidence_candidate`
- `reviewed_contextual`
- `needs_deeper_review`
- `duplicate_or_overlapping_publication`
- `out_of_scope`
- `insufficient_source_text`
- `unreadable_or_scanned_requires_manual_handling`

These are workflow states, not Evidence Quality, Consensus, Claim Confidence, or scientific truth scores.

## Prioritization

For a large corpus, review in roughly this order unless a research question demands otherwise:

1. randomized controlled trials;
2. systematic reviews and meta-analyses;
3. comparative observational studies;
4. uncontrolled prospective or retrospective studies;
5. withdrawal/durability studies;
6. safety/adverse-event studies;
7. mechanistic or biomarker studies;
8. qualitative/contextual publications;
9. duplicates and out-of-scope material.

The purpose is to put the most decision-relevant evidence in front of the scientific reviewer first, not to imply lower-ranked designs are worthless.

## Trust boundaries

The queue builder does not:

- call an LLM;
- use the network;
- query SQLite;
- OCR image-only PDFs;
- promote Evidence Records;
- alter review status;
- infer missing statistical values;
- synthesize scientific conclusions;
- pool studies;
- rank treatments;
- calculate Evidence Quality, Consensus, or Claim Confidence;
- determine scientific truth.

Image-only or poorly extractable PDFs are flagged for separate handling rather than silently treated as empty evidence.

## Relationship to future Paper Records

The queue is intentionally shaped to support the future first-class Paper Record layer.

The long-term flow is:

```text
PDF
  -> deterministic mechanical extraction
  -> scientific review batch
  -> reviewed Paper Record
  -> zero or more bounded Evidence Records
  -> optional deterministic Statistical Verification
  -> later synthesis layers
```

Paper-level review and Evidence Record promotion remain distinct operations. Reviewing one result from a publication must not silently authorize every other result in that publication.
