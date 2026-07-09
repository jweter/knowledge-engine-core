# Scientific Data Model

This document defines the canonical conceptual data model for the Knowledge
Engine. It is not a database schema, ORM model, API contract, or storage design.
It describes what the system means when it talks about scientific knowledge.

The model should remain useful across chemistry, biology, medicine, physics,
materials science, engineering, mathematics, and domains that are not yet part of
the project.

## Design Premises

- Treat `Paper` as a source object, not the whole knowledge model.
- Store scientific knowledge independently of any particular storage technology,
  index, graph database, vector database, or AI model.
- Distinguish source material from extracted information.
- Distinguish evidence from interpretation.
- Distinguish uncertainty from error.
- Preserve provenance for every derived object.
- Never make a storage representation synonymous with knowledge.
- Never let the system decide truth; let it organize evidence, disagreement,
  uncertainty, and traceable conclusions for human review.

## Model Layers

The conceptual model has five layers:

1. Source Layer: materials that contain scientific information.
2. Extraction Layer: structured information derived from sources.
3. Evidence Layer: observations, results, methods, claims, and support.
4. Relationship Layer: typed links among sources, concepts, claims, and evidence.
5. Reasoning Layer: questions, hypotheses, confidence, consensus, and discovery.

Each layer depends on the layers below it, but no layer is reducible to one
database technology or AI system.

## Core Objects

### Source

Purpose:
A `Source` is any original material that may contain scientific, technical, or
methodological knowledge.

Required properties:
- Stable source identifier within the Knowledge Engine.
- Source type.
- Provenance.
- Access or acquisition context.

Optional properties:
- External identifiers.
- License or usage information.
- Publisher, institution, repository, or owner.
- Version.
- Access date.
- Language.
- Domain tags.

Relationships to other objects:
- Contains or references `Document` objects.
- May originate `Dataset`, `Protocol`, `Patent`, or other source-specific
  objects.
- Provides provenance for extracted `Claim`, `Observation`, `Evidence`, and
  `Metadata`.

Lifecycle:
Discovered, evaluated for inclusion, acquired or referenced, ingested, parsed,
indexed, enriched, versioned, and possibly deprecated or superseded.

Examples:
- A journal article.
- A PDF preprint.
- A clinical trial registry record.
- A patent filing.
- A public dataset.
- A laboratory protocol.
- A technical standard.

Why it exists:
The Knowledge Engine must represent where knowledge came from before it can
represent what the knowledge says. Sources are carriers of knowledge, not the
knowledge model itself.

### Document

Purpose:
A `Document` is a concrete textual, visual, tabular, or mixed representation of
a source that can be parsed, stored, indexed, or cited.

Required properties:
- Document identifier.
- Source reference.
- Document type.
- Location or storage reference.
- Content fingerprint where applicable.
- Provenance.

Optional properties:
- File format.
- Page count.
- Text extraction status.
- Language.
- Version.
- Parser diagnostics.
- Checksums.

Relationships to other objects:
- Belongs to a `Source`.
- May contain `Claims`, `Methods`, `Results`, `Observations`, figures, tables,
  citations, and references.
- May be represented by extracted text and source spans.

Lifecycle:
Registered, parsed, validated, indexed, reparsed if parser quality improves, and
possibly superseded by a newer version.

Examples:
- A PDF file for a paper.
- JATS XML for an article.
- HTML documentation.
- A patent PDF.
- A dataset README.

Why it exists:
The same source may have multiple document representations. The model needs a
clear boundary between the intellectual source and the file or record being
processed.

### Paper

Purpose:
A `Paper` is a scholarly source that reports, reviews, analyzes, or argues about
scientific or technical knowledge.

Required properties:
- Source identifier.
- Title or title candidate.
- Authorship or authorship status.
- Publication or release context.
- Provenance.

Optional properties:
- DOI.
- Abstract.
- Journal or venue.
- Publication date.
- Keywords.
- References.
- Full text.
- Figures and tables.
- Funding information.
- Retraction or correction status.

Relationships to other objects:
- Is a specialized `Source`.
- May have one or more `Documents`.
- May contain `Claims`, `Methods`, `Results`, `Observations`, and references.
- May cite other `Sources`.
- May support or contradict other claims.

