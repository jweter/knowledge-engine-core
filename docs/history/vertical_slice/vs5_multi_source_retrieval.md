# VS-5 Multi-Source Retrieval

VS-5 expands the vertical slice from one real source to a tiny multi-paper demo
corpus.

It proves this retrieval-only path:

```text
Scientific Question
  -> Multiple Legal Sources
  -> Local PDFs
  -> Parser
  -> SQLite
  -> FTS Search
  -> ke answer --sources
  -> Ranked cited retrieval results
```

No AI, embeddings, claim extraction, evidence records, scientific synthesis,
database schema changes, or parser redesign were added.

## Selected Papers

### Existing Source: Gao et al. 2022

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

Source URL:
`https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.935823/full`

PDF URL:
`https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.935823/pdf`

License:
CC-BY

License URL:
`https://creativecommons.org/licenses/by/4.0/`

Why it belongs:
This systematic review and meta-analysis provides synthesized randomized trial
evidence for semaglutide-associated weight loss in adults with overweight or
obesity without diabetes.

### New Source: Garvey et al. 2022

Title:
Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5
trial

Authors:
W. Timothy Garvey; Rachel L. Batterham; Meena Bhatta; Silvio Buscemi; Louise N.
Christensen; Juan P. Frias; Esteban Jodar; Kristian Kandler; Georgia Rigas;
Thomas A. Wadden; Sean Wharton; STEP 5 Study Group

Year:
2022

Journal:
Nature Medicine

DOI:
`10.1038/s41591-022-02026-4`

Source URL:
`https://www.nature.com/articles/s41591-022-02026-4`

PDF URL:
`https://www.nature.com/articles/s41591-022-02026-4.pdf`

License:
CC-BY

License URL:
`https://creativecommons.org/licenses/by/4.0/`

Why legally usable:
The publisher page identifies the article as open access and licensed under the
Creative Commons Attribution 4.0 International License.

Why it belongs:
STEP 5 provides randomized trial evidence for sustained two-year weight loss
with continued semaglutide treatment in adults with overweight or obesity
without diabetes.

### New Source: Ryan et al. 2024

Title:
Long-term weight loss effects of semaglutide in obesity without diabetes in the
SELECT trial

Authors:
Donna H. Ryan; Ildiko Lingvay; John Deanfield; Steven E. Kahn; Eric Barros;
Bartolome Burguera; Helen M. Colhoun; Cintia Cercato; Dror Dicker; Deborah B.
Horn; G. Kees Hovingh; Ole Kleist Jeppesen; Alexander Kokkinos; A. Michael
Lincoff; Sebastian M. Meyhofer; Tugce Kalayci Oral; Jorge Plutzky; Andre P. van
Beek; John P. H. Wilding; Robert F. Kushner

Year:
2024

Journal:
Nature Medicine

DOI:
`10.1038/s41591-024-02996-7`

Source URL:
`https://www.nature.com/articles/s41591-024-02996-7`

PDF URL:
`https://www.nature.com/articles/s41591-024-02996-7.pdf`

License:
CC-BY

License URL:
`https://creativecommons.org/licenses/by/4.0/`

Why legally usable:
The publisher page identifies the article as open access and provides a
publisher PDF. The article is treated as CC-BY open-access content for the local
demo.

Why it belongs:
The SELECT analysis provides long-term weight and anthropometric outcome data
for semaglutide in adults with overweight or obesity and cardiovascular disease,
without diabetes.

## Local PDF Handling

The PDFs were downloaded only under:

```text
papers/corpora/glp1_weight_loss/
```

Local PDF files:

```text
papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf
papers/corpora/glp1_weight_loss/s41591-022-02026-4.pdf
papers/corpora/glp1_weight_loss/s41591-024-02996-7.pdf
```

Git ignore verification:

```text
.gitignore:31:papers/**/*.pdf papers/corpora/glp1_weight_loss/*.pdf
```

The PDFs should not be committed.

## Import Commands Used

Existing source:

```text
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/fphar-2022-935823.pdf --keyword glp1 --keyword semaglutide --keyword obesity --keyword weight-loss
```

New sources:

```text
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/s41591-022-02026-4.pdf --keyword glp1 --keyword semaglutide --keyword obesity --keyword weight-loss --keyword step5
python -m knowledge_engine.cli import papers/corpora/glp1_weight_loss/s41591-024-02996-7.pdf --keyword glp1 --keyword semaglutide --keyword obesity --keyword weight-loss --keyword select
```

Observed import results:

