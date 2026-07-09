# VS-6 Retrieval Evaluation

VS-6 adds a lightweight human evaluation layer for retrieval results from the
GLP-1 vertical slice.

This is not scientific synthesis. It does not add AI, embeddings, claim
extraction, evidence records, relationship modeling, confidence scoring, parser
changes, or database schema changes.

## Research Question

Do GLP-1 receptor agonists reduce body weight in adults with overweight or
obesity?

## Command Evaluated

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
```

## Evaluation Fields

Each retrieved paper is evaluated with:

- Title.
- DOI.
- Retrieval rank.
- Relevance to the research question.
- Snippet usefulness.
- Metadata overlay status.
- Likely evidence type.
- Whether it should proceed to future evidence extraction.
- Notes on limitations or caveats.

## Evaluation Summary

| Rank | Paper | DOI | Relevance | Snippet usefulness | Metadata overlay | Likely evidence type | Proceed to evidence extraction? |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | Efficacy and safety of semaglutide on weight loss in obese or overweight patients without diabetes: A systematic review and meta-analysis of randomized controlled trials | `10.3389/fphar.2022.935823` | High | Medium | Matched by DOI | Systematic review and meta-analysis | Yes |
| 2 | Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5 trial | `10.1038/s41591-022-02026-4` | High | Low to medium | Matched by DOI | Randomized controlled trial | Yes |
| 3 | Long-term weight loss effects of semaglutide in obesity without diabetes in the SELECT trial | `10.1038/s41591-024-02996-7` | Medium to high | Medium | Matched by DOI | Prespecified trial analysis / long-term outcomes | Yes, with population caveat |

## Per-Paper Evaluation

### Rank 1: Gao et al. 2022

Title:
Efficacy and safety of semaglutide on weight loss in obese or overweight
patients without diabetes: A systematic review and meta-analysis of randomized
controlled trials

DOI:
`10.3389/fphar.2022.935823`

Retrieval rank:
1

Relevance to research question:
High. The paper directly addresses semaglutide-associated weight loss in adults
with obesity or overweight without diabetes.

Snippet usefulness:
Medium. The snippet confirms GLP-1 receptor agonist and weight-management
context, but it is not a clean result passage and should not be treated as an
evidence statement.

Metadata overlay status:
Matched by DOI. Curated title, authors, year, journal, source URL, license type,
and DOI displayed from `sources.csv`.

Likely evidence type:
Systematic review and meta-analysis.

Proceed to future evidence extraction:
Yes.

Limitations or caveats:
This source synthesizes semaglutide trials rather than representing independent
primary evidence. It should be useful for overview evidence, included-study
identification, and comparison against primary trial extraction, but it should
not be double-counted with its included trials in later synthesis.

### Rank 2: Garvey et al. 2022

Title:
Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5
trial

DOI:
`10.1038/s41591-022-02026-4`

Retrieval rank:
2

Relevance to research question:
High. The paper directly evaluates semaglutide treatment in adults with
overweight or obesity and reports long-term body-weight outcomes.

Snippet usefulness:
Low to medium. The result was correctly retrieved, but the displayed snippet came
from a reference or contextual passage rather than the most useful abstract or
results passage.

Metadata overlay status:
Matched by DOI. Curated title, authors, year, journal, source URL, license type,
and DOI displayed from `sources.csv`.

Likely evidence type:
Randomized controlled trial.

Proceed to future evidence extraction:
Yes.

Limitations or caveats:
The paper is highly suitable for future evidence extraction, but retrieval
snippets alone are not enough. Future extraction should capture treatment arm,
comparator, duration, body-weight endpoints, population criteria, and adverse
event context.

### Rank 3: Ryan et al. 2024

Title:
Long-term weight loss effects of semaglutide in obesity without diabetes in the
SELECT trial

DOI:
`10.1038/s41591-024-02996-7`

Retrieval rank:
3

Relevance to research question:
Medium to high. The paper addresses semaglutide-associated weight and
anthropometric outcomes in adults with overweight or obesity without diabetes,
but the trial population has preexisting cardiovascular disease and the parent
trial was cardiovascular-outcomes focused.

Snippet usefulness:
Medium. The snippet mentions overweight or obesity, absence of diabetes,
semaglutide, anthropometric outcomes, and baseline body mass context. It is
topically useful but still not a substitute for source-span evidence.

Metadata overlay status:
Matched by DOI. Curated title, authors, year, journal, source URL, license type,
and DOI displayed from `sources.csv`.

Likely evidence type:
Prespecified trial analysis / long-term outcomes.

Proceed to future evidence extraction:
Yes, with population caveat.

Limitations or caveats:
This source should be extracted as long-term supporting evidence, but not treated
as a general obesity efficacy trial without qualification. Its cardiovascular
disease population and parent trial design should be preserved as interpretation
limits.

## Retrieval Quality Assessment

Overall retrieval quality:
Good enough to proceed to a limited evidence-extraction prototype.

Strengths:

- All three imported papers were retrieved.
- All three metadata overlays matched by DOI.
- All three results displayed curated title, authors, year, journal, source URL,
  license type, and DOI.
- The ranking placed the broad systematic review first, followed by two
  long-term semaglutide trial sources.
- The output preserved the retrieval-only disclaimer.

Weaknesses:

- Snippets are inconsistent in usefulness.
- At least one relevant paper returned a snippet from a reference/contextual
  passage rather than the main findings.
- FTS ranking is relevance ranking, not evidence-quality ranking.
- The current command does not distinguish primary evidence, review evidence,
  or background evidence in output.
- The current command does not identify population caveats without manual
  review.

## What VS-6 Proved

VS-6 proved that retrieval output can be reviewed with a small, explicit,
human-readable checklist before the project introduces evidence records.

It also proved that the current vertical slice has enough retrieval quality to
support the next architectural step: carefully extracting evidence from a small
number of known-relevant papers.

## What VS-6 Did Not Prove

VS-6 did not prove:

- Scientific synthesis.
- Claim extraction.
- Evidence record design.
- Relationship modeling.
- Confidence scoring.
- Automated relevance judgment.
- Source-span precision.
- Corpus completeness.

## Recommendation for VS-7

VS-7 should create the first manual evidence extraction template for one paper.

The safest next step is not automation. It is a small, human-curated structure
that records:

- research question;
- source paper;
- relevant result text or source span;
- study type;
- population;
- intervention;
- comparator;
- outcome;
- direction of evidence;
- limitations;
- citation/provenance.

This should remain manual and transparent. The goal is to define the shape of an
evidence record before trying to automate extraction.

