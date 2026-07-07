# License Policy

The vertical slice must be reproducible without committing copyrighted papers to
the repository.

## Repository Policy

- Do not commit PDF files.
- Do not commit full paper text extracted from copyrighted sources.
- Do not commit credentials, institutional access tokens, or private download
  links.
- Do commit source metadata, stable identifiers, source URLs, license notes, and
  access dates.
- Prefer open access sources when practical.

## Acceptable Source Usage Notes

Each source row in `sources.csv` should include one of the following usage notes:

- Open access with license named.
- Public domain.
- Preprint available for research use.
- Institutional access, local use only.
- Metadata-only until legal use is confirmed.
- Excluded because usage rights are unclear.

## Local Files

Local PDFs for later milestones should be stored under:

```text
papers/corpora/glp1_weight_loss/
```

The local PDF path may be recorded in `sources.csv`, but the file itself should
remain outside version control.

## Provenance Expectations

For every source considered, record:

- Source URL.
- DOI or stable identifier when available.
- Access date.
- License or usage note.
- Whether full text can be used locally.

This policy is intentionally conservative. The prototype should prove
traceability without creating legal ambiguity.

