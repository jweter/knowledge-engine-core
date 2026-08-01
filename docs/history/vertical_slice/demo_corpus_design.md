# Demo Corpus Design: GLP-1 Receptor Agonists and Body Weight

This document defines the VS-2 demonstration corpus plan for the Knowledge
Engine vertical slice.

No papers have been downloaded. No PDFs have been imported. No code or database
schema changes are required by this document.

## Purpose

The purpose of this corpus is to create a scientifically defensible miniature
source set that can demonstrate retrieval over a real research question.

The corpus is not intended to be comprehensive. It should be small enough for a
human reviewer to inspect, but strong enough to include primary trials,
synthesized evidence, limitations, and at least some qualifying evidence.

## Research Question

Do GLP-1 receptor agonists reduce body weight in adults with overweight or
obesity?

## Target Size

Target size:
- 8 to 10 papers.

Ideal number:
- 10 papers.

Minimum useful size:
- 5 papers, if they include at least one pivotal randomized trial, one
  longer-term or withdrawal study, one comparator study, and one systematic
  review or meta-analysis.

## Required Study Types

The corpus should include:

- Randomized controlled trials.
- Systematic reviews or meta-analyses.
- Landmark clinical trials.
- Recent reviews or long-term follow-up studies.
- At least one study that qualifies the main finding rather than merely
  supporting it.

## Examples of Useful Source Types

Randomized controlled trials:
- Semaglutide versus placebo trials.
- Liraglutide versus placebo trials.
- Semaglutide versus liraglutide comparative trials.
- Tirzepatide trials only if explicitly labeled as adjacent GLP-1-based or dual
  incretin evidence.

Meta-analyses and systematic reviews:
- GLP-1 receptor agonist class-level reviews.
- Semaglutide-specific reviews.
- Dose-response or comparative analyses.

Landmark clinical trials:
- SCALE Obesity and Prediabetes.
- Semaglutide STEP trials.
- SELECT weight analysis.

Recent reviews:
- Reviews that summarize effectiveness, durability, adverse effects, and
  clinical uncertainty.

## Publication Date Range

Preferred range:
- 2015 to 2025.

Rationale:
- 2015 captures the pivotal liraglutide 3.0 mg weight management trial.
- 2018 captures dose-ranging semaglutide evidence.
- 2021 to 2024 captures pivotal semaglutide phase 3, withdrawal, comparative,
  long-term, and cardiovascular-outcomes-related weight analyses.
- 2025 sources may be used if they provide high-quality synthesis, but the first
  demo should avoid depending only on very recent review literature.

## Inclusion Criteria

A paper may be included when it meets all of the following:

- Adult participants, or a review/meta-analysis focused primarily on adults.
- Population includes overweight or obesity.
- Intervention includes a GLP-1 receptor agonist or clearly related
  GLP-1-based incretin therapy.
- Reports body weight, BMI, percent body weight change, waist circumference, or
  weight maintenance outcomes.
- Provides enough bibliographic metadata for citation.
- Has a DOI or stable source URL.
- Can be legally accessed or referenced for local research use.

Preferred:
- Randomized design.
- Placebo or active comparator.
- Clear treatment duration.
- Explicit body weight endpoint.
- Full text available through open access, PubMed Central, publisher access, or
  institutional access.

## Exclusion Criteria

Exclude papers when:

- The population is pediatric only.
- The source is mechanism-only without body weight outcomes.
- The source is safety-only without weight outcomes.
- The source is a news article, editorial, marketing page, or non-scientific
  commentary.
- The study is not about GLP-1 receptor agonists or closely related incretin
  therapies.
- The source lacks sufficient citation metadata.
- Legal usage status cannot be determined.
- The source is a duplicate report of the same trial without adding a new
  relevant analysis.

## Expected Limitations

- The corpus will not represent all obesity pharmacotherapies.
- The corpus will likely overrepresent semaglutide because it has the most
  prominent pivotal obesity trial program.
- Trial populations may not represent all real-world patients.
- Many trials are industry funded.
- Follow-up duration varies across studies.
- Weight loss after drug discontinuation is a major limitation and should be
  represented explicitly.
- Adverse effects and discontinuation may affect interpretation but are not the
  primary endpoint of this demo corpus.
- Tirzepatide is a dual GIP/GLP-1 receptor agonist, not a pure GLP-1 receptor
  agonist; if included, it should be categorized as adjacent GLP-1-based
  evidence.

## Known Biases

- Publication bias toward positive pivotal trials.
- Sponsor involvement in many obesity pharmacotherapy trials.
- Enrichment of trial participants able to tolerate medication and adhere to
  protocol.
- Underrepresentation of long-term discontinuation outcomes.
- Underrepresentation of cost, access, adherence, and real-world persistence.
- Potentially limited racial, geographic, sex, and comorbidity generalizability
  depending on trial enrollment.

