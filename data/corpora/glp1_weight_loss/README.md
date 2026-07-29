# Obesity and Metabolic-Disease Therapeutics Corpus

This directory began as the GLP-1 weight-loss vertical slice and remains at the
same stable repository path for compatibility. Its Phase 1 scope now covers
legally reusable research on obesity and metabolic-disease therapeutics, with
GLP-1 receptor agonists retained as the first named subtopic.

The corpus exercises scientific metadata, legal provenance, deterministic
adjudication, bounded acquisition, retrieval, evidence display, and manifest
validation. It does not by itself provide a final scientific conclusion.

## Scientific Question

What treatment effects, limitations, and safety findings are reported for
therapeutic interventions used in adults with obesity, overweight, type 2
diabetes, or metabolic syndrome?

## Files

- `corpus.json`: version 1 corpus definition.
- `sources.csv`: version 1 source manifest with curated metadata, legal-use
  status, provenance, and local file names.
- `scientific_question.md`: human-readable question definition and rationale.
- `inclusion_criteria.md`: deterministic criteria for adding papers.
- `exclusion_criteria.md`: deterministic criteria for excluding or holding
  papers.
- `license_policy.md`: policy for legal and reproducible use of source
  documents.
- `evidence_records.jsonl`: historical draft evidence records from the original
  GLP-1 vertical slice.

## Manifest Validation

