# Glossary

This glossary defines core Knowledge Engine terminology. The goal is scientific
clarity, not novelty. Terms should remain stable unless a better definition is
needed for accuracy, reproducibility, or long-term maintainability.

## Principles

- Prefer precise scientific language over marketing language.
- Distinguish source material from extracted information.
- Distinguish evidence from interpretation.
- Distinguish uncertainty from error.
- Preserve provenance for anything derived from a source.
- Avoid implying that the system decides truth.

## Core Source Terms

### Source

Any original material that may contain scientific or technical knowledge.
Examples include papers, textbooks, patents, clinical trial records, public
datasets, technical documentation, standards, and government reports.

### Source Document

A file or record ingested by Knowledge Engine from a source. In Phase 0 and
Phase 1, this is usually a PDF. A source document is the concrete object being
parsed, stored, indexed, and traced.

### Paper

A scientific paper represented in the database. A paper is a type of source
document with bibliographic metadata, extracted text, and optional relationships
to authors, journals, keywords, identifiers, and future evidence records.

### Corpus

A defined collection of source documents assembled for a specific purpose,
domain, question, or release. A corpus should have documented inclusion criteria,
exclusion criteria, source provenance, and licensing expectations.

Use this term for a collection of papers.

### Collection

A user-facing grouping of source documents. A collection may be informal and
local, while a corpus should be reproducible and documented. Collections can
become corpora after scope, provenance, and inclusion rules are defined.

### Source Vault

The durable storage layer for source documents, metadata, extracted text, and
provenance. The source vault is the foundation that later evidence, graph,
search, and AI layers build on.

## Ingestion Terms

### Manifest

A structured file that declares what should be imported. A manifest should list
source document paths, source URLs, licensing information, expected identifiers,
keywords, collection or corpus membership, and schema version.

### Import Run

One execution of an ingestion workflow. An import run reads a manifest or input
set, processes each item, records outcomes, and produces an import report.

Use this term for an import as an operation.

### Import Item

One source document entry within an import run. Import items should have explicit
states such as pending, stored, duplicate skipped, failed, or ignored.

### Import Report

A human-readable and machine-readable summary of an import run. It should include
counts, failures, duplicates, skipped items, warnings, and enough context to
resume or audit the run.

### Ingestion

The overall process of bringing source documents into the Knowledge Engine. It
may include manifest validation, duplicate detection, parsing, metadata
enrichment, storage, indexing, and reporting.

### Parser

A component that reads a source document and extracts text, metadata candidates,
diagnostics, and source spans. Parsers should not decide scientific meaning and
should not write directly to durable storage.

### Parsed Document

The structured result produced by a parser from a source document. It contains
extracted text, metadata candidates, diagnostics, and references back to the
source document.

Use this term for a parsed paper in architecture documents. Code may use a more
specific type name such as `ParsedPaper` when the source document is known to be
a paper.

### Extracted Text

Text produced from a source document by a parser. Extracted text is not
guaranteed to be complete or correct; it should be tied to parser diagnostics and
source provenance.

### Parser Diagnostic

Structured information about parser behavior, warnings, failures, extraction
quality, page-level details, and uncertainty. Parser diagnostics help improve
ingestion without confusing parser output with scientific evidence.

## Metadata Terms

### Metadata

Descriptive information about a source document or scientific record. Metadata
may include title, authors, journal, publication year, DOI, keywords, source URL,
license, identifiers, and retrieval date.

Use this term for descriptive information, not scientific claims.

### Metadata Candidate

A metadata value proposed by a parser, manifest, or enrichment provider before it
is accepted as the preferred value. Candidates should preserve their source.

### Enriched Metadata

Metadata obtained or corrected from an external or secondary source such as
PubMed, Crossref, arXiv, or a curated manifest. Enriched metadata must preserve
provider provenance.

### Identifier

A stable external reference for a source or record, such as DOI, PubMed ID, arXiv
ID, ISBN, patent number, clinical trial ID, ORCID, or ISSN.

