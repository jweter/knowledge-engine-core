# License Policy

This corpus must be reproducible without committing copyrighted papers to
the repository, matching `glp1_weight_loss/license_policy.md` exactly.

## Repository Policy

- Do not commit PDF files.
- Do not commit full paper text extracted from copyrighted sources.
- Do not commit credentials, institutional access tokens, or private
  download links.
- Do commit source metadata, stable identifiers, source URLs, license
  notes, and access dates.
- Prefer open access sources when practical.

## Acceptable Source Usage Notes

Each source row in `sources.csv` must set `usage_status` to one of the
following values, enforced by `knowledge_engine.corpus.validation`
(`USAGE_STATUSES`):

- `approved_open_access` -- open access with license named.
- `approved_public_domain` -- public domain.
- `approved_author_manuscript` -- preprint or author manuscript available
  for research use.
- `approved_local_only` -- institutional access, local use only.
- `metadata_only` -- metadata-only until legal use is confirmed.
- `needs_legal_review` -- usage rights not yet confirmed.
- `excluded_legal` -- excluded because usage rights are unclear.

For `approved_open_access` rows, `license_type` must additionally pass
`knowledge_engine.license_rules.evaluate_license` -- only unrestricted
`CC BY` (any real published version) or `CC0` bases are accepted;
`CC BY-NC`, `CC BY-ND`, and `CC BY-SA` variants are rejected because they
restrict commercial use and/or derivative works, which conflicts with
this project's extraction and redistribution of derived Evidence
Records. `ke corpus-validate` re-checks every row's `license_type`
against this rule on every run, not just at initial ingestion.

(This section previously described a six-item prose vocabulary that
predated the machine-checked `usage_status`/`license_type` enum values
above; it never matched the enforced schema. Corrected 2026-08-09 during
a license/attribution review across all three corpora -- see
`docs/roadmap.md`'s v1.0.0 release-gate section.)

## Local Files

Local PDFs for later milestones should be stored under:

```text
papers/corpora/oncology_nsclc_checkpoint_inhibitors/
```

The local PDF path may be recorded in `sources.csv`, but the file itself
should remain outside version control.

## Provenance Expectations

For every source considered, record:

- Source URL.
- DOI or stable identifier when available.
- Access date.
- License or usage note.
- Whether full text can be used locally.

This policy is intentionally conservative. The corpus should prove
traceability without creating legal ambiguity.
