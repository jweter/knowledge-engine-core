# M14 Empirical PDF Calibration Pilot

## Purpose

Calibrate incoming-PDF checks against a bounded sample of real, legally acquired PMC Open Access files instead of assuming that every PDF contains complete and perfectly matching metadata.

## Command

```bash
python -m knowledge_engine.pdf_calibration_cli inspect \
  --receipt work/m14/acquisition-pilot.json \
  --pdf-directory work/m14/pdfs \
  --output work/m14/pdf-calibration.json
```

The acquisition receipt must contain between one and four files. Run the pilot first with one paper, inspect the findings, then repeat with three additional papers selected for structural variation.

## Current classification model

### Hard failure

- payload does not begin with a PDF signature;
- SHA-256 does not match the acquisition receipt;
- receipt-backed file is missing or unsafe.

### Review required

- PDF advertises encryption.

### Warning

- embedded title metadata was not observed;
- embedded author metadata was not observed;
- terminal `%%EOF` marker is absent or displaced.

Warnings do not reject a paper. They identify ordinary PDF variation that downstream identity reconciliation must resolve from PubMed, PMC, visible document content, and other authoritative evidence.

## Pilot sequence

1. Acquire one approved PMC OA PDF through the production acquisition command.
2. Run this inspector and examine every finding.
3. Repeat with three additional papers representing different journals and study forms.
4. Record recurring, occasional, and contradictory observations.
5. Add stricter rules only when the four-file evidence supports them.

Downloaded PDFs, receipts, and generated calibration reports remain local and must not be committed.

## Boundary

This profiler performs byte-level calibration only. It does not yet claim full PDF parsing, visible first-page extraction, malware scanning, or semantic identity resolution. Those capabilities should be added only after real pilot evidence establishes the required behavior and tolerance thresholds.
