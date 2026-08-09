# Future AI Orchestration Plan

**Superseded by the canonical document.** The real, full plan (1,056
lines, team-authored) lives at `knowledge-engine-ai`'s
`docs/roadmap/future_ai_orchestration_plan.md`
(https://github.com/jweter/knowledge-engine-ai/pull/7 at time of
writing, pending merge). This file previously held a reconstruction
drafted from a written relay when the original download link did not
resolve; that reconstruction has been reviewed against the real
document and retired here to avoid two divergent copies of the same
plan living in two repos. Read the canonical document in the `ai`
repo, not this stub.

## What the real document adds beyond this repo's reconstruction

For continuity with anyone who read the earlier version of this file:
the real document is substantially more complete. It defines full
field-level schemas for `ResearchPlan`, `ResearchSession`,
`ResearchEvent`, `EvidenceComparison`, `KnowledgeGap`, and
`HypothesisCandidate`; a Tool Permission Model with five numbered
consequence levels; a four-layer Verification Pipeline (Structural,
Grounding, Contradiction, Citation); an Evaluation Framework across
Retrieval/Extraction/Synthesis/Workflow/Adversarial dimensions;
explicit success criteria on every `AI-O1`-`AI-O11` milestone; a
"What Not to Build" list; and all 16 named design-risk blocks (this
repo's earlier reconstruction, drafted before the real file was
available, was missing two: non-deterministic research continuation,
and autonomous hypothesis generation outrunning evidence quality).

## Relationship to `knowledge-engine-core`

The real document's own "Relationship to the Existing Knowledge
Engine" section restates this project's already-established package
boundary: `core` owns ingestion, provenance, Evidence Records, graph
data, and deterministic checks; `ai` owns the Research Copilot and
orchestration layer; `web` remains presentation. This is consistent
with `docs/ai_layer_architecture.md`'s "one rule that does not
change" and its own "Orchestration: a multi-agent pattern for the
Research Copilot" section, which readers should treat as this
repo's account of the same evolving thinking -- not a competing plan.

## Real gate, unchanged

As stated in both documents: the real blocker is evidence-base
thickness, not architecture. As of this note, GLP-1 has the only
externally-audited golden map; oncology has a small,
same-session-self-audited reviewed layer (growing -- see
`data/corpora/oncology_nsclc_checkpoint_inhibitors/README.md`);
mental-health has none. `AI-O1`-`AI-O3` in the real document's roadmap
do not require more evidence coverage to build (they wire existing
tools); later milestones benefit substantially from it.