Lifecycle:
Discovered, ingested, parsed, enriched, linked to identifiers, connected to
evidence records, and possibly corrected, retracted, superseded, or versioned.

Examples:
- A journal research article.
- A preprint.
- A review article.
- A conference paper.

Why it exists:
Papers are central scientific carriers today, but they are not the entire
knowledge model. Treating them as a source type prevents the architecture from
becoming paper-bound.

### Dataset

Purpose:
A `Dataset` is a structured or semi-structured collection of observations,
measurements, records, simulations, or derived values used as scientific input
or output.

Required properties:
- Dataset identifier.
- Source or repository reference.
- Provenance.
- Scope description.
- Access or license status.

Optional properties:
- Schema or variable definitions.
- Units.
- Collection method.
- Version.
- Size.
- File formats.
- Quality notes.
- Missingness information.

Relationships to other objects:
- May be a `Source`.
- May be used by an `Experiment`, `Method`, or `Claim`.
- May contain `Observations` or `Measurements`.
- May support `Evidence`.
- May be derived from other datasets.

Lifecycle:
Discovered, acquired or referenced, validated, versioned, linked to methods and
claims, and possibly superseded.

Examples:
- Gene expression matrix.
- Clinical trial participant table.
- Materials property dataset.
- Simulation output.
- Survey dataset.

Why it exists:
Many scientific conclusions depend on data that is not fully represented by a
paper. Datasets must be first-class knowledge carriers.

### Protocol

Purpose:
A `Protocol` is a documented procedure for producing observations, measurements,
experiments, analyses, or artifacts.

Required properties:
- Protocol identifier.
- Procedure description or reference.
- Provenance.
- Intended purpose.

Optional properties:
- Materials.
- Instruments.
- Parameters.
- Preconditions.
- Step order.
- Version.
- Validation status.
- Safety or ethical constraints.

Relationships to other objects:
- May be a `Source`.
- Defines or informs a `Method`.
- May be used by an `Experiment`.
- May qualify `Evidence` by describing how it was produced.

Lifecycle:
Registered, versioned, applied, evaluated, modified, and possibly superseded.

Examples:
- Laboratory assay protocol.
- Computational analysis pipeline.
- Clinical measurement protocol.
- Engineering test procedure.

Why it exists:
Scientific evidence depends not only on results, but on how results were
produced. Protocols preserve procedural context.

### Patent

Purpose:
A `Patent` is a legal and technical source that describes an invention, method,
composition, device, or process.

Required properties:
- Patent identifier.
- Jurisdiction or issuing authority.
- Filing or publication context.
- Provenance.

Optional properties:
- Inventors.
- Assignee.
- Claims.
- Citations.
- Legal status.
- Priority date.
- Classification codes.

Relationships to other objects:
- Is a specialized `Source`.
- May contain technical `Claims`, `Methods`, `Concepts`, and references.
- May relate to papers, datasets, protocols, or products.

Lifecycle:
Discovered, ingested, parsed, linked to identifiers and citations, and updated
as legal status changes.

Examples:
- Drug formulation patent.
- Battery materials patent.
- Manufacturing process patent.

Why it exists:
Important scientific and technical knowledge often appears first or only in
patents. The model must support technical knowledge outside academic publishing.

### Experiment

Purpose:
An `Experiment` is a planned or described intervention, observation, simulation,
analysis, or test intended to produce evidence about a question or hypothesis.

Required properties:
- Experiment identifier.
- Method or protocol reference.
- Scientific question or hypothesis context.
- Provenance.

Optional properties:
- Variables.
- Conditions.
- Controls.
- Population or system.
- Instruments.
- Parameters.
- Dataset inputs.
- Results.
- Limitations.

Relationships to other objects:
- Tests a `Hypothesis` or addresses a `Scientific Question`.
- Uses a `Method` or `Protocol`.
- Produces `Observations`, `Measurements`, and `Results`.
- Contributes to `Evidence`.

Lifecycle:
Proposed, designed, conducted or simulated, reported, interpreted, replicated,
revised, or invalidated.

Examples:
- Randomized clinical trial.
- Chemical synthesis and assay.
- Materials stress test.
- Physics detector run.
- Computational simulation.

