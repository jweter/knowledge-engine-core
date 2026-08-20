# Parser Benchmark Expansion: Marker + MORE

## Purpose
Expand the planned scientific-document parser benchmark beyond PyMuPDF, Docling, and MinerU by evaluating `Marker` as an additional parser candidate and using ideas from the `MORE` benchmark to strengthen methodology.

## Benchmark candidates
- PyMuPDF: current baseline.
- Docling: structured parser candidate.
- MinerU: alternate parser/OCR candidate.
- Marker: structured Markdown/JSON parser candidate.

`MORE` is a benchmark/reference methodology, not a runtime dependency.

## Corpus design
Build a versioned 20–50 document pilot containing representative scientific failure classes:
- single-column clean PDFs;
- two-column journal layouts;
- dense tables;
- equations and symbols;
- figures/captions;
- footnotes;
- references;
- supplementary-material style PDFs;
- scanned/OCR-required documents;
- malformed or partially extractable files;
- mixed-language examples if relevant.

Never commit copyrighted full text unless redistribution is explicitly permitted. Store manifests, hashes, expected metrics, and locally reproducible fixture instructions instead.

## Metrics
### Text fidelity
- normalized character/word accuracy where ground truth exists;
- reading-order correctness;
- missing/duplicated content;
- header/footer contamination.

### Structure
- headings and section hierarchy;
- tables;
- equations;
- lists;
- figure captions;
- references;
- page and block coordinates where available.

### Operational quality
- elapsed time;
- peak memory;
- CPU/GPU requirement;
- install complexity;
- offline behavior;
- deterministic reruns;
- failure diagnostics;
- model download size;
- platform support.

### Knowledge Engine fit
- ability to map output into the canonical parser contract;
- provenance fidelity;
- stable block identity;
- ability to preserve page/span locations;
- graceful fallback behavior.

## Evaluation policy
No parser becomes the default because it wins one aggregate score. Results should identify **document-class strengths**. A routing strategy may be superior to one universal parser.

Possible future routing:
```text
PDF
 -> fast baseline probe
 -> choose parser profile
 -> parse
 -> quality checks
 -> fallback/secondary parser when required
 -> canonical ParsedDocument
```

## Acceptance criteria
- Benchmark is reproducible and versioned.
- Ground truth and scoring logic are separated from parser-specific code.
- Results expose per-document-class performance, not only a single average.
- Parser failures never silently produce trusted empty/garbled documents.
- Licensing/model terms are recorded before adding any dependency.

## Decision outcomes
Each candidate should end in one of:
- default parser;
- specialist/fallback parser;
- benchmark-only reference;
- rejected with recorded reason.

## Non-goals
- adopting every parser;
- optimizing benchmark scores at the expense of provenance;
- using benchmark corpora that cannot be legally reproduced.