# VS-3 First Source Import

VS-3 proves the first real-source Knowledge Engine path:

```text
Scientific Question
  -> Legal Source
  -> Local PDF
  -> Parser
  -> SQLite
  -> FTS Search
  -> ke answer
  -> Cited retrieval result
```

No AI, embeddings, claim extraction, evidence records, knowledge graph, or
scientific synthesis were added.

## Selected Paper

Title:
Efficacy and safety of semaglutide on weight loss in obese or overweight
patients without diabetes: A systematic review and meta-analysis of randomized
controlled trials

Authors:
Xueqin Gao; Xiaoli Hua; Xu Wang; Wanbin Xu; Yu Zhang; Chen Shi; Ming Gu

Year:
2022

Journal:
Frontiers in Pharmacology

DOI:
`10.3389/fphar.2022.935823`

Article URL:
`https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.935823/full`

PDF URL:
`https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.935823/pdf`

License:
Creative Commons Attribution License (CC BY)

License URL:
`https://creativecommons.org/licenses/by/4.0/`

Access date:
2026-07-07

## Legal and Provenance Details

This source is legally usable for the VS-3 local demonstration because the
publisher article page and PDF identify it as an open-access article distributed
under the Creative Commons Attribution License (CC BY).

The paper belongs in the GLP-1 weight-loss demo corpus because it is a
systematic review and meta-analysis of randomized controlled trials evaluating
semaglutide-associated weight loss in adults with obesity or overweight without
diabetes. It provides review-level supporting evidence for the demo research
question.

## Local File Handling

The PDF was downloaded only to:

```text
papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf
```

The file is intentionally ignored by Git through:

```text
papers/**/*.pdf
```

The source metadata and legal provenance are recorded in:

```text
data/corpora/glp1_weight_loss/sources.csv
```

The PDF itself should not be committed.

## Import Command Used

```text
python -m knowledge_engine.cli init
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf --keyword glp1 --keyword semaglutide --keyword obesity --keyword weight-loss
```

Observed import result:

```text
Imported #1: fphar-2022-935823 1..14
Pages: 14  Words: 9408
```

## Database Verification

The local SQLite database contains one imported paper record.

Observed record summary:

```text
id: 1
title: fphar-2022-935823 1..14
doi: 10.3389/fphar.2022.935823
publication_year: None
pages: 14
words: 9408
raw_text_chars: 59290
body_text_chars: 59290
```

## Search Command Used

```text
python -m knowledge_engine.cli search semaglutide
```

Observed result summary:

- The imported paper was returned by SQLite FTS search.
- The snippet included the article title text and semaglutide-related context.
- A display bug caused by PDF ligature characters was found and fixed with a
  minimal CLI text-normalization change.

## Answer Command Used

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?"
```

Observed output summary:

- The imported paper was returned as a relevant paper.
- The displayed title came from the parser-captured title:
  `fphar-2022-935823 1..14`.
- The publication year displayed as `Unknown`.
- The matching snippet referenced GLP-1 receptor agonist and weight management
  language from the extracted text.
- The citation included the captured DOI:
  `10.3389/fphar.2022.935823`.
- The command ended with:

```text
This is retrieval only.
No scientific synthesis has been performed.
```

## Parser Strengths

- Successfully opened and parsed the publisher PDF.
- Extracted full text from all 14 pages.
- Counted 9,408 words.
- Captured the DOI.
- Created searchable text that SQLite FTS could retrieve.

## Parser Weaknesses

- The parser captured `fphar-2022-935823 1..14` as the title instead of the real
  article title.
- Authors were not captured.
- Publication year was not captured.
- Abstract was not captured as a structured metadata field.
- The extracted text contained PDF ligature characters, which exposed a CLI
  display issue on Windows.
- Source spans are still coarse; the system can show snippets, but not precise
  page or offset citations.

## Missing Metadata

The following metadata is known from source provenance but not captured by the
current parser/database import:

- Correct title.
- Authors.
- Publication year.
- Journal.
- License type.
- License URL.
- PDF URL.
- Access date.

These are recorded in `sources.csv` for now rather than added to the database
schema.

## What This Proved

VS-3 proves that Knowledge Engine Core can:

- Start from a legally usable scientific source.
- Store local PDF provenance outside Git.
- Import a real publisher PDF through the existing CLI.
- Extract text with the existing parser.
- Store the paper and extracted text in SQLite.
- Index the paper in SQLite FTS.
- Retrieve the paper through `ke search`.
- Retrieve the paper through `ke answer`.
- Produce a cited retrieval result with the required retrieval-only disclaimer.

## What This Did Not Prove

VS-3 does not prove:

- Scientific synthesis.
- Claim extraction.
- Evidence records.
- Relationship modeling.
- Confidence or uncertainty scoring.
- Accurate metadata extraction.
- Source-span citation precision.
- Corpus-scale ingestion.
- Parser robustness across multiple publishers.

## Recommendation for VS-4

VS-4 should import two to four additional clearly legal open-access sources from
the demo corpus and then evaluate retrieval quality across multiple papers.

Before adding more sources, consider a small metadata correction workflow that
uses `sources.csv` to preserve known title, year, journal, license, and URL
metadata without changing the database schema prematurely.