Why it exists:
Experiments connect methods, observations, and hypotheses. They make evidence
more than isolated statements.

### Observation

Purpose:
An `Observation` is a recorded perception, measurement, event, state, output, or
result under specified conditions.

Required properties:
- Observation identifier.
- What was observed.
- Context or conditions.
- Provenance.

Optional properties:
- Measurement value.
- Unit.
- Instrument.
- Uncertainty or error estimate.
- Time.
- Location.
- Subject or system.
- Method reference.
- Quality flags.

Relationships to other objects:
- May be produced by an `Experiment`.
- May be contained in a `Dataset`.
- May support, weaken, or qualify a `Claim`.
- May become part of an `Evidence Record`.

Lifecycle:
Recorded, validated, normalized, linked to method and source, aggregated,
reinterpreted, or rejected.

Examples:
- Blood glucose measurement.
- Crystal structure parameter.
- Battery capacity after cycles.
- Particle collision event.
- Survey response.

Why it exists:
Observations are among the smallest direct inputs to scientific knowledge. They
anchor evidence in recorded experience or measurement.

### Measurement

Purpose:
A `Measurement` is a structured `Observation` expressed as a value, category,
count, or state under specified conditions.

Required properties:
- Measurement identifier.
- Observed subject or system.
- Value or recorded state.
- Method or instrument context.
- Provenance.

Optional properties:
- Unit.
- Reference range.
- Calibration information.
- Detection limit.
- Uncertainty or error estimate.
- Time.
- Location.
- Quality flags.

Relationships to other objects:
- Is a specialized `Observation`.
- May be produced by an `Experiment`.
- May be contained in a `Dataset`.
- May contribute to `Evidence`.
- May be summarized by a `Result`.

Lifecycle:
Recorded, validated, normalized, converted, linked to source and method,
aggregated, reanalyzed, or rejected.

Examples:
- Blood glucose of 94 mg/dL measured by a named assay.
- Tensile strength of 620 MPa for a material sample.
- Gene expression count for a sample and transcript.
- Temperature recorded during a reaction.

Why it exists:
Many scientific domains require structured values with units and uncertainty.
Representing measurement as a specialized observation keeps the model general
while preserving enough structure for quantitative science.

### Claim

Purpose:
A `Claim` is a statement that can be evaluated against evidence.

Required properties:
- Claim identifier.
- Claim text or normalized representation.
- Claim type.
- Provenance.

Optional properties:
- Scope.
- Conditions.
- Population or system.
- Variables.
- Source span.
- Confidence.
- Status.
- Related concepts.

Relationships to other objects:
- May be extracted from a `Document`.
- May be supported, contradicted, or qualified by `Evidence`.
- May address a `Scientific Question`.
- May relate to other claims.
- May be part of a `Consensus` assessment.

Lifecycle:
Extracted or authored, normalized, linked to evidence, reviewed, revised,
qualified, supported, contradicted, deprecated, or treated as provisionally
verified.

Examples:
- "Compound X inhibits enzyme Y under condition Z."
- "GLP-1 receptor agonists reduce body weight in adults with obesity."
- "This alloy has higher tensile strength after heat treatment."

Why it exists:
Claims are evaluable units of scientific meaning. They are not automatically
true; they are objects that evidence can act upon.

### Evidence

Purpose:
`Evidence` is information that supports, weakens, contradicts, qualifies, or
contextualizes a claim, hypothesis, answer, or question.

Required properties:
- Evidence identifier.
- Evidence type.
- Source or provenance reference.
- Relationship to the claim, hypothesis, or question it bears on.

Optional properties:
- Evidence quality.
- Method reference.
- Observation or result references.
- Source span.
- Limitations.
- Confidence contribution.
- Reviewer notes.

Relationships to other objects:
- Originates from `Sources`, `Documents`, `Datasets`, `Experiments`, or
  `Observations`.
- Supports, contradicts, or qualifies `Claims`.
- Contributes to `Consensus`.
- Informs `Reasoning`.

Lifecycle:
Identified, structured, linked to source spans, evaluated for quality, reviewed,
updated, superseded, or invalidated.

Examples:
- A reported trial result.
- A measurement table.
- A replicated experimental result.
- A statistical association with method details.