```text
Imported #2: Long-term weight loss effects of semaglutide in obesity without diabetes in the SELECT trial
Pages: 20  Words: 9465

Imported #3: Two-year effects of semaglutide in adults with overweight or obesity: the STEP 5 trial
Pages: 23  Words: 11981
```

Database verification:

```text
id: 1
doi: 10.3389/fphar.2022.935823
pages: 14
words: 9408
raw_text_chars: 59290

id: 2
doi: 10.1038/s41591-024-02996-7
pages: 20
words: 9465
raw_text_chars: 57680

id: 3
doi: 10.1038/s41591-022-02026-4
pages: 23
words: 11981
raw_text_chars: 76785
```

## Answer Command Used

```text
python -m knowledge_engine.cli answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
```

Observed result summary:

- Three papers were retrieved.
- All three displayed curated metadata from `sources.csv`.
- All three displayed `Metadata source: corpus sources.csv`.
- All three displayed authors, journal, source URL, license type, year, and DOI.
- All three displayed snippets.
- The command ended with the retrieval-only disclaimer.

Observed ranking:

1. Gao et al. 2022 systematic review/meta-analysis.
2. Garvey et al. 2022 STEP 5 randomized trial.
3. Ryan et al. 2024 SELECT long-term analysis.

## Retrieval Ranking Observations

- The review article ranked first, likely because its broad title and full text
  contain many query terms.
- STEP 5 ranked second and was clearly relevant to the question.
- SELECT ranked third and was relevant, but the question did not include
  cardiovascular disease or SELECT-specific terms.
- The ranking is plausible for retrieval, but it is not evidence weighting.
- The ranking should not be interpreted as scientific confidence or study
  quality.

## Snippet Quality Observations

- Snippets were sufficient to confirm topical relevance.
- The Frontiers snippet included title and GLP-1/weight-management language.
- The SELECT snippet included overweight/obesity and anthropometric outcome
  language.
- The STEP 5 snippet was less ideal because it came from a reference passage
  rather than the main result section.
- FTS snippets are useful for retrieval verification, but not enough for
  evidence extraction.

## Parser Strengths

- Parsed all three real publisher PDFs.
- Captured page count and word count for all three sources.
- Captured DOI for all three sources.
- Captured usable titles for the two Nature Medicine PDFs.
- Captured first authors for the two Nature Medicine PDFs.
- Produced searchable extracted text for all three sources.

## Parser Weaknesses

- The Frontiers paper title was parsed incorrectly as `fphar-2022-935823 1..14`.
- The Frontiers authors, year, and abstract were not captured.
- Publication year was not captured for any of the three papers.
- Author extraction appears incomplete, usually capturing only one visible
  author rather than the full author list.
- Snippets can come from references rather than primary result passages.
- Source spans remain coarse and are not suitable as precise citations.

## Metadata Overlay Strengths

- The overlay made all three retrieval results scientifically readable.
- DOI matching worked across the imported database records and `sources.csv`.
- Curated title, authors, year, journal, source URL, license type, and DOI were
  displayed without modifying database records.
- The metadata provenance label made the manual source explicit.

## Metadata Overlay Weaknesses

- DOI matching is the only matching strategy.
- The overlay does not validate licenses.
- The overlay does not resolve conflicting metadata.
- The overlay does not update database records.
- The overlay depends on manually maintained CSV quality.
- The overlay is display-only and should not be treated as metadata enrichment.

## What VS-5 Proved

VS-5 proved that Knowledge Engine Core can:

- Track multiple legally usable open-access scientific sources.
- Keep local PDFs out of Git.
- Import multiple real PDFs through the existing CLI.
- Extract and store full text in SQLite.
- Search multiple papers with SQLite FTS.
- Retrieve multiple relevant papers with `ke answer --sources`.
- Display curated corpus metadata at retrieval time.
- Preserve the retrieval-only boundary and disclaimer.

## What VS-5 Did Not Prove

VS-5 did not prove:

- Scientific synthesis.
- Evidence records.
- Claim extraction.
- Relationship modeling.
- Confidence scoring.
- Citation spans.
- Robust metadata parsing across publishers.
- Bulk import behavior.
- Corpus completeness.

## Recommendation for VS-6

VS-6 should improve retrieval review without adding synthesis. The safest next
step is to add a small retrieval evaluation checklist or report that records, for
each query result:

- whether the paper is relevant;
- whether the snippet is useful;
- whether the metadata overlay matched;
- whether the result is primary evidence, review evidence, or background;
- whether the result should be included in future evidence extraction.

This would keep the project honest before moving toward evidence records.

