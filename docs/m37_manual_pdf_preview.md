# M37 Manual PDF Preview and Manifest Draft

## Purpose

`ke import`/`ke corpus-import` have always accepted any local PDF -- no
door was ever closed there. What was missing was a way to add one without
hand-typing a `sources.csv` row's worth of metadata (title, authors, DOI,
license) for it. This milestone closes that gap using infrastructure that
already existed: `PyMuPDFParser` (the same parser `ke import` itself uses)
already extracts title/authors/abstract/DOI/page-count/word-count
deterministically from a PDF's own bytes, and M36's Unpaywall lookup
already resolves a DOI's OA status and license. `ke manual-pdf-preview`
wires those together into one small reviewable JSON file; `ke
manual-pdf-manifest-draft` turns an approved preview into one
manifest-ready CSV row -- so a human reviews and approves, rather than
typing.

## Two-step, review-first shape

Mirrors the discovery-then-adjudication pattern used everywhere else in
this project (M14, M34, M35), scaled down to one PDF at a time:

1. `ke manual-pdf-preview` parses the PDF locally and reports evidence.
   Never writes to the corpus manifest or database.
2. `ke manual-pdf-manifest-draft` refuses to produce a row unless the
   preview's `license_rule_result` is exactly `"passed"` -- the same bar
   every automated pipeline's adjudication engine already enforces, never
   guessed. It never touches `sources.csv` directly either, matching
   `manifest_curation_cli.py`'s existing "export a draft, don't modify the
   manifest" contract for the automated pipelines. Running this command
   against a preview you have reviewed and accepted is itself the
   approval act -- there is no separate approvals file for a single PDF
   the way a batch of dozens of automated candidates needs one.

## Commands

```bash
ke manual-pdf-preview --pdf paper.pdf --output preview.json [--doi-lookup]
```

Local parsing always runs, fully offline. `--doi-lookup` additionally
queries Unpaywall for a found DOI's OA/license evidence over the network
(requires `KE_UNPAYWALL_EMAIL`, same as M36's other commands). Without
`--doi-lookup`, `license_rule_result` is always
`"incomplete_missing_license"` -- there is no way to verify reuse rights
from the PDF's own bytes alone, so this module does not pretend to.

```bash
ke manual-pdf-manifest-draft --preview preview.json --output draft.csv
```

Both commands refuse to overwrite an existing output unless `--force` is
supplied, and reject symbolic-link inputs/outputs.

## Why the manifest draft requires a DOI and a passed license

Every other pipeline in this project anchors identity on a provider ID
(PMCID) or DOI and only promotes a candidate whose license evidence has
already passed. A manually-uploaded PDF has no provider assigning it an
ID, so DOI (extracted from the PDF's own text, the same
`knowledge_engine.parser.DOI_PATTERN` `ke import` already relies on) is
the only available identity anchor. If no DOI is found, or the DOI lookup
was skipped, or Unpaywall reports a license this project doesn't accept
(anything more restrictive than CC BY/CC0), `manual-pdf-manifest-draft`
refuses outright rather than promoting a row with unverified reuse rights.

## Output contract

Preview JSON: `source_path`, `content_hash`, `title`, `authors`,
`abstract`, `doi`, `page_count`, `word_count`, `doi_lookup_performed`,
`unpaywall_title`/`unpaywall_is_oa`/`unpaywall_best_license` (populated
only when `--doi-lookup` found a record), `license_rule_result`,
`previewed_at`.

Manifest draft CSV: the exact `sources.csv` column schema
(`manifest_curation.py`'s `MANIFEST_FIELDS`), one row, `source_id` =
`manual-<content-hash-prefix>`, `inclusion_reason` =
`MANUAL_UPLOAD_LICENSE_VERIFIED_VIA_UNPAYWALL`.

## What is deliberately not built yet

- No automatic append to `sources.csv` or `ke corpus-import` invocation --
  a human (or an operator with the day's standing authorization) still
  takes the explicit final step, mirroring every other pipeline's
  discovery/adjudication-vs-acquisition/import separation.
- No batch mode (many PDFs at once). A human manually supplying PDFs one
  at a time doesn't need the worksheet/approvals machinery built for
  automated discovery batches of dozens or hundreds of candidates; if that
  changes, a batch variant is a natural, separate follow-up.
- No non-DOI identity path. A PDF with no discoverable DOI (a preprint, a
  report, a working paper) currently has no way to clear the manifest-draft
  gate; extending identity to other cases (e.g. a human-supplied DOI
  override, or PMID/other-identifier support) is a deliberate future
  decision, not an oversight.