## Known Gaps

- Real-world persistence and adherence.
- Long-term outcomes after discontinuation.
- Weight maintenance strategies after stopping therapy.
- Comparative evidence across all available GLP-1 receptor agonists.
- Patient-centered outcomes beyond body weight.
- Cost, access, and equity.
- Differences by diabetes status, baseline BMI, age, sex, race, and comorbidity.
- Long-term rare adverse events.

## Expected Contradictory or Qualifying Evidence

The main evidence is expected to support weight reduction while qualifying the
finding in several ways:

- Weight regain after discontinuation may show that benefit depends on continued
  treatment.
- Adults with type 2 diabetes may lose less weight than adults without diabetes.
- Liraglutide appears effective but less potent than semaglutide in direct or
  indirect comparisons.
- Gastrointestinal adverse events and discontinuation may limit use.
- Trial results may not fully predict real-world persistence or access.
- Tirzepatide may show larger weight reductions, but it is a dual incretin
  therapy and should not be conflated with pure GLP-1 receptor agonists.

## Why This Corpus Is Scientifically Useful

This corpus is scientifically useful because it can test whether the Knowledge
Engine can retrieve source material that represents:

- A clear intervention question.
- Strong primary evidence.
- Synthesized evidence.
- Multiple agents.
- Different treatment durations.
- Comparator and withdrawal evidence.
- Evidence that supports, qualifies, and contextualizes a likely answer.

The corpus should let the system return relevant papers without pretending to
perform scientific synthesis. That makes it appropriate for the current vertical
slice.

## Candidate Papers

### 1. A Randomized, Controlled Trial of 3.0 mg of Liraglutide in Weight Management

Category:
- Foundational.

Metadata:
- Authors: Xavier Pi-Sunyer, Arne Astrup, Ken Fujioka, Frank Greenway, et al.;
  SCALE Obesity and Prediabetes NN8022-1839 Study Group.
