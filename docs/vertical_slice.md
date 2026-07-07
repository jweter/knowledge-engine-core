# Vertical Slice Prototype

This document defines the first end-to-end architectural prototype for Knowledge
Engine Core. It is not Phase 1 implementation. It is a small proof that one
scientific question can move through the conceptual architecture from source
documents to a traceable answer.

The prototype should be intentionally small, local, and understandable. It
should prove that the architecture works before the project optimizes for scale,
automation, or performance.

## Scope

The vertical slice should support approximately 10 legally usable scientific
papers focused on one narrow research question.

The complete path is:

```text
PDF
  -> Parser
  -> Metadata
  -> Claim extraction
  -> Evidence records
  -> Relationships
  -> Scientific question
  -> Evidence retrieval
  -> Simple evidence synthesis
  -> Human-readable answer
  -> Source citations
```

The prototype should answer one question well enough to demonstrate traceable
scientific reasoning. It does not need to generalize across domains yet.

## Non-Goals

- Bulk corpus ingestion.
- Full Phase 1 manifest and recovery behavior.
- Automated claim extraction at production quality.
- Embeddings or vector search.
- LLM reasoning.
- Knowledge graph databases.
- Web interface.
- Multi-user workflows.
- Performance optimization.
- Automated scientific truth determination.

## Architecture

The prototype should follow the conceptual layers already defined in the
Scientific Data Model:

```text
Source Layer
  PDF papers and bibliographic metadata

Extraction Layer
  parsed text, source spans, metadata candidates, parser diagnostics

Evidence Layer
  manually or simply extracted claims, evidence records, methods, results,
  limitations, confidence notes, and uncertainty notes

Relationship Layer
  typed support, contradiction, qualification, citation, and concept links

Reasoning Layer
  one scientific question, retrieved evidence, simple synthesis, answer, and
  source citations
```

The vertical slice should use the simplest durable representation that keeps
these layers visible. Early implementation may use local files or small SQLite
tables, but the design should not depend on any one storage technology as the
definition of knowledge.

## Components

### Source Set

Purpose:
Define the 10-paper prototype corpus.

Minimum behavior:
- Store or reference each PDF.
- Record title, DOI if available, source URL, license or usage note, and access
  date.
- Identify one narrow scientific question the papers can reasonably address.

Prototype simplification:
The source set can be curated manually. It does not need duplicate detection,
resumable import, or automated metadata enrichment.

### Parser

Purpose:
Convert each PDF into extracted text and basic parser diagnostics.

Minimum behavior:
- Extract raw text.
- Record page count.
- Record word count.
- Preserve paper identifier and source document path.
- Report extraction failures without stopping the whole prototype.

Prototype simplification:
Use the existing PDF parser behavior. Source spans may initially be coarse, such
as paper identifier plus page number or section label.

### Metadata

Purpose:
Preserve descriptive information separately from scientific claims.

Minimum behavior:
- Store title.
- Store authors when available.
- Store DOI when available.
- Store publication year or unknown status.
- Store source provenance for each metadata field where practical.

Prototype simplification:
Metadata can be corrected manually after parsing. Manual corrections must remain
visible as manual metadata, not silently treated as parser output.

### Claim Extraction

Purpose:
Identify evaluable statements from the source set.

Minimum behavior:
- Create a small number of claims per paper.
- Link each claim back to a paper and source span.
- Classify claim type, such as descriptive, causal, comparative,
  methodological, or limitation.
- Mark whether the claim was manually entered or extracted by a simple rule.

Prototype simplification:
Manual claim extraction is acceptable and preferred if it keeps the first slice
transparent. A simple text file, CSV, JSONL file, or small CLI command can be
used later.

### Evidence Records

Purpose:
Connect claims to the evidence that supports, contradicts, weakens, or qualifies
them.

Minimum behavior:
- Link evidence to a claim or scientific question.
- Link evidence to source spans.
- Record evidence direction: supports, contradicts, qualifies, or contextualizes.
- Record method or result notes when available.
- Record limitation and uncertainty notes.

Prototype simplification:
Evidence quality can be a short human-readable note rather than a numeric score.
Confidence can be low, medium, high, or unknown with visible rationale.

### Relationships

Purpose:
Represent typed links among claims, evidence, concepts, and sources.

Minimum behavior:
- Support relationships between evidence and claims.
- Contradiction relationships between conflicting claims or evidence records.
- Qualification relationships for scope, method, population, or condition
  limits.
- Concept links for the main entities in the question.

Prototype simplification:
Relationships can be manually curated. A full graph database is unnecessary.

### Scientific Question

Purpose:
Anchor the prototype around one question that can be answered from the source
set.

Minimum behavior:
- Store the question text.
- Store related concepts.
- Store inclusion notes describing which evidence is relevant.
- Retrieve matching evidence records.

