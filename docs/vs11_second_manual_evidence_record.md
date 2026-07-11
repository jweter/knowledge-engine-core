# VS-11 Second Manual Evidence Record

VS-11 adds a second manual evidence record to the GLP-1 vertical slice and
verifies that the Markdown evidence report can display multiple reviewed
evidence records without synthesis.

It does not add AI, embeddings, automated claim extraction, automated evidence
extraction, scientific synthesis, consensus calculation, confidence scoring,
parser changes, database schema changes, new imports, or new PDF downloads.

## Why VS-11 Exists

VS-10 proved that a Markdown report can combine retrieval results, curated
source metadata, and one matched manual evidence record. That was useful, but it
only exercised one evidence type from one randomized controlled trial.

VS-11 adds a second source-linked evidence record from a different paper so the
report can show multiple reviewed evidence records across different study
types.

## Selected Source

The second record uses:

- Title: Efficacy and safety of semaglutide on weight loss in obese or
  overweight patients without diabetes: A systematic review and meta-analysis of
  randomized controlled trials.
- Authors: Xueqin Gao; Xiaoli Hua; Xu Wang; Wanbin Xu; Yu Zhang; Chen Shi;
  Ming Gu.
- Journal: Frontiers in Pharmacology.
- Year: 2022.
- DOI: 10.3389/fphar.2022.935823.

This paper was selected because it is a systematic review and meta-analysis. It
tests whether the evidence record format can represent a pooled evidence source,
not only a single trial.

## Difference From STEP 5

The STEP 5 record represents one randomized controlled trial result. The Gao et
al. record represents a review-level synthesis of multiple randomized trials as
reported by the paper authors.

This difference matters because the evidence record needs to preserve:

- study type;
- population scope;
- pooled outcome wording;
- heterogeneity limitations;
- the distinction between reported review findings and corpus-level Knowledge
  Engine conclusions.

## Evidence Record Change

One JSONL record was appended to:

```text
data/corpora/glp1_weight_loss/evidence_records.jsonl
```

The new record ID is:

```text
ev-glp1-gao-meta-analysis-body-weight-001
```

The record is manually extracted and remains in draft prototype status.

## Report Behavior

The VS-10 report command was run with the updated evidence file:

```text
ke evidence-report "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv --evidence data/corpora/glp1_weight_loss/evidence_records.jsonl --output data/corpora/glp1_weight_loss/reports/glp1_weight_loss_evidence_report.md --force
```

The generated report showed:

- manual evidence available for Gao et al.;
- manual evidence available for STEP 5;
- manual evidence not available for SELECT;
- separate evidence previews under the matching retrieved papers;
- the required no-synthesis disclaimer.

The generated report was treated as a local review artifact, not a committed
source document.

## Field Fit

The current evidence fields handled both the RCT and meta-analysis examples
reasonably well. The shared fields for population, intervention, comparator,
outcome, result summary, limitations, uncertainty notes, source span, and
provenance remained useful.

The meta-analysis record exposed one limitation: future evidence records may
need more explicit fields for pooled estimate type, heterogeneity, included
study count, review methods, and risk-of-bias interpretation. For VS-11, those
details remain in human-readable result and limitation fields.

## Limitations

- The second evidence record was manually extracted from one review paper.
- The system does not validate the extracted record against the PDF.
- The system does not compare the two evidence records.
- The system does not calculate consensus or confidence scores.
- The system does not distinguish trial-level and review-level evidence beyond
  the `study_type` field and text notes.
- The report can display multiple records, but it does not synthesize them.

## What This Proves

VS-11 proves that the vertical slice can represent and display multiple manual
evidence records for the same research question across different source papers
and study types.

It also proves that the report can show manual evidence availability by source
without claiming that the question has been answered.

## What This Does Not Prove

VS-11 does not prove:

- automated evidence extraction;
- scientific synthesis;
- corpus-level consensus;
- contradiction detection;
- confidence scoring;
- source-span verification;
- systematic review appraisal;
- review workflow approval.

## Risks Discovered

- Review-level evidence needs more structured appraisal fields later.
- Pooled estimates can be easy to overstate unless limitations and uncertainty
  are kept visible.
- The same primary trials may appear both as individual papers and inside a
  meta-analysis, creating future double-counting risk.
- Evidence records need lifecycle status before the project accumulates many
  draft manual records.

## Recommendation for VS-12

VS-12 should add a minimal evidence review checklist or status field so manual
evidence records can be marked as draft, reviewed, needs revision, or rejected
without turning them into scientific synthesis.