### Keyword

A human-readable label attached to a source document, corpus, or collection.
Keywords are useful for organization but are not evidence, claims, or ontology
terms unless explicitly modeled as such.

### Provenance

The recorded origin and transformation history of data. Provenance should answer
where a value came from, when it was obtained, how it was produced, and what
source or process supports it.

Use this term for traceability of sources, metadata, extracted text, evidence,
and future AI-generated outputs.

### Source Span

A precise location in a source document that supports an extracted value,
evidence record, claim, or interpretation. A source span may include page number,
character offsets, bounding boxes, section names, or quoted text within copyright
limits.

## Evidence Terms

### Claim

A statement made by a source or extracted from a source that can be evaluated
against evidence. A claim may be descriptive, causal, methodological,
statistical, or interpretive.

### Evidence

Information from one or more sources that supports, weakens, qualifies, or
contextualizes a claim. Evidence is not the same as a conclusion; it is the basis
on which conclusions may be evaluated.

### Evidence Record

A structured record that links a claim or question to supporting or opposing
evidence, source spans, methodology, limitations, and provenance.

### Method

The procedure, design, dataset, experiment, model, or analysis used to produce
evidence. Methods should be represented separately from results.

### Result

An observed, measured, computed, or reported outcome from a method. Results
should remain linked to source spans, methods, and limitations.

### Measurement

A structured observation expressed as a value, category, count, or state with
units, method, instrument, and uncertainty where applicable. A measurement is a
specialized observation, not a separate source of knowledge.

### Limitation

A stated or inferred constraint on how evidence should be interpreted. Examples
include sample size, study design, measurement limits, population scope,
confounding, missing data, or unreplicated results.

### Evidence Quality

An assessment of how strongly evidence should be weighted, based on method,
sample size, reproducibility, measurement quality, statistical rigor, and known
limitations.

Use this term instead of vague phrases such as "good evidence" when modeling
evidence strength.

### Confidence

A transparent estimate of how strongly the current evidence supports a claim,
answer, relationship, or hypothesis. Confidence must be derived from visible
factors and should never hide uncertainty or disagreement.

Use this term for confidence, not certainty.

### Uncertainty

The known incompleteness, ambiguity, variability, or unresolved disagreement in
available evidence. Uncertainty is expected in scientific knowledge and should be
shown rather than hidden.

### Consensus

The degree to which available evidence and sources agree about a claim.
Consensus should be measured or described separately from evidence quality and
confidence.

### Verified Fact

A claim that has strong evidence, clear provenance, low current contradiction,
and broad support within the represented corpus. Knowledge Engine should use this
term carefully: verified facts remain revisable when new evidence appears.

Use this term for a verified scientific fact.

## Relationship and Graph Terms

### Concept

A scientific or technical idea, entity, process, method, material, disease,
organism, variable, or phenomenon that can appear across sources.

### Relationship

A typed connection between two records, concepts, claims, sources, or evidence
items. Relationships should have direction, type, provenance, and confidence
where applicable.

Use this term for relationships generally.

### Citation

A relationship in which one source references another. Citation does not by
itself imply support, agreement, quality, or correctness.

### Support

A relationship in which evidence strengthens a claim, hypothesis, or answer.
Support should link back to source spans and evidence records.

### Contradiction

A relationship in which evidence or claims are in substantive conflict. A
contradiction may arise from different methods, populations, definitions,
measurements, assumptions, or errors.

Use this term for contradictions. Do not treat contradiction as failure;
contradictions often identify research opportunities.

### Qualification

A relationship in which evidence narrows, limits, or contextualizes a claim
without directly supporting or contradicting it.

### Knowledge Graph

A graph of concepts, sources, claims, evidence, and typed relationships with
provenance. The knowledge graph should represent traceable scientific structure,
not just semantic similarity.

## Question and Discovery Terms

### Research Question

A question that can guide evidence gathering, analysis, or future investigation.
A research question should be specific enough to connect to sources, concepts,
claims, or evidence records.