Why it exists:
Evidence is the core bridge between source material and scientific knowledge.
The system should reason from evidence, not from authority or popularity.

### Evidence Record

Purpose:
An `Evidence Record` is a structured representation of evidence and its
connection to a claim, question, hypothesis, or relationship.

Required properties:
- Evidence record identifier.
- Evidence reference.
- Target object.
- Relationship type.
- Provenance.

Optional properties:
- Evidence quality.
- Confidence contribution.
- Limitations.
- Reviewer status.
- Source spans.

Relationships to other objects:
- Links `Evidence` to `Claims`, `Hypotheses`, `Questions`, or `Relationships`.
- May be used in `Consensus` and `Confidence` calculations.

Lifecycle:
Created, reviewed, updated, combined with other records, deprecated, or
superseded.

Examples:
- A trial result supporting a treatment-effect claim.
- A replication failure contradicting a mechanism claim.
- A dataset limitation qualifying a population-level claim.

Why it exists:
The same evidence can bear on multiple claims in different ways. Evidence
records preserve that context.

### Provenance

Purpose:
`Provenance` records where an object came from, how it was produced, when it was
produced or obtained, and what process or source supports it.

Required properties:
- Origin reference.
- Producing process or actor.
- Time or version context.
- Trace to source or prior object.

Optional properties:
- Tool version.
- Parser version.
- Metadata provider.
- Human reviewer.
- Transformation steps.
- Confidence in provenance.

Relationships to other objects:
- Applies to every derived object.
- Connects claims, metadata, evidence, reasoning, and hypotheses back to sources.

Lifecycle:
Created with the object it describes, extended when transformations occur,
audited, corrected, or invalidated.

Examples:
- DOI came from Crossref on a specific date.
- Abstract came from a parser with a specific version.
- Claim came from page 4, paragraph 2 of a paper.
- Hypothesis came from a reasoning process over specified evidence records.

Why it exists:
Without provenance, the Knowledge Engine cannot be transparent, reproducible, or
scientifically trustworthy.

### Metadata

Purpose:
`Metadata` describes a source, document, object, or record without itself being a
scientific claim.

Required properties:
- Metadata field name.
- Value.
- Subject object.
- Provenance.

Optional properties:
- Confidence.
- Provider.
- Field-level status.
- Normalized value.
- Original value.

Relationships to other objects:
- Describes `Sources`, `Documents`, `Datasets`, `Papers`, `Patents`,
  `Protocols`, and other records.
- May have multiple candidates from different providers.

Lifecycle:
Parsed, imported from manifest, enriched, normalized, reviewed, corrected, or
superseded.

Examples:
- Title.
- Author list.
- DOI.
- Journal.
- License.
- Retrieval date.

Why it exists:
Metadata makes scientific sources discoverable and auditable, but it should not
be confused with evidence or knowledge claims.

### Relationship

Purpose:
A `Relationship` is a typed connection between two conceptual objects.

Required properties:
- Relationship identifier.
- Source object.
- Target object.
- Relationship type.
- Provenance.

Optional properties:
- Direction.
- Confidence.
- Evidence references.
- Valid time range.
- Qualifiers.
- Reviewer status.

Relationships to other objects:
- Connects any compatible model objects.
- May itself be supported or contradicted by `Evidence`.
- May participate in a `Knowledge Graph`.

Lifecycle:
Created, supported, contradicted, qualified, reviewed, versioned, or deprecated.

Examples:
- Paper cites paper.
- Evidence supports claim.
- Claim contradicts claim.
- Concept is related to concept.
- Experiment tests hypothesis.

Why it exists:
Scientific knowledge depends on connections. Relationships make those
connections explicit and auditable.

### Concept

Purpose:
A `Concept` is a scientific, technical, mathematical, or methodological idea or
entity that can appear across sources and claims.

Required properties:
- Concept identifier.
- Preferred label.
- Concept type.
- Provenance or curation source.

Optional properties:
- Synonyms.
- Definitions.
- External ontology identifiers.
- Domain.
- Parent or related concepts.
- Ambiguity notes.

Relationships to other objects:
- Connects to `Claims`, `Sources`, `Evidence`, `Questions`, and other concepts.
- May be part of ontologies or knowledge graphs.