Prototype simplification:
Only one question needs to exist. It should be narrow enough that a human can
evaluate whether the answer is reasonable.

### Evidence Retrieval

Purpose:
Find evidence records relevant to the scientific question.

Minimum behavior:
- Retrieve by question identifier, linked concepts, keywords, or manually
  assigned relevance.
- Return evidence with claim text, direction, confidence, limitations, and source
  citations.
- Preserve provenance in the retrieval result.

Prototype simplification:
Manual question-to-evidence links are acceptable. Keyword search can supplement
manual links but should not be the only source of relevance.

### Evidence Synthesis

Purpose:
Create a transparent answer from retrieved evidence.

Minimum behavior:
- Summarize the main supported answer.
- Identify supporting evidence.
- Identify contradictory or qualifying evidence.
- State uncertainty.
- Avoid claiming certainty.
- Include source citations.

Prototype simplification:
Synthesis can use deterministic templates or manually written summaries. No LLM
is required.

### Human-Readable Answer

Purpose:
Show that the system can produce a useful research-facing output.

Minimum behavior:
- Display the scientific question.
- Display a concise answer.
- Display evidence grouped by supports, contradicts, and qualifies.
- Display confidence and uncertainty rationale.
- Display citations to source documents.

Prototype simplification:
A CLI command or Markdown report is enough. A web UI is unnecessary.

## Manual Steps

Manual work is acceptable in this prototype when it makes provenance clearer.

Allowed manual steps:
- Selecting the 10 papers.
- Confirming metadata.
- Writing or correcting claims.
- Creating evidence records.
- Assigning evidence direction.
- Adding concept tags.
- Linking evidence to the scientific question.
- Writing the first synthesis template or answer notes.

Manual steps must be explicit. The prototype should never hide manual judgment as
automated extraction or automated reasoning.

## Success Criteria

The vertical slice succeeds when:

- Approximately 10 PDFs can be represented as sources and documents.
- Text can be extracted or failures can be recorded.
- Metadata is stored separately from claims and evidence.
- At least one scientific question is represented.
- Each paper contributes zero or more claims.
- Claims link back to source spans.
- Evidence records link claims, sources, methods or result notes, limitations,
  and provenance.
- Relationships can represent support, contradiction, and qualification.
- A retrieval step returns evidence relevant to the question.
- A synthesis step produces a human-readable answer.
- The answer includes source citations and visible uncertainty.
- A reviewer can trace every answer statement back to evidence and source
  material.

## Failure Criteria

The vertical slice fails if:

- The answer cannot be traced back to source documents.
- Metadata, claims, evidence, and synthesis are mixed together without clear
  boundaries.
- Manual judgments are presented as automated conclusions.
- Contradictory or qualifying evidence cannot be represented.
- The model requires a graph database, LLM, vector index, or web interface to
  function.
- The prototype becomes a bulk ingestion project.
- The implementation optimizes performance before proving the conceptual flow.
- The output gives the impression that the system has decided scientific truth.

## Milestones

### VS-0: Select the Prototype Question and Source Set

Goal:
Choose one narrow scientific question and approximately 10 legally usable PDFs.

Testable outcome:
A reviewer can see the question, inclusion rationale, and source list.

Complexity:
Low.

Risk:
Choosing a question that is too broad will make synthesis vague.

### VS-1: Represent Sources, Documents, and Metadata

Goal:
Create the minimum representation for papers, PDFs, provenance, and metadata.

Testable outcome:
Each paper has a source identity, document reference, basic metadata, and
provenance.

Complexity:
Low to medium.

Risk:
Overfitting the representation to papers instead of preserving the source and
document distinction.

### VS-2: Parse Text and Preserve Extraction Diagnostics

Goal:
Extract raw text from the prototype PDFs and record page count, word count, and
failure status.

Testable outcome:
Each PDF has extracted text or a visible parser failure.

Complexity:
Low.

Risk:
Poor PDF extraction may make source spans coarse or incomplete.

### VS-3: Capture Claims

Goal:
Create a small set of evaluable claims linked to source spans.

Testable outcome:
Claims can be listed by paper and traced to source text.

Complexity:
Medium.

Risk:
Claims may be too broad, compound, or interpretive unless the first examples are
carefully curated.

### VS-4: Create Evidence Records

Goal:
Link claims to supporting, contradicting, qualifying, or contextualizing
evidence.

Testable outcome:
Evidence records include direction, source span, method or result notes,
limitations, confidence notes, and provenance.

Complexity:
Medium.

Risk:
Evidence records can become vague if they do not clearly state what evidence
bears on which claim or question.

### VS-5: Add Relationships and Concepts

Goal:
Represent typed relationships among claims, evidence, contradictions,
qualifications, and the main scientific concepts.

Testable outcome:
The prototype can show why two claims agree, conflict, or differ by scope.

Complexity:
Medium.

Risk:
Relationship names may drift unless constrained to a small initial vocabulary.