Use this term for a research question.

### Unknown

A documented gap in current knowledge. Unknowns may include missing experiments,
weak evidence areas, unresolved contradictions, absent data, or questions outside
the current corpus.

### Discovery

A newly identified, evidence-grounded connection, pattern, contradiction,
question, or hypothesis that may help humans understand or investigate a
scientific problem. A discovery is not automatically a verified fact.

Use this term for a discovery.

### Hypothesis

A proposed explanation, relationship, mechanism, or prediction that requires
further evaluation. A hypothesis may be human-authored or AI-generated.

### Generated Hypothesis

An AI-generated or system-generated hypothesis. It must include provenance for
the inputs and reasoning steps that produced it, and it should be treated as a
research lead rather than a conclusion.

Use this term for an AI-generated hypothesis.

### Finding

A concise statement of what the system or a human reviewer observed in the
available sources. A finding should cite evidence and indicate confidence.

### Insight

A human-facing interpretation of evidence, relationships, or findings. Insights
should be traceable and should not be stored as ungrounded assertions.

## Reasoning Terms

### Reasoning

The process of connecting claims, evidence, relationships, assumptions, and
uncertainty to produce an answer, finding, hypothesis, or recommendation.

Use this term for reasoning. Reasoning must be inspectable when used in the
Knowledge Engine.

### Reasoning Trace

A recorded explanation of the evidence, assumptions, intermediate steps, and
uncertainty involved in reasoning. A reasoning trace should allow a human to
audit how an output was produced.

### Answer

A response to a user question or research question. An answer should include
sources, evidence, uncertainty, and confidence when it goes beyond simple
document retrieval.

### Recommendation

A suggested next action, source, experiment, query, or investigation. A
recommendation should be justified by evidence or workflow context and should
not be treated as a decision made by the system.

## Search and Retrieval Terms

### Lexical Search

Search based on exact words, phrases, tokens, or related textual matching.
SQLite FTS5 provides lexical search in Phase 0.

### Semantic Search

Search based on meaning or learned representations rather than exact words.
Semantic search is future work and should remain traceable to source documents.

### Ranking

The ordering of search results, evidence, claims, or recommendations. Ranking
must be documented enough that users understand the main factors affecting order.

### Index

A data structure optimized for retrieval. In Phase 0, the FTS5 index supports
lexical search over source text and metadata.

## System and Workflow Terms

### Module

A focused part of the codebase with a clear responsibility, such as parsing,
persistence, search, configuration, or command-line interaction.

### Adapter

A component that connects Knowledge Engine to a specific parser, metadata
provider, storage backend, or external service while preserving a stable
internal interface.

### Provider

An external or internal source of metadata, identifiers, evidence, or enrichment
data. Examples include PubMed, Crossref, local manifests, and future institutional
repositories.

### Repository

A persistence abstraction that stores and retrieves domain records. In code,
repository classes should protect callers from unnecessary database details.

### Migration

A controlled change to the database schema or stored data format. Migrations
should be versioned, reversible where practical, and documented.

### Reproducible Ingestion

An ingestion process that can be rerun or audited using the same manifest,
source documents, configuration, and code version to understand what was
imported and why.

## Preferred Term Summary

- Collection of papers: `Corpus` when reproducible and scoped; `Collection` when
  informal.
- Import: `Import Run`.
- Parsed paper: `Parsed Document` or code-specific `ParsedPaper`.
- Metadata: `Metadata`.
- Evidence: `Evidence` or `Evidence Record`.
- Relationships: `Relationship`, with specific types such as `Citation`,
  `Support`, `Contradiction`, and `Qualification`.
- Confidence: `Confidence`.
- Provenance: `Provenance`.
- Reasoning: `Reasoning`.
- AI-generated hypothesis: `Generated Hypothesis`.
- Verified scientific fact: `Verified Fact`.
- Contradiction: `Contradiction`.
- Research question: `Research Question`.
- Discovery: `Discovery`.