Validate the committed corpus metadata without checking local PDFs:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json
```

If the local ignored PDFs are present, check file readiness:

```bash
ke corpus-validate data/corpora/glp1_weight_loss/corpus.json --check-files
```

Validation does not import papers, parse PDFs, write to SQLite, infer a license,
or produce scientific synthesis. Legal and scientific eligibility for M14 is
recorded by deterministic adjudication rules before acquisition.

## Path Contract

The corpus uses the Phase 1 version 1 path contract:

- `source_manifest` and `license_policy` are relative to this directory.
- `default_local_papers_directory` is relative to the project root.
- Source-row `local_path` values are filenames relative to
  `papers/corpora/glp1_weight_loss`.

PDF files are ignored by Git. The source list records enough provenance to
reconstruct the corpus without committing copyrighted or licensed full-text
documents.

## Current Status

The committed manifest holds 943 sources: the small historical GLP-1
prototype set (3 rows) plus 940 accepted records from thirteen small
(`--limit 250`) automated discovery batches (`retstart` 0 through 3000) of
the project owner's larger corpus-building effort, following M14's rules.
Ruleset corrections along the way held 3 pediatric-titled records and 1
correction-notice record that earlier rule versions had wrongly accepted.
A further ninety-six records were manually excluded after individual
abstract review, since v9's disease/intervention keyword match has no
automated way to catch several recurring patterns: single-patient case
reports where the named disease is only incidental patient background or
the reported intervention treats an unrelated coexisting condition (a
dermatology case report was caught this way in the `retstart=1750` batch;
six more -- a liver-abscess, a limb-ischemia/antiphospholipid, a
renal-abscess, a Graves'-disease myopericarditis, a necrotizing-fasciitis
presentation, and an invasive-mucormycosis case report -- were caught the
same way in the `retstart=2000` batch); gene-/protein-name lexical
collisions (e.g. the NOD-SCID mouse strain, the FTO gene's "fat mass and
obesity-associated" full name); type 1 diabetes-specific sources per
`exclusion_criteria.md`'s explicit rule (two more caught in the
`retstart=1750` batch, one an immune-tolerance intervention paper and one
a fatty-acid/microbiota paper, both explicitly T1D-scoped despite
matching the batch's disease/intervention keywords; a bioelectronic
thymic-modulation immune-tolerance paper caught the same way in the
`retstart=2000` batch); a pediatric study population whose title's
forward-looking "Adult" outcome term obscured the actual (non-adult)
subjects (the same evasion pattern recurred once more in the
`retstart=1750` batch: a childhood-obesity review whose title named
"Adult Cardiometabolic Disease" only as a future burden, not an adult
intervention); and a few papers matching a target term only via generic
English phrasing unrelated to the actual disease entity.

The `retstart=2000` batch also surfaced a distinct, newly-documented
pattern, in two rounds: a first, proactive self-audit pass (before
exporting approvals) excluded 23 records under the patterns above; a
Codex review on the growth PR then caught two records this pass had
missed (a necrotizing-fasciitis case report and a MASLD/T2D
epidemiological-relationship review), which prompted a second, stricter
pass checking every accepted title directly against
`inclusion_criteria.md`'s explicit two-part requirement -- the title
must name *both* an approved scope term *and* a named therapeutic
intervention -- rather than relying on the four previously-documented
patterns alone. That second pass found 29 more records where the
deterministic ruleset had accepted a title naming no therapeutic
intervention at all, because the target disease appeared only as an
incidental covariate deep in an abstract about a different primary
disease (hemodialysis frailty, COPD hypoxemia, ventilator-weaning
prediction, heart-failure diuretic resistance, park walkability, and
others), or because the record was a mechanism-only review, a
data-quality or measurement-comparison methodology paper, a
risk-prediction model, or a conceptual framework with no treatment
evidence. Of those 29, 17 were this batch's own net-new candidates
(excluded from `sources.csv` before the final import below); the
remaining 12 had already been acquired by an earlier, already-merged
batch under query overlap and were left as a documented follow-up at
the time, since that batch's own diff couldn't retroactively fix them --
a dedicated cleanup pass later removed all 12 in one pass, confirmed
against the same abstracts, bringing the total to 81 manual exclusions
across the whole corpus. Several of the earlier exclusions were first
caught by Codex reviews on the growth PRs, including all four
`retstart=1750` exclusions and two of the `retstart=2000` batch's; the
rest of the `retstart=2000` batch's 38 exclusions (of 40 total: 23 in
the first pass, 17 more -- 2 Codex-caught, 15 self-audited -- in the
second) were caught proactively during self-audit. As of the
`retstart=1250` batch, the project owner gave explicit direction that
this corpus-building phase should prioritize breadth over precision:
only the clear-cut patterns above are now screened before acquisition,
not exhaustive gray-area sweeps for mechanism-only reviews,
analytical-chemistry papers, or drugs studied for unrelated diseases --
drugs studied for an unrelated disease (e.g. an SGLT2 inhibitor trial in
aortic stenosis, a GLP-1 receptor agonist scoping review on rotator cuff
disease) remain included under this policy, since they still name a
therapeutic agent, even when the target disease itself is absent from
the title. See `CHANGELOG.md` for the full per-batch
history and `docs/m14_candidate_review_worksheet.md` for the v6-v9
ruleset history. Accepted records proceed
automatically; rejected and held records remain auditable but do not block
the batch or require owner review. The corpus continues to grow in small
batches toward a 1,000-paper cap (revised down from an earlier "at least
a couple thousand" target, explicitly for GitHub space reasons -- see
`docs/roadmap.md`'s "Scaling beyond 500 papers for Phase 2 tuning"
section) and `docs/m27_corpus_library.md` for how the resulting parsed
content is persisted across sessions once imported.

The `retstart=2250` batch (250 candidates, 97 deterministically accepted,
1 already present from query overlap, 96 net-new PMC OA PDFs acquired)
deliberately ran with **no manual audit layer** -- the project owner gave
explicit direction to prioritize shipping milestone after milestone over
further precision tightening, and this project's own "Working-version
review policy" (`docs/roadmap.md`, Phase 1) already states that
"repository execution must not depend on the project owner manually
reviewing individual candidates... before a working version exists" and
that "deterministic automation must accept, reject, hold, retry, or
exclude each record." The `retstart=2000` batch's manual self-audit
rounds went beyond what that policy actually calls for; this batch
returns to trusting the v9 ruleset's own accept/reject/hold decisions
directly, the same way `retstart=0` through `retstart=1250` did before
manual auditing crept in.

A Codex review on the `retstart=2250` growth PR caught three real bugs
this no-manual-audit approach surfaced, none of them scientific-scope
judgment calls: (1) a genuine study-level duplicate the deterministic
DOI/PMID-based dedup couldn't catch -- consecutive-DOI Portuguese and
English translations of the same knee-arthroplasty study, resolved by
keeping the English row; (2) a real, previously-undetected bug where
`Paper.doi` (and, more seriously, duplicate-collision detection) trusted
`parsed.doi` -- the PDF's own extracted DOI, which can be a truncated
in-text citation (e.g. `10.1172/jci` instead of the full
`10.1172/jci.insight.198707`) -- over the manifest's own correct,
PubMed/PMC-sourced DOI; a truncated parsed DOI had falsely collided with
an unrelated already-imported paper's DOI, silently routing a
genuinely new paper to `needs_review` and dropping it from the imported
corpus entirely (the same class of bug M27's manifest-title fix
addressed for `title`, now extended to `doi`, in both
`PaperRepository._build_paper` and
`resolve_duplicate_before_persistence`). Fixed at the code level
(`manifest_doi` now wins the same way `manifest_title` already did) plus
the specific rows involved, corpus corrected 800 -> 799.

The `retstart=2500` batch (250 candidates, 81 deterministically accepted,
0 already present, 81 net-new PMC OA PDFs acquired) ran the same
no-manual-audit way as `retstart=2250`, now with the manifest-DOI fix in
place: a fresh `ke corpus-import` completed with 880 imported, 0 failed,
0 skipped -- an exact one-to-one match against the manifest's 880 rows,
confirming the false-collision class of bug from the previous batch did
not recur. As expected for a no-manual-audit batch, a Codex review then
caught two genuine scientific-scope misses -- an incidental-comorbidity
pulmonary-infection case report (T2D was only patient background;
ciprofloxacin treated the unrelated infection) and an explicitly type 1
diabetes-specific beta-cell/NOD-mouse study -- and explicitly invited
checking the rest of the batch's title-level misses the same way. Doing
so (abstract-verified, not title-pattern-only) found 11 more: an
eating-disorders-prevalence study, a Prader-Willi sarcopenia diagnostic
tool study (a diagnostic/measurement paper, not a treatment one, despite
the syndrome's well-established obesity link), a policy-only
case-finding evidence brief with no treatment evidence, an unrelated
anal-fistula surgery outcomes study, a Weight-Adjusted-Waist-Index/brain
health association study, a multi-disease COVID-era public-health
narrative review, a light-exposure/dementia association study, an
unrelated MS lifestyle-factors study, a hypertension/LV-geometry review,
a kidney-cancer epidemiology study, and an arsenic-exposure/pregnancy-CVD
review -- all matching already-established patterns (incidental
comorbidity, diagnostic/measurement-only, policy-only, or off-target
primary disease with only an incidental obesity/T2D mention), not new
gray-area judgment calls. Four titles found by the same sweep were kept
after review: a cagrilintide (an anti-obesity drug) mechanism study a
generic intervention-term list had missed, ROHHAD syndrome (obesity is
literally in the syndrome's name), and two adipokine/AGE mechanism
reviews kept under the explicit "mechanism-only reviews" breadth-over-
precision carve-out. All 13 exclusions removed, corpus corrected 880 ->
867.

**Resolved follow-ups:** both systemic quality gaps surfaced during the
`retstart=2000` batch's Codex review have since been closed. The dozen
already-merged records from earlier batches matching the
title-lacks-intervention pattern above (found by re-running that
batch's stricter title check against the whole manifest, not just its
own additions) were removed in a dedicated cleanup pass, each
re-confirmed against its full abstract before removal. A Codex review
on that cleanup PR then caught 2 more the pass had missed -- both had
been correctly identified as false positives during the earlier
`retstart=2000` abstract review but were dropped by mistake when the
final exclusion list was compiled, an oversight in transcription, not
in the underlying judgment. Also caught by that same Codex review: a
third instance of the identical incidental-obesity-covariate pattern
(a high-altitude mine workers' sleep-disordered-breathing study,
`pmc-13332975`) dating to the much earlier `retstart=500` batch, found
via a full-corpus regex sweep (title lacks both a scope term and an
intervention term) prompted by that review comment. All 3 removed,
bringing the corpus to 704 papers. That same sweep surfaced roughly 90
more titles with neither pattern present -- not individually
abstract-verified and not removed here, since retroactively
re-auditing the entire corpus's precision this way is exactly the kind
of tightening the project owner has asked to defer until after more
milestones land; flagged here for whenever that pass happens, not
acted on now.
`PyMuPDFParser`'s title extraction being unreliable for some publisher
PDF layouts (Cureus's "Review began MM/DD/YYYY" peer-review-date
banner, Frontiers' "TYPE Review"/"TYPE Original Research" article-type
header), which had left roughly 7% of imported `Paper.title` values
across the whole corpus not the actual paper title, was fixed at the
persistence layer: `CorpusIngestionService`/`LinkedCorpusIngestionService`
now pass the manifest row's own (PubMed/PMC-sourced, always-required)
title through to `PaperRepository._build_paper` as `manifest_title`,
which wins over `parsed.title` when present. A fresh corpus-import
after that fix confirmed the bad-title count dropped from 50 to 0.

**Open follow-up (not yet acted on):** while confirming the dozen
already-merged records above, the deterministic ruleset's own
`evaluate_scientific_scope` function (`knowledge_engine/scientific_scope.py`)
was run directly against each excluded title/abstract and returned
`"passed"` for every one of them -- meaning these were never truly
edge cases the v9 ruleset almost caught; the function's design
evaluates the disease *and* intervention terms over title+abstract
combined (unlike its pediatric check, which is deliberately
title-only, per that function's own code comment), and its
intervention-term list (`treatment`, `therapy`, `drug`, `medication`,
etc.) is generic enough to match incidentally in nearly any clinical
abstract regardless of whether the paper actually studies that
intervention. This is a real, verified weakness in the deterministic
rule, not just an interpretation difference against
`inclusion_criteria.md`'s prose -- but tightening it would change
`accepted`/`held` outcomes for future discovery batches and, if applied
retroactively, could reclassify many already-included papers; that is
a corpus-inclusion-philosophy decision for the project owner, not
something this cleanup unilaterally changes. Left as an explicit,
documented open question rather than acted on.

The `retstart=2750` batch (250 candidates, 77 deterministically accepted,
14 already present from query overlap, 63 net-new PMC OA PDFs acquired)
ran the same no-manual-audit way as the prior several batches. This
batch's import used linked resume rather than a from-scratch fresh
import: this session's local database already held a completed import
run for the existing 867 papers (restored from the committed compressed
snapshot), so `ke corpus-import ... --resume-from <parent_run_id>`
skipped re-parsing those 867 already-`imported` source_ids and processed
only the 63 new ones, reporting 63 imported, 0 failed, 867 skipped --
the resume-mode equivalent of the exact one-to-one reconciliation prior
batches got from a fresh import against an empty database. Corpus grew
867 -> 930.

A Codex review on the `retstart=2750` growth PR then caught 10 genuine
scientific-scope false positives among those 63, all matching patterns
this corpus had already documented and excluded in earlier batches
(kidney-cancer and ovarian-cancer/circadian-rhythm epidemiology reviews,
an unrelated multiple-sclerosis outcomes study, two policy-only evidence
briefs, a Prader-Willi sarcopenia diagnostic-only study, an idiopathic
intracranial hypertension case report, a type 2 diabetes qualitative
well-being study naming no intervention, a diabetes knowledge/attitudes/
practices survey naming no intervention, an alcohol-consumption/cancer
review, and a bariatric-surgery outcomes study explicitly scoped to type
1 diabetes) -- not new gray-area judgment calls, the same v9 ruleset gap
(a generic intervention-term list matching incidentally in an abstract
about a different primary disease or population) this corpus's README
already documents at length. All 10 removed from `sources.csv`; since
this session's local database enforces foreign keys, correcting the
already-imported rows meant a full fresh reimport (removing the 10 rows'
PDFs, reinitializing the local database, and re-running `ke corpus-import`
against the corrected manifest) rather than a surgical row deletion --
reported 920 imported, 0 failed, 0 skipped, an exact one-to-one match
against the corrected manifest. Corpus corrected 930 -> 920. Regenerated
the compressed `corpus_library` snapshot accordingly.

The `retstart=3000` batch (250 candidates, 60 deterministically accepted,
16 already present from query overlap) applied a lesson directly from the
`retstart=2750` correction: since a previously-excluded false positive is
removed from `sources.csv` rather than tracked in a persistent "already
seen and rejected" registry, an overlapping later batch can legitimately
re-discover the exact same PMID and re-accept it under the same v9
ruleset gap -- which is exactly what happened here. Three of this batch's
60 accepted candidates were the identical kidney-cancer, diabetes
knowledge/attitudes/practices, and alcohol/cancer PMIDs the
`retstart=2750` correction had just removed. Rather than wait for another
Codex review to catch the same three papers a second time, this batch's
44 net-new candidates (after the 16-way overlap filter) were checked by
title against every documented exclusion pattern before acquisition --
the same categories the last two Codex reviews established (off-target
primary disease with no scope/intervention term, policy-only or
prediction-model-only papers with no treatment evaluated, type 1
diabetes-specific sources, no-intervention-named qualitative/survey
studies) -- rather than an exhaustive gray-area sweep. 13 matched: the 3
exact-duplicate false positives above, a type 1 diabetes-specific
adjunct-medications study, an ankle-fracture-fixation study, two
dementia/Alzheimer's risk-factor studies, a coronary
ischaemia-reperfusion antiplatelet/antithrombin study, a busulfan
(chemotherapy) pharmacokinetics study, a frailty/socioeconomic-
inequalities study, a type 2 diabetes policy model predicting life
expectancy with no treatment evaluated, a bariatric-surgery weight-regain
prediction-model study, and a qualitative-interviews study naming no
intervention. All 13 excluded before acquisition -- 31 net-new PMC OA
PDFs acquired and imported via linked resume against the same local
import run (31 imported, 0 failed, 920 skipped). Corpus grew 920 -> 951.
Regenerated the compressed `corpus_library` snapshot.

A Codex review on the `retstart=3000` growth PR then caught 8 more
false positives the proactive title screen above missed, all failing
`inclusion_criteria.md`'s explicit two-part title requirement (an
approved scope term *and* a named therapeutic intervention) the same way
as before: an NHANES observational obesity/cardiovascular-disease
association study, a hospitalised-adults hypoglycaemia-episodes
observational study, an in-hospital-outcomes study of T2D as a covariate
for STEMI (an off-target primary disease), a diabetic-eye-disease
progression/risk-factor study, a T2D-development sibling-pairs genetics
study, and three primary mechanistic/model papers (a novel mouse model
for cardiovascular-kidney-metabolic syndrome, a macrophage lysosomal
acid lipase deletion phenotype study, an H19 lncRNA prenatal-programming
study) that name no therapeutic intervention at all. The screen's own
title scan had actually flagged several of these correctly during
review, but they were dropped when the final exclusion list was
compiled -- the same transcription-error failure mode a much earlier
batch's Codex review caught (see the "retstart=2000" history above); the
other three reflect applying this corpus's "mechanism-only reviews"
breadth carve-out too broadly, to primary mechanistic *research* papers
naming no intervention rather than the review articles the carve-out's
own wording names. All 8 removed from `sources.csv` and their PDFs;
corrected with a full fresh reimport (943 imported, 0 failed, 0
skipped, an exact one-to-one match). Corpus corrected 951 -> 943.
Regenerated the compressed `corpus_library` snapshot again.