Lifecycle:
Proposed, normalized, linked to external vocabularies, merged, split, deprecated,
or reviewed.

Examples:
- GLP-1.
- Entropy.
- Tensile strength.
- Randomized controlled trial.
- Lithium-ion battery.

Why it exists:
Concepts let the system connect knowledge across documents, disciplines,
languages, and representations.

### Scientific Question

Purpose:
A `Scientific Question` is a question that can guide evidence gathering,
analysis, experimentation, or reasoning.

Required properties:
- Question identifier.
- Question text or normalized representation.
- Scope.
- Provenance.

Optional properties:
- Related concepts.
- Related claims.
- Status.
- Priority.
- Domain.
- Known unknowns.
- Candidate hypotheses.

Relationships to other objects:
- Generates or organizes `Hypotheses`.
- Is addressed by `Claims`, `Evidence`, and `Experiments`.
- May emerge from `Contradictions` or gaps.

Lifecycle:
Proposed, scoped, linked to evidence, refined, partially answered, reopened, or
retired.

Examples:
- What mechanisms regulate appetite after GLP-1 treatment?
- Which materials retain capacity under high-temperature cycling?
- Does method A outperform method B under condition C?

Why it exists:
Questions organize inquiry. They prevent the model from becoming only a passive
archive of statements.

### Hypothesis

Purpose:
A `Hypothesis` is a proposed explanation, relationship, mechanism, or prediction
that requires evaluation.

Required properties:
- Hypothesis identifier.
- Hypothesis statement.
- Provenance.
- Testability or evaluation context.

Optional properties:
- Generated or human-authored status.
- Related question.
- Related concepts.
- Supporting evidence.
- Contradicting evidence.
- Confidence.
- Proposed tests.

Relationships to other objects:
- May answer or refine a `Scientific Question`.
- May be tested by `Experiments`.
- May be supported or contradicted by `Evidence`.
- May become a `Claim` if asserted by a source or reviewer.

Lifecycle:
Proposed, evaluated, tested, supported, contradicted, refined, rejected, or
converted into a claim with evidence.

Examples:
- A mechanism proposed to explain a biological pathway.
- A predicted relationship between processing temperature and material strength.
- An AI-generated cross-disciplinary analogy requiring human evaluation.

Why it exists:
The Knowledge Engine should help generate research leads while making clear that
hypotheses are not conclusions.

### Contradiction

Purpose:
A `Contradiction` is a substantive conflict among claims, evidence, results, or
interpretations.

Required properties:
- Contradiction identifier.
- Conflicting objects.
- Conflict type.
- Provenance.

Optional properties:
- Possible explanation.
- Related methods.
- Related populations or conditions.
- Severity.
- Status.
- Reviewer notes.

Relationships to other objects:
- Connects conflicting `Claims`, `Evidence`, `Results`, or `Relationships`.
- May generate `Scientific Questions` or `Hypotheses`.
- May affect `Consensus` and `Confidence`.

Lifecycle:
Detected, reviewed, classified, investigated, resolved, narrowed, or left open.

Examples:
- Two studies report opposite treatment effects.
- A replication fails under similar conditions.
- A patent claim conflicts with later empirical evidence.

Why it exists:
Contradictions are not failures of the system. They are high-value signals for
uncertainty, boundary conditions, and discovery.

### Consensus

Purpose:
`Consensus` describes the degree and structure of agreement among evidence,
claims, and sources about a question or claim.

Required properties:
- Consensus subject.
- Evidence set or corpus scope.
- Assessment method.
- Time or version context.
- Provenance.

Optional properties:
- Agreement level.
- Disagreement level.
- Evidence quality summary.
- Confidence.
- Minority positions.
- Domain or population scope.

Relationships to other objects:
- Aggregates `Evidence Records`.
- Applies to `Claims`, `Questions`, `Hypotheses`, or `Relationships`.
- Changes over time as new evidence appears.

Lifecycle:
Computed or reviewed, updated, versioned, strengthened, weakened, split by
subdomain, or superseded.

Examples:
- Broad agreement that a treatment reduces a measured outcome in a population.
- Weak consensus because evidence quality is low.
- Consensus that differs between animal models and human studies.

Why it exists:
Scientific knowledge is often collective and provisional. Consensus helps users
see the state of evidence without pretending uncertainty has disappeared.