### VS-6: Retrieve Evidence for the Question

Goal:
Given the prototype question, return the relevant evidence records with
citations and provenance.

Testable outcome:
A command or report retrieves the evidence set for the question.

Complexity:
Medium.

Risk:
Pure keyword retrieval may miss relevant evidence, so manual links should be
allowed in the first slice.

### VS-7: Synthesize a Human-Readable Answer

Goal:
Generate a concise answer that separates support, contradiction, qualification,
confidence, and uncertainty.

Testable outcome:
The answer can be reviewed against its evidence records and source citations.

Complexity:
Medium.

Risk:
The synthesis may sound more certain than the evidence permits.

### VS-8: End-to-End Review

Goal:
Validate that the entire chain works from PDF to cited answer.

Testable outcome:
A reviewer can start from the final answer and trace backward to evidence,
claims, source spans, metadata, and PDFs.

Complexity:
Low to medium.

Risk:
Small inconsistencies between object names, files, commands, or reports can make
the architecture feel more complete than it really is.

## Recommended Implementation Order

1. VS-0: Select the prototype question and source set.
2. VS-1: Represent sources, documents, and metadata.
3. VS-2: Parse text and preserve extraction diagnostics.
4. VS-3: Capture claims.
5. VS-4: Create evidence records.
6. VS-5: Add relationships and concepts.
7. VS-6: Retrieve evidence for the question.
8. VS-7: Synthesize a human-readable answer.
9. VS-8: Perform end-to-end review.

This order keeps each step independently testable while preserving the main
architectural flow. It also avoids building later reasoning behavior before the
source, claim, evidence, and provenance boundaries are visible.

## Design Guidance

- Keep the prototype small enough to inspect by hand.
- Prefer explicit records over hidden inference.
- Preserve source citations even when data entry is manual.
- Use simple confidence language until a real scoring model exists.
- Treat contradictions as useful evidence, not errors.
- Keep the prototype separate from Phase 1 bulk ingestion.
- Do not introduce a new database, graph engine, vector store, or LLM just to
  make the prototype feel more advanced.
- The prototype proves architecture by traceability, not by automation.

## Implemented Retrieval Slice

The first coding milestone adds one CLI command:

```text
ke answer "Do GLP-1 receptor agonists reduce body weight?"
```

This command demonstrates the smallest working scientific pipeline currently
available in Knowledge Engine Core:

```text
Scientific Question
  -> Existing SQLite corpus
  -> Existing FTS index
  -> Ranked relevant papers
  -> Matching snippets
  -> Simple citations
  -> Retrieval-only disclaimer
```

### What It Does

- Accepts a natural-language scientific question.
- Converts the question into a conservative SQLite FTS query.
- Uses the existing search index and ranking behavior.
- Returns matching imported papers.
- Displays paper title.
- Displays publication year when available.
- Displays a matching abstract or text snippet.
- Explains that the paper matched indexed title, abstract, or body text.
- Displays a simple citation using title, year, and DOI when available.
- Ends with:

```text
This is retrieval only.
No scientific synthesis has been performed.
```

### What It Does Not Do

- It does not import papers.
- It does not select the corpus automatically.
- It does not extract claims.
- It does not create evidence records.
- It does not classify support, contradiction, or qualification.
- It does not synthesize scientific conclusions.
- It does not use AI, LLMs, embeddings, vector search, or a knowledge graph.

### Limitations

- Retrieval quality depends entirely on the existing SQLite FTS index.
- Natural-language questions are reduced to keyword-style FTS queries.
- Snippets are evidence-adjacent but are not evidence records.
- Citations use only metadata currently stored in the database.
- The command may retrieve papers that mention query terms without directly
  answering the question.
- The command may miss relevant papers that use different terminology.

### Architectural Meaning

This milestone proves that a scientific question can enter the system and return
traceable source material from the indexed corpus. It does not yet prove the
Evidence Layer or Reasoning Layer. The output is intentionally framed as
retrieval because no scientific synthesis has been performed.

### Next Slice

VS-2 should add a tiny curated source set and end-to-end demo data so the command
can be exercised against approximately one to ten real or generated prototype
papers. It should still avoid claim extraction, AI summarization, embeddings,
and knowledge graph construction.

## VS-4 Metadata Overlay

VS-4 adds an optional display-time metadata overlay:

```text
ke answer "Do GLP-1 receptor agonists reduce body weight in adults with overweight or obesity?" --sources data/corpora/glp1_weight_loss/sources.csv
```

When `--sources` is provided, `ke answer` loads the corpus source CSV, matches
retrieval results by DOI, and displays curated title, authors, year, journal,
source URL, and license type when available.

This is intentionally not metadata enrichment. It does not modify parser output,
database records, the database schema, or search ranking. Curated metadata is
used only for display and is labeled as coming from the corpus source file.