- Year: 2015.
- Journal: New England Journal of Medicine.
- DOI: `10.1056/NEJMoa1411892`.
- Source: [NEJM](https://www.nejm.org/doi/full/10.1056/NEJMoa1411892).

Why it belongs:
- Landmark adult liraglutide 3.0 mg obesity trial.
- Establishes earlier GLP-1 receptor agonist evidence before semaglutide.

Expected contribution:
- Demonstrates that GLP-1 receptor agonism can reduce body weight versus
  placebo when added to lifestyle intervention.

Expected limitations:
- Older agent with smaller average weight loss than later semaglutide trials.
- Industry-sponsored pivotal trial.

### 2. Efficacy and Safety of Semaglutide Compared With Liraglutide and Placebo for Weight Loss in Patients With Obesity

Category:
- Foundational.

Metadata:
- Authors: Patrick M. O'Neil, Andreas L. Birkenfeld, Barbara M. McGowan, Ofri
  Mosenzon, John P. H. Wilding, et al.
- Year: 2018.
- Journal: The Lancet.
- DOI: `10.1016/S0140-6736(18)31773-2`.
- Source: [DOI](https://doi.org/10.1016/S0140-6736(18)31773-2).

Why it belongs:
- Dose-ranging phase 2 trial comparing semaglutide, liraglutide, and placebo.
- Helps connect older liraglutide evidence to later semaglutide phase 3
  evidence.

Expected contribution:
- Provides early comparative evidence that semaglutide produced clinically
  relevant weight loss and may outperform liraglutide.

Expected limitations:
- Phase 2 dose-ranging trial rather than final obesity-dose phase 3 evidence.
- Daily semaglutide doses differ from the later once-weekly 2.4 mg formulation.

### 3. Once-Weekly Semaglutide in Adults With Overweight or Obesity

Category:
- Foundational.

Metadata:
- Authors: John P. H. Wilding, Rachel L. Batterham, Salvatore Calanna, Melanie
  Davies, Luc F. Van Gaal, et al.; STEP 1 Study Group.
- Year: 2021.
- Journal: New England Journal of Medicine.
- DOI: `10.1056/NEJMoa2032183`.
- Source: [NEJM](https://www.nejm.org/doi/full/10.1056/NEJMoa2032183).

Why it belongs:
- Pivotal STEP 1 randomized trial in adults with overweight or obesity without
  diabetes.

Expected contribution:
- Strong primary evidence that once-weekly semaglutide 2.4 mg reduces body
  weight versus placebo.

Expected limitations:
- Trial population excluded diabetes.
- Does not by itself answer durability after stopping treatment.

### 4. Semaglutide 2.4 mg Once a Week in Adults With Overweight or Obesity, and Type 2 Diabetes

Category:
- Supporting.

Metadata:
- Authors: Melanie J. Davies, Louise Faerch, Ole K. Jeppesen, Ildiko Lingvay,
  et al.; STEP 2 Study Group.
- Year: 2021.
- Journal: The Lancet.
- DOI: `10.1016/S0140-6736(21)00213-0`.
- Source: [The Lancet](https://www.thelancet.com/journals/lancet/article/PIIS0140-6736%2821%2900213-0/fulltext).

Why it belongs:
- Tests semaglutide 2.4 mg in adults with overweight or obesity and type 2
  diabetes.

Expected contribution:
- Adds population heterogeneity and helps show that diabetes status may affect
  magnitude of weight loss.

Expected limitations:
- Diabetes population may not generalize to adults without diabetes.
- Weight loss effect may be smaller than in non-diabetes trials.

### 5. Effect of Subcutaneous Semaglutide vs Placebo as an Adjunct to Intensive Behavioral Therapy on Body Weight in Adults With Overweight or Obesity

Category:
- Supporting.

Metadata:
- Authors: Thomas A. Wadden, Timothy S. Bailey, Liana K. Billings, Melanie
  Davies, Juan P. Frias, et al.; STEP 3 Investigators.
- Year: 2021.
- Journal: JAMA.
- DOI: `10.1001/jama.2021.1831`.
- Source: [PubMed](https://pubmed.ncbi.nlm.nih.gov/33625476/).

Why it belongs:
- Tests semaglutide with intensive behavioral therapy and an initial low-calorie
  diet.

Expected contribution:
- Shows whether pharmacotherapy adds weight loss beyond a stronger lifestyle
  intervention context.

Expected limitations:
- Intensive behavioral therapy may reduce comparability to routine care.
- Industry sponsorship and selected trial population remain relevant.

### 6. Effect of Continued Weekly Subcutaneous Semaglutide vs Placebo on Weight Loss Maintenance in Adults With Overweight or Obesity

Category:
- Contradictory.

Metadata:
- Authors: Domenica Rubino, Niclas Abrahamsson, Melanie Davies, Richard
  Hesse, Frank L. Greenway, et al.; STEP 4 Investigators.
- Year: 2021.
- Journal: JAMA.
- DOI: `10.1001/jama.2021.3224`.
- Source: [JAMA](https://jamanetwork.com/journals/jama/fullarticle/2777886).

Why it belongs:
- Withdrawal design tests whether continued treatment is required for weight
  loss maintenance.

Expected contribution:
- Qualifies the main answer by showing that stopping treatment can lead to
  weight regain or loss of continued benefit.

Expected limitations:
- Participants first completed a semaglutide run-in, so it is enriched for
  tolerability and response.

### 7. Two-Year Effects of Semaglutide in Adults With Overweight or Obesity: The STEP 5 Trial

Category:
- Supporting.

Metadata:
- Authors: W. Timothy Garvey, Rachel L. Batterham, Meena Bhatta, Silvia
  Buscemi, M. Drent, et al.; STEP 5 Study Group.
- Year: 2022.
- Journal: Nature Medicine.
- DOI: `10.1038/s41591-022-02026-4`.
- Source: [Nature Medicine](https://www.nature.com/articles/s41591-022-02026-4).

Why it belongs:
- Extends the question from short-term weight loss to two-year durability with
  continued treatment.

Expected contribution:
- Supports sustained weight reduction when treatment continues.

Expected limitations:
- Smaller sample than STEP 1.
- Still a controlled trial setting.

### 8. Effect of Weekly Subcutaneous Semaglutide vs Daily Liraglutide on Body Weight in Adults With Overweight or Obesity Without Diabetes

Category:
- Supporting.

Metadata:
- Authors: Domenica M. Rubino, Frank L. Greenway, Usman Khalid, Patrick M.
  O'Neil, Julio Rosenstock, et al.; STEP 8 Investigators.
- Year: 2022.
- Journal: JAMA.
- DOI: `10.1001/jama.2021.23619`.
- Source: [JAMA](https://jamanetwork.com/journals/jama/fullarticle/2787907).

Why it belongs:
- Directly compares semaglutide 2.4 mg with liraglutide 3.0 mg.

Expected contribution:
- Helps distinguish a class-level answer from agent-specific differences.

Expected limitations:
- Open-label active comparison.
- Smaller sample than STEP 1.

### 9. Tirzepatide Once Weekly for the Treatment of Obesity

Category:
- Background.

Metadata:
- Authors: Ania M. Jastreboff, Louis J. Aronne, Nadia N. Ahmad, Sean Wharton,
  Lisa Connery, et al.; SURMOUNT-1 Investigators.
- Year: 2022.
- Journal: New England Journal of Medicine.
- DOI: `10.1056/NEJMoa2206038`.
- Source: [NEJM](https://www.nejm.org/doi/full/10.1056/NEJMoa2206038).

Why it belongs:
- Provides adjacent incretin-based obesity evidence and a useful boundary case
  for terminology.

Expected contribution:
- Tests whether the corpus and later retrieval can avoid conflating pure GLP-1
  receptor agonists with dual GIP/GLP-1 receptor agonists.

Expected limitations:
- Tirzepatide is not a pure GLP-1 receptor agonist.
- Should not be used as direct support for the narrow GLP-1 receptor agonist
  question unless clearly labeled as adjacent evidence.

### 10. Efficacy and Safety of Semaglutide on Weight Loss in Obese or Overweight Patients Without Diabetes

Category:
- Supporting.

Metadata:
- Authors: Xueqin Gao, Xiaoli Hua, Xu Wang, Wanbin Xu, Yu Zhang, Chen Shi,
  Ming Gu.
- Year: 2022.
- Journal: Frontiers in Pharmacology.
- DOI: `10.3389/fphar.2022.935823`.
- Source: [Frontiers in Pharmacology](https://www.frontiersin.org/journals/pharmacology/articles/10.3389/fphar.2022.935823/full).

Why it belongs:
- Systematic review and meta-analysis of randomized controlled trials of
  semaglutide in adults with overweight or obesity without diabetes.

Expected contribution:
- Provides synthesized evidence that can help validate whether retrieval finds
  both primary trials and review-level evidence.

Expected limitations:
- Semaglutide-specific rather than class-wide.
- Depends on included trials and may share their sponsor and publication biases.

## Optional Additions if the Corpus Needs More Balance

### Weight Regain and Cardiometabolic Effects After Withdrawal of Semaglutide

Category:
- Contradictory.

Metadata:
- Authors: John P. H. Wilding, Rachel L. Batterham, Melanie Davies, Luc F. Van
  Gaal, Kristian Kandler, et al.; STEP 1 Study Group.
- Year: 2022.
- Journal: Diabetes, Obesity and Metabolism.
- DOI: `10.1111/dom.14725`.
- Source: [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9542252/).

Why it may be added:
- Strongly qualifies the main answer by showing regain after semaglutide
  withdrawal.

Why it is optional:
- It is an extension of STEP 1 rather than an independent randomized primary
  trial.

### Long-Term Weight Loss Effects of Semaglutide in Obesity Without Diabetes in the SELECT Trial

Category:
- Supporting.

Metadata:
- Authors: Donna H. Ryan, Ildiko Lingvay, A. Michael Lincoff, Helen M.
  Colhoun, et al.
- Year: 2024.
- Journal: Nature Medicine.
- DOI: `10.1038/s41591-024-02996-7`.
- Source: [Nature Medicine](https://www.nature.com/articles/s41591-024-02996-7).

Why it may be added:
- Provides long-term weight and anthropometric outcomes in a large cardiovascular
  outcomes trial population with overweight or obesity without diabetes.

Why it is optional:
- The parent trial was cardiovascular-outcomes focused rather than designed
  primarily as a weight-loss efficacy trial.

## Category Summary

Foundational:
- Pi-Sunyer et al. 2015, liraglutide 3.0 mg.
- O'Neil et al. 2018, semaglutide dose-ranging phase 2.
- Wilding et al. 2021, STEP 1 semaglutide pivotal trial.

Supporting:
- Davies et al. 2021, STEP 2.
- Wadden et al. 2021, STEP 3.
- Garvey et al. 2022, STEP 5.
- Rubino et al. 2022, STEP 8.
- Gao et al. 2022, semaglutide systematic review and meta-analysis.

Contradictory:
- Rubino et al. 2021, STEP 4 withdrawal trial.

Background:
- Jastreboff et al. 2022, SURMOUNT-1 tirzepatide boundary case.

## Evaluation

This corpus is sufficient to demonstrate the current vertical slice if the goal
is retrieval-only answering.

It is strong enough because it includes:

- Pivotal primary trials.
- A pre-semaglutide GLP-1 receptor agonist trial.
- Semaglutide phase 2 and phase 3 evidence.
- A diabetes subgroup trial.
- A behavioral-intervention context.
- A withdrawal or maintenance trial.
- A direct semaglutide-versus-liraglutide comparison.
- Review-level synthesized evidence.
- One adjacent incretin therapy boundary case.

It is not sufficient for full scientific synthesis because:

- It is too small for a balanced systematic review.
- It does not fully represent adverse events, long-term safety, access, cost, or
  real-world adherence.
- It may overrepresent semaglutide and sponsor-funded pivotal trials.
- It includes tirzepatide only as adjacent background, not direct evidence for
  pure GLP-1 receptor agonists.

Recommended adjustment:
- Keep the 10-paper plan for the retrieval demo.
- If the next milestone moves toward evidence records, add the STEP 1 withdrawal
  extension as an explicit qualifying source and consider replacing SURMOUNT-1 if
  the corpus must remain strictly limited to GLP-1 receptor agonists.