### Confidence

Purpose:
`Confidence` is a transparent estimate of how strongly current evidence supports
an object, relationship, answer, hypothesis, or consensus assessment.

Required properties:
- Subject.
- Basis.
- Assessment method.
- Provenance.

Optional properties:
- Numeric score.
- Qualitative category.
- Evidence quality components.
- Uncertainty notes.
- Reviewer notes.
- Time context.

Relationships to other objects:
- Depends on `Evidence`, `Evidence Quality`, `Consensus`, `Contradictions`, and
  provenance.
- Applies to `Claims`, `Relationships`, `Hypotheses`, `Answers`, and
  `Consensus`.

Lifecycle:
Estimated, reviewed, recalculated, revised, invalidated, or versioned.

Examples:
- High confidence in a well-replicated measurement.
- Low confidence in a single small study.
- Moderate confidence with important population limitations.

Why it exists:
Users need to see strength of support without confusing confidence with truth or
certainty.

### Uncertainty

Purpose:
`Uncertainty` represents known incompleteness, ambiguity, variability, or
unresolved disagreement.

Required properties:
- Subject.
- Uncertainty type.
- Basis.
- Provenance.

Optional properties:
- Magnitude.
- Range.
- Source of uncertainty.
- Reducibility.
- Related questions.
- Related contradictions.

Relationships to other objects:
- Applies to observations, claims, evidence, relationships, hypotheses,
  confidence, and consensus.
- May generate `Scientific Questions`.
- May reduce or qualify `Confidence`.

Lifecycle:
Identified, characterized, reduced, reframed, increased by new evidence, or
accepted as inherent.

Examples:
- Measurement error.
- Conflicting study results.
- Missing population data.
- Ambiguous terminology.
- Unknown mechanism.

Why it exists:
Uncertainty is part of science. The system should make uncertainty visible
rather than hiding it behind single answers.

## Relationship Model

Relationships should be typed, directional when appropriate, and traceable to
provenance. A relationship may also have evidence, confidence, uncertainty, and a
valid time range.

Core relationships:

- `Source contains Document`.
- `Source specializes as Paper`, `Dataset`, `Protocol`, or `Patent`.
- `Document represents Source`.
- `Document contains Claim`.
- `Document contains Method`.
- `Document contains Result`.
- `Document contains Observation`.
- `Dataset contains Observation`.
- `Measurement specializes Observation`.
- `Protocol defines Method`.
- `Experiment uses Protocol`.
- `Experiment applies Method`.
- `Experiment tests Hypothesis`.
- `Experiment addresses Scientific Question`.
- `Experiment produces Observation`.
- `Experiment produces Measurement`.
- `Observation contributes to Evidence`.
- `Measurement contributes to Evidence`.
- `Result summarizes Observation`.
- `Claim is supported by Evidence`.
- `Claim is contradicted by Evidence`.
- `Claim is qualified by Evidence`.
- `Evidence originates from Source`.
- `Evidence Record links Evidence to Claim`.
- `Concept appears in Source`.
- `Concept connects Claims`.
- `Relationship connects Concepts`.
- `Scientific Question generates Hypothesis`.
- `Hypothesis is tested by Experiment`.
- `Hypothesis is supported by Evidence`.
- `Hypothesis is contradicted by Evidence`.
- `Contradiction connects conflicting Claims or Evidence`.
- `Contradiction generates Scientific Question`.
- `Evidence contributes to Consensus`.
- `Consensus changes over time`.
- `Confidence summarizes support for a subject`.
- `Uncertainty qualifies Confidence`.
- `Provenance traces every derived object to its origin`.

## ASCII Architecture Diagram

