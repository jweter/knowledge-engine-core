# Oncology Corpus Scoping

## Decision

`docs/roadmap.md`'s "Decision: domain diversification beyond GLP-1"
(2026-08-08) records the project owner's decision to add a second,
unrelated research domain alongside continued GLP-1 depth work: a
single-domain corpus risks looking like infrastructure built to promote one
drug class rather than general-purpose scientific infrastructure.

## Chosen question

**Do immune checkpoint inhibitors (anti-PD-1/PD-L1) improve overall
survival in adults with advanced non-small-cell lung cancer (NSCLC)?**

See `data/corpora/oncology_nsclc_checkpoint_inhibitors/scientific_question.md`
for the full question frame (population, intervention, comparator, outcomes,
subtopics, and explicit out-of-scope boundaries) and
`knowledge_engine/scientific_scope.py`'s `ONCOLOGY_NSCLC_CHECKPOINT_SCOPE`
for the exact deterministic scope-matching vocabulary.

## Why this pairing, not oncology broadly

Mirrors the GLP-1 corpus's own shape and the same lesson its
`scientific_question.md` already documents: a corpus too narrow to reliably
supply a legally-reusable full-text sample is as much a failure mode as one
too broad to be evidence-map-defensible. "Cancer" or "immunotherapy" alone
would be too broad -- thousands of disparate cancer types, drug classes, and
endpoints with no coherent single evidence map possible. A single named
population/intervention pair, matching GLP-1's original "GLP-1 receptor
agonists and weight loss" framing, is the shape that has actually worked
here before.

Advanced NSCLC with anti-PD-1/PD-L1 checkpoint inhibitors was picked over
other oncology candidates considered (see "Alternatives considered" below)
because it has the closest evidence shape to the GLP-1 corpus:

- Large, well-known randomized controlled trials exist (the KEYNOTE,
  CheckMate, and IMpower trial families), comparable in scale and public
  recognizability to STEP/SELECT for GLP-1.
- A clear comparator arm (chemotherapy or placebo) in essentially every
  landmark trial.
- Clear, quantitative primary endpoints (overall survival, progression-free
  survival) -- the same shape `ke statistical-verify`'s typed
  statistical-input schema (built for GLP-1's STEP 5/SELECT records) already
  expects, so no new statistical-verification architecture should be needed,
  only new typed inputs.
- Substantial PMC/Europe PMC/CORE open-access coverage expected, given how
  heavily immuno-oncology has been published in the last decade -- reduces
  the risk of a too-thin corpus, the same risk that made the original GLP-1
  question widen to the broader metabolic-disease frame (see
  `data/corpora/glp1_weight_loss/scientific_question.md`'s own rationale).

## Alternatives considered

- **Cardiovascular disease**: also a strong candidate (large RCT base,
  comparable evidence shape), but closer conceptually to GLP-1's own
  metabolic-disease scope (semaglutide/tirzepatide already have
  cardiovascular-outcome trials in the GLP-1 corpus) -- less effective at
  demonstrating the platform generalizes to a genuinely different field.
- **Mental health / neuropsychiatric**: genuinely distant from GLP-1, but
  evidence in this field is more heterogeneous in outcome measures
  (symptom-scale scores vary by instrument, less standardized than survival
  endpoints), which would likely require new statistical-verification work
  before a golden map could be as rigorous as GLP-1's. Reasonable future
  third domain, not the first choice for reusing existing tooling
  unmodified.

## Status

Corpus definition files exist
(`data/corpora/oncology_nsclc_checkpoint_inhibitors/`: `corpus.json`,
`inclusion_criteria.md`, `exclusion_criteria.md`, `scientific_question.md`,
`license_policy.md`, `sources.csv`). `ke discovery-cycle-run`,
`europepmc-candidate-review-prepare`, and `core-candidate-review-prepare`
all accept `--corpus oncology_nsclc_checkpoint_inhibitors` to adjudicate
against this corpus's scope vocabulary instead of the GLP-1 default (see
`knowledge_engine/scientific_scope.py`).

**2026-08-08: first bulk seeding batch complete.** See
`data/corpora/oncology_nsclc_checkpoint_inhibitors/README.md`'s Status
section for the full account: 335 real, source-audited-license PMC OA
papers imported after a documented rule-based scope screen. This is bulk
ingestion metadata, not yet a reviewed evidence base or a golden evidence
map -- Evidence Record authoring, relationship review, and a golden map for
this corpus remain future, separate work, mirroring the GLP-1 corpus's own
progression from bulk acquisition to a reviewed map.

**2026-08-08: PICO extraction does not generalize to this corpus without
tuning -- do not promote at scale yet.** Ran the standard
`ke extraction-review-batch-generate` + `ke extraction-review-autoclassify`
pipeline against all 335 imported papers as a trial run (output not
committed; local scratch only). It produced 6,194 draft claim candidates,
of which 1,710 passed M52's structural eligibility filter (non-blank,
non-overlong PICO fields). Manually inspecting a spread of those 1,710
against the papers' own text found the `comparator` and `outcome` fields
are systematically wrong: `knowledge_engine/extraction/pico.py`'s cue
patterns (`compared (?:to|with)`, `assessed using`, `measured using`,
`evaluated using`, `underwent`) were tuned by reading GLP-1 RCT abstracts
(the module's own docstring says so) and collide, in this corpus's more
heterogeneous mix of retrospective/observational NSCLC studies, with
statistical-result sentences ("compared with the non-irH group, ... lower
baseline log2-SII, P < 0.001") and methods sentences ("assessed using the
Hosmer-Lemeshow goodness-of-fit test") far more often than with an actual
comparator-arm or outcome-definition statement. Every one of the 1,710
eligible `comparator` fields was 60+ characters -- none looked like a
short, clean comparator description -- which is itself evidence the
pattern is matching the wrong sentence type at scale, not a borderline
case needing a spot check. No records were promoted; `evidence_records.jsonl`
for this corpus still does not exist. The corpus-specific extraction-accuracy
diagnosis and targeted fix this implies is tracked as the next milestone
for this corpus -- see `docs/roadmap.md`.
