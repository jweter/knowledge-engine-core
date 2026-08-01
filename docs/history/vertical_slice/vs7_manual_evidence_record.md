# VS-7 Manual Evidence Record

VS-7 creates the first manual Evidence Layer prototype for the Knowledge Engine
vertical slice.

This is not automated claim extraction, scientific synthesis, AI reasoning,
metadata enrichment, parser redesign, or a database schema change.

## Why VS-7 Exists

The previous vertical-slice milestones proved that Knowledge Engine Core can
retrieve multiple legally usable papers and display curated metadata. VS-6 then
showed that the retrieval results are good enough for a careful manual evidence
extraction prototype.

VS-7 defines the first minimal evidence record so the project can start learning
what an evidence object needs to contain before automating anything.

## Why STEP 5 Was Chosen First

The selected source is:

```text
Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5 trial
Garvey et al.
Nature Medicine
2022
DOI: 10.1038/s41591-022-02026-4
```

STEP 5 was chosen because it is a randomized controlled trial with a clear
population, intervention, comparator, outcome, and result structure. That makes
it a cleaner first evidence-record example than a systematic review or
meta-analysis.

## Why Manual Extraction Is Acceptable

Manual extraction is acceptable at this stage because the goal is to define and
test the shape of an evidence record, not to automate extraction.

The record is explicitly labeled:

```text
extraction_method: manual_human_review
extraction_status: draft_manual_prototype
```

Manual extraction also keeps provenance visible and prevents the system from
pretending that it can already identify claims, evidence, limitations, or
scientific conclusions automatically.

## Evidence Record Format

The first record is stored as JSONL:

```text
data/corpora/glp1_weight_loss/evidence_records.jsonl
```

JSONL was chosen because future evidence records may need nested provenance,
source spans, limitations, and extraction metadata while remaining easy to
append, review, and validate line by line.

The first record includes:

- `schema_version`
- `evidence_record_id`
- `extraction_method`
- `extraction_status`
- `source_doi`
- `source_title`
- `source_type`
- `study_type`
- `research_question`
- `claim_text`
- `evidence_direction`
- `population`
- `intervention`
- `comparator`
- `outcome`
- `result_summary`
- `source_span`
- `short_source_excerpt`
- `limitations`
- `uncertainty_notes`
- `confidence_note`
- `provenance`
- `created_for_milestone`

This is intentionally not a universal schema. It is the smallest useful
prototype for one manual evidence record.

## Selected Evidence Record Summary

The manual record captures evidence that semaglutide 2.4 mg was associated with
greater body-weight reduction than placebo at week 104 in STEP 5.

Structured summary:

- Population: adults with obesity, or overweight with at least one
  weight-related comorbidity, without diabetes.
- Intervention: once-weekly subcutaneous semaglutide 2.4 mg plus behavioral
  intervention.
- Comparator: placebo plus behavioral intervention.
- Outcome: percentage change in body weight from baseline to week 104.
- Evidence direction: supports.
- Result: the paper reports greater body-weight reduction with semaglutide than
  placebo at week 104.

This record does not say that the Knowledge Engine has proven the research
question. It says that this paper provides evidence bearing on the question.

## Provenance Behavior

The evidence record preserves:

- DOI.
- Source title.
- Local PDF path.
- Page number.
- Section/table context.
- Source URL.
- PDF URL.
- License type and license URL.
- Metadata source.
- Manual extraction notes.

The source span is practical rather than perfect. It identifies page and section
context, but it does not yet provide character offsets, bounding boxes, or a
machine-verifiable quote location.

## Limitations

- Only one evidence record exists.
- The record is manually extracted.
- The format has not been tested across multiple study designs.
- The source span is coarse.
- The record does not include adverse-event extraction.
- The record does not include all STEP 5 endpoints.
- The record does not aggregate evidence across papers.
- The record does not assign a scientific confidence score.

## What This Proves

VS-7 proves that Knowledge Engine Core can represent one manually reviewed piece
of scientific evidence with clear provenance, limitations, and a connection to a
research question.

It also proves that the project can begin modeling an Evidence Layer without
changing the database schema or adding automation too early.

## What This Does Not Prove

VS-7 does not prove:

- Automated evidence extraction.
- Claim extraction.
- Scientific synthesis.
- Confidence scoring.
- Evidence aggregation.
- Contradiction handling.
- Relationship modeling.
- Generality across disciplines or study designs.

## Risks Discovered

- Evidence records can become too verbose unless the required fields stay
  focused.
- Source spans need a stronger future design for page, section, character
  offset, and possibly bounding box references.
- A single result can involve multiple estimands, endpoints, and analysis
  populations; the evidence record must avoid flattening those distinctions too
  aggressively.
- Manual extraction is useful for design, but it will require review discipline
  if more records are added.

## Recommendation for VS-8

VS-8 should display manual evidence records in a human-readable report or CLI
command.

The next milestone should still avoid synthesis. A good VS-8 target would be:

```text
ke evidence list --records data/corpora/glp1_weight_loss/evidence_records.jsonl
```

or a Markdown report generator that renders evidence records with source,
population, intervention, comparator, outcome, result summary, limitations, and
provenance.

