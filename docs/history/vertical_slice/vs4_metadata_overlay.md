# VS-4 Metadata Overlay

VS-4 adds a display-time metadata overlay for retrieval output.

It does not change parser behavior, database records, database schema, search
ranking, or scientific reasoning.

## Why VS-4 Exists

VS-3 proved that Knowledge Engine Core can import a real legally usable PDF,
extract text, index it in SQLite FTS, and retrieve it with `ke answer`.

It also exposed a practical problem: the parser successfully extracted text, but
the displayed metadata was weak.

Observed parser/database metadata for the first source:

- Title: `fphar-2022-935823 1..14`
- Authors: missing
- Publication year: missing
- Abstract: missing
- DOI: captured correctly

The corpus source file already contains better human-curated metadata with
provenance and license details. VS-4 lets `ke answer` use that curated metadata
for display without pretending that the parser extracted it.

## Display Overlay, Not Enrichment

This is not metadata enrichment.

Metadata enrichment would imply updating stored records, resolving conflicts,
tracking provider priority, and preserving field-level provenance in durable
storage. That belongs later.

VS-4 is intentionally smaller:

- The database remains unchanged.
- Parser output remains unchanged.
- The CSV is loaded only when the user passes `--sources`.
- Matching uses DOI when available.
- Curated values are used only for CLI display.
- The output explicitly labels curated metadata as coming from the corpus source
  file.

## Command Example

```text
ke answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
```

## Provenance Behavior

When a search result DOI matches a row in `sources.csv`, `ke answer` displays:

- Curated title.
- Curated authors.
- Curated year.
- Curated journal.
- Curated DOI.
- Curated source URL.
- Curated license type.

The output includes:

```text
Metadata source: corpus sources.csv
```

This line is required because manual corpus metadata must remain visibly manual.

If no DOI match is found, the command falls back to database/parser metadata.

If the CSV is invalid, the command fails clearly instead of silently ignoring the
problem.

## Limitations

- Matching currently uses DOI only.
- The overlay does not update database records.
- The overlay does not validate licenses.
- The overlay does not fetch metadata from PubMed, Crossref, publishers, or any
  external provider.
- The overlay does not resolve conflicts between CSV metadata and database
  metadata.
- The overlay does not add structured provenance tables.
- The overlay is intended for small demonstration corpora, not large-scale
  ingestion.

## Later Work

Later milestones should consider:

- Field-level metadata provenance.
- A durable metadata correction workflow.
- Importing curated source metadata during ingestion.
- Conflict handling between parser, corpus, PubMed, Crossref, and publisher
  metadata.
- Displaying source spans for metadata where available.
- Supporting identifiers beyond DOI, such as PubMed ID, PMC ID, arXiv ID, and
  source URL.
- Moving from CSV overlay to a documented manifest format if the corpus grows.