```text
                           Scientific Question
                                   |
                                   v
                              Hypothesis
                                   |
                             tested by
                                   v
Source ---- contains ----> Document ---- contains ----> Claim
  |                            |                         |
  |                            |                         |
  |                            v                         v
  |                        Source Span              Relationship
  |                            |                         |
  |                            v                         v
  |                         Metadata                 Concept
  |
  +-- specializes as --> Paper
  +-- specializes as --> Dataset ---- contains ----> Observation
  |                                                   |
  |                                             specializes as
  |                                                   v
  |                                             Measurement
  +-- specializes as --> Protocol ---- defines ----> Method
  +-- specializes as --> Patent
                                      |
                                      v
                                Experiment
                                      |
                                  produces
                                      v
                                Observation
                                      |
                               contributes to
                                      v
                                  Evidence
                                      |
             +------------------------+------------------------+
             |                        |                        |
          supports                contradicts              qualifies
             |                        |                        |
             v                        v                        v
           Claim                Contradiction                Claim
             |
             v
      Evidence Record
             |
             v
         Consensus <--------- Evidence Set --------- Evidence
             |
             v
        Confidence
             ^
             |
        Uncertainty

Every derived object has Provenance.
Every reasoning output should be traceable to Evidence and Source.
```

## Design Critique

### 10 Biggest Weaknesses

1. The model is broad enough to risk becoming too abstract for Phase 1.
2. The boundary between `Claim`, `Finding`, and `Result` will need practical
   examples before implementation.
3. `Evidence` is powerful but may become overloaded unless evidence types are
   refined.
4. `Consensus` may be difficult to model fairly across disciplines.
5. `Confidence` may invite false precision if reduced to a single score.
6. `Concept` normalization can become a major ontology problem.
7. Mathematical knowledge may not fit cleanly into observation-centered models.
8. Engineering and design knowledge may require artifact and constraint objects.
9. Patent claims and scientific claims use the same word "claim" differently.
10. The model does not yet specify governance for human review and correction.

### 10 Biggest Assumptions

1. Scientific knowledge can be usefully represented as linked conceptual
   objects.
2. Provenance can be captured well enough to support trust.
3. Most domains can share common objects such as source, claim, evidence, method,
   observation, and relationship.
4. Claims can be separated from evidence in a stable way.
5. Evidence quality can be represented transparently across domains.
6. Concepts can be normalized without destroying important context.
7. Consensus can be represented without implying final truth.
8. Future AI systems can operate over traceable evidence rather than opaque
   summaries.
9. Users will value uncertainty and provenance enough to tolerate added
   complexity.
10. The model can evolve without breaking early corpora if versioning and
    migrations are handled carefully.

### 10 Concepts Most Likely to Evolve

1. Evidence
2. Evidence Quality
3. Confidence
4. Consensus
5. Concept
6. Claim
7. Observation
8. Method
9. Provenance
10. Relationship

## Smallest Indivisible Unit of Scientific Knowledge

The smallest indivisible unit of scientific knowledge is probably not a paper.
A paper is a container. It is also probably not always a claim, because claims
can be broad, compound, interpretive, or unsupported.

Several candidates matter:

### Observation

An observation is close to atomic because it records something under conditions.
It is often the smallest direct contact with reality. But an observation without
method, context, unit, or provenance is not enough to be scientific knowledge.

### Measurement

A measurement is an observation with value, unit, instrument, and method. It is
highly structured and often atomic in experimental sciences. But not all fields
produce measurements, and not all knowledge is numerical.

### Claim

A claim is atomic in argument and reasoning. It can be supported or contradicted.
But claims may be too interpretive to be the smallest unit, and many claims are
composed from multiple observations or results.

### Result

A result summarizes observations produced by a method. It is often what papers
report and what evidence records use. But a result may aggregate many
measurements and statistical choices.

### Evidence Statement

An evidence statement links an observation or result to a claim under a method
and provenance. It is not merely data and not merely assertion. It says, in
effect, "this evidence bears on that claim in this way."

### Proposed Answer

The smallest indivisible unit of scientific knowledge should be treated as an
`Evidence Statement`:

```text
Under a specified method and context, this observation or result bears on this
claim or question in this way, with this provenance and uncertainty.
```

This is small enough to be traceable, testable, and composable. It is also rich
enough to remain scientific rather than becoming an isolated number or sentence.

In implementation terms, this likely corresponds to an `Evidence Record`, but
conceptually the indivisible unit is the evidence-bearing statement: a link among
observation/result, method/context, claim/question, provenance, and uncertainty.

This answer should remain open to revision. Some domains may need specialized
atomic units, especially mathematics, engineering design, and computational
simulation. But for a general scientific knowledge infrastructure, the evidence
statement is the best current candidate.
