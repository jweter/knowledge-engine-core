# GLP-1 Same-PICO Contradiction Search Audit

## Decision

No source-verified, direction-reversing result was identified for the direct
semaglutide-versus-placebo body-weight PICO in this bounded search. The search
did identify one legally reusable pilot trial that materially qualifies the
map at an agent, population, dose, and surgical-context boundary. It is added
as a `qualifies` relationship, not a `contradicts` relationship.

This is a reproducible negative search result. It is not proof that no
contradictory literature exists, and it is not a consensus or truth claim.

## Search Contract

The direct target was continued semaglutide treatment for adults with
overweight or obesity, compared with placebo or matched control, with body
weight measured during the randomized treatment window. Different GLP-1
receptor agonists, doses, populations, comparators, endpoints, and withdrawal
windows were treated as possible qualifiers rather than same-PICO
contradictions.

The decision rules are recorded in
`docs/glp1_same_pico_contradiction_search_plan.md`.

## Search Executed

The audit was run on 2026-08-04 in five layers:

1. Screened all 156 committed Evidence Records for null, non-significant,
   control-favoring, and hedged body-weight findings.
2. Screened all 952 committed source-manifest rows by title, identifiers,
   study type, and PICO metadata.
3. Generated 261 deterministic shared-concept relationship candidates from
   the local graph and inspected all 18 unique records paired with the STEP 5,
   SELECT, or Gao direct-evidence anchors.
4. Ran a direct PubMed title/abstract query, returning 113 records.
5. Ran a negative-signal PubMed query, returning 45 records, and inspected the
   abstract text and negative-result language for all 45.

The direct query was:

```text
semaglutide[Title] AND (overweight[Title/Abstract] OR obesity[Title/Abstract])
AND placebo[Title/Abstract] AND (randomized[Title/Abstract] OR
randomised[Title/Abstract]) AND ("body weight"[Title/Abstract] OR
"weight loss"[Title/Abstract] OR bodyweight[Title/Abstract])
```

The negative-signal query added:

```text
AND ("no significant"[Title/Abstract] OR "not significant"[Title/Abstract]
OR "no difference"[Title/Abstract] OR "did not"[Title/Abstract]
OR "failed to"[Title/Abstract])
```

Similarity ranking was attempted first, but the configured sentence-transformer
model was not locally cached and the environment could not complete the remote
certificate handshake. The audit therefore used the repository's deterministic
shared-concept candidate mode and records that limitation rather than silently
claiming similarity-ranked coverage.

## Candidate Dispositions

| Candidate | Disposition | Reason |
| --- | --- | --- |
| STEP 2 semaglutide trial in adults with type 2 diabetes | Excluded from this addition | Favored semaglutide for body weight; it is a population/magnitude qualifier, not a direction-reversing result. The accessible conference record is CC BY-NC-ND. |
| STEP 3 semaglutide trial with intensive behavioral therapy | No new record | Favored semaglutide and therefore did not supply the searched contradiction. |
| STEP 6 semaglutide trial in East Asian adults | No new record | Favored semaglutide and qualified population applicability without reversing direction. |
| 2025 Cochrane semaglutide review | No new record | The pooled randomized evidence favored semaglutide; the review was used as a trial-discovery cross-check, not imported as a reviewed local record. |
| Exenatide trial in adults with schizophrenia | Excluded | Reported no body-weight benefit, but studied a different agent and a materially different psychiatric population; the full text is CC BY-NC-ND. |
| Liraglutide physical-fitness analysis | Existing endpoint qualifier | Its null fitness endpoint is already represented and is not a null body-weight result. |
| STEP 1 withdrawal extension | Existing durability qualifier | It changes the treatment window to withdrawal and therefore does not contradict on-treatment efficacy. |
| GLIDE pilot trial | Added as an agent/population qualifier | Legally reusable CC BY source. It found no additional six-month body-weight benefit from liraglutide 1.8 mg after gastric banding, but differs in agent, dose, diabetes status, surgical context, outcome priority, and statistical power. |

Negative phrases in the remaining PubMed results concerned other endpoints,
subgroup interactions, adverse events, or contextual findings rather than an
aligned semaglutide-versus-placebo body-weight direction reversal.

## Added Qualifier

The GLIDE pilot randomized 27 adults with obesity and type 2 diabetes after
laparoscopic adjustable gastric banding to liraglutide 1.8 mg or placebo. Its
multivariable analysis found a six-month between-group body-weight difference
of 2.0 kg (95% CI -4.2 to 8.1; p=0.50). At 12 months, six months after study
treatment ended, weight was 8.2 kg higher in the former liraglutide arm (95%
CI 1.6 to 14.9; p=0.02). The trial enrolled 27 participants against a planned
sample of 58 and described itself as significantly underpowered.

The result qualifies broad class-level expectations after metabolic surgery.
It does not contradict STEP 5 because STEP 5 studied semaglutide 2.4 mg during
continued treatment in adults without diabetes and without the same surgical
context.

Source and legal basis:

- DOI: `10.1038/s41366-023-01368-4`
- PMID: `37696925`
- PMCID: `PMC10599987`
- License: Creative Commons Attribution 4.0 International (`CC BY`)
- Local PDF: ignored under `papers/corpora/glp1_weight_loss/`
- SHA-256: `467637a80c9962ef15133596a2c3c0e4d4c9b2261eb51f2d445966c120649bda`

## Map Effect

This audit adds:

- one reviewed Evidence Record with role `agent_population_qualifier`;
- one reviewed `qualifies` relationship from GLIDE to STEP 5; and
- no `contradicts` relationship.

The map's contradiction assessment now points to an executed search rather
than an informal absence. The map still does not infer evidence, compute
consensus, score confidence, perform benefit-harm analysis, or decide truth.

## Remaining Uncertainty

Bibliographic indexing, terminology, and the evidence base change over time.
Future trials may identify an aligned null or control-favoring result, and some
eligible evidence may not use the searched phrases. The query should therefore
be rerun periodically and whenever the direct map PICO changes. Any future
candidate must still pass source, license, PICO, result, and relationship
review before it changes the map.
