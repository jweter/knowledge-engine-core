# M10 Duplicate Detection and Resumability Operational Contract

## Purpose

M10 makes local corpus reruns safe without weakening provenance or silently collapsing distinct sources. It extends the trusted Source Vault foundation with explicit duplicate outcomes and immutable resume/retry lineage.

This document describes the implemented behavior, the remaining command-line contract, and the final merge checklist for Issue #7 and draft PR #11.

## Trust Boundaries

M10 does not:

- download documents or follow source URLs;
- perform fuzzy title matching or automatic merge decisions;
- replace or supersede existing papers automatically;
- infer that a DOI alone proves two files are identical;
- mutate prior import runs or prior import items;
- treat database uniqueness errors as the primary duplicate policy.

Uncertain identity remains visible and requires human review.

## Duplicate Evidence Hierarchy

Evidence is evaluated before paper, paper-text, or FTS persistence.

1. Exact SHA-256 content hash.
2. Normalized DOI with reconcilable hash evidence.
3. Normalized DOI with conflicting or insufficient hash evidence.
4. Normalized title and publication year as advisory evidence only.

Stronger evidence dominates weaker evidence.

### Exact hash

An existing paper or earlier item with the same content hash is a safe duplicate skip. The import item records the matched identity and structured evidence. No new paper, paper-text, or FTS row is written.

### DOI with the same hash

A normalized DOI match with matching content hash is a safe duplicate skip.

### DOI conflict or insufficient hash evidence

A normalized DOI match with a different hash, or without enough hash evidence to establish equivalence, is `needs_review`. No paper, paper-text, or FTS row is written.

### Title and year

A normalized title/publication-year match is advisory only. It must never automatically merge or discard a source. The candidate is held for review.

## Persisted Audit Fields

Each import item can record:

- `duplicate_outcome`;
- `matched_paper_id`;
- `matched_import_item_id`;
- `computed_content_hash`;
- deterministic structured duplicate evidence;
- `retry_of_import_item_id`.

Evidence JSON must remain deterministic, sanitized, and free of internal exception text.

## Same-Run Duplicates

When a later item duplicates an earlier item in the same run, same-run lineage is retained even when the earlier item has already created a paper. The later item can therefore record both:

- the earlier `import_item_id`;
- the matched `paper_id`.

This preserves the causal history of the run instead of reducing the event to a generic database match.

## Fresh Reruns

A fresh rerun creates a new immutable import run. Existing papers are detected before persistence, so rerunning the same manifest does not duplicate paper, paper-text, or FTS records.

Fresh reruns do not reuse prior item outcomes as execution instructions. They evaluate the current manifest and current database identity again.

## Immutable Linked Runs

Resume and retry operations create a new run with:

- `run_mode` set to `resume` or `retry_failed`;
- `parent_import_run_id` pointing to the selected prior run;
- a new manifest snapshot;
- new import-item identities.

The parent run and every parent item remain unchanged.

Linked operations require the current corpus and parent run to have the same `corpus_id`. A mismatch fails closed and the attempted linked run is rolled back.

## Stable Source Reconciliation

Resume/retry planning reconciles rows by stable `source_id`, never by CSV row number or list position.

Planning fails closed when current or prior rows have:

- a missing stable `source_id`;
- duplicate `source_id` values within the same run.

Manifest reordering therefore does not alter lineage decisions.

## Resume Policy

A resume plan:

- skips a prior successful import;
- skips a prior safe exact duplicate;
- does not automatically retry a prior failed item;
- processes a new source;
- processes an unresolved prior item, subject to current validation and duplicate checks.

A failed prior item is marked with the reason `failed_requires_explicit_retry` and requires the explicit retry mode.

## Retry-Failed Policy

A retry-failed plan:

- processes only current rows whose matching parent item failed;
- records `retry_of_import_item_id` for the selected prior failure;
- skips parent successes, safe duplicates, unresolved items, and new sources.

This prevents a targeted retry from becoming an accidental broad reimport.

## Required Ingestion Guard

Linked-run planning assigns skipped items before document parsing. The ingestion eligibility gate must therefore require:

```python
item.item_status == "valid"
```

in addition to manifest, licensing, and path checks. Without this guard, a planner-skipped item could still be parsed because its original manifest metadata remains importable.

## Command-Line Contract

`corpus-import` will expose mutually exclusive options:

```text
--resume-from <import-run-id>
--retry-failed-from <import-run-id>
```

Providing both options is an error. Supplying neither creates a fresh run.

CLI output must display:

- new import-run ID;
- run mode;
- parent run ID when linked;
- imported, skipped, failed, and needs-review counts;
- deterministic duplicate outcome and matched identity where safe;
- the no-download/no-URL-following boundary;
- the requirement for scientific and human review.

Summaries must be derived from persisted item outcomes rather than transient counters alone.

## Final M10 Acceptance Checklist

Before PR #11 can be marked ready and merged:

- [x] additive M10 schema and ORM mappings;
- [x] fail-closed schema verification and migration regression coverage;
- [x] deterministic duplicate query layer;
- [x] pure duplicate-decision hierarchy;
- [x] pre-persistence resolution with no-write review behavior;
- [x] same-run duplicate lineage;
- [x] fresh-rerun paper/text/FTS integrity coverage;
- [x] pure resume/retry planner by stable `source_id`;
- [x] immutable linked-run creation and parent-history tests;
- [ ] linked-run execution wired into corpus ingestion;
- [ ] title/year advisory resolution from authoritative publication-year evidence;
- [ ] mutually exclusive CLI resume/retry options;
- [ ] deterministic persisted-outcome reporting;
- [ ] release notes and final architectural review;
- [ ] final Black, Ruff, strict mypy, pytest, and `git diff --check` gate;
- [ ] final diff audit for generated files, databases, local PDFs, caches, secrets, and unrelated changes.

## Operational Principle

A rerun is not an edit to history. It is a new, traceable attempt whose decisions are derived from current evidence and linked to prior outcomes without overwriting them.
