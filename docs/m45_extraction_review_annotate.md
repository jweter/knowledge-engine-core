# M45 Reference Knowledge Layer: Reviewer-Aid Annotation

## Purpose

M41-M44 built the reference knowledge layer's four live-lookup sources
(Wikipedia, RxNorm, MeSH, PubChem) as standalone tools a human runs
directly. `docs/reference_knowledge_layer_design.md`'s Addendum names
four integration points buildable without waiting on Phase 4's Knowledge
Graph or a Phase 5 report renderer -- M45 builds three of them at once:
`ke extraction-review-annotate`, a new step in the Phase 2 review
workflow that attaches RxNorm/MeSH reference context directly onto the
draft evidence items a human reviewer already works from.

**M45 is background context only, exactly like M41-M44.** It never sets,
infers, or defaults `research_question` or `evidence_direction`, and it
does not change `ke extraction-review-promote`'s existing refusal to
promote a record missing either. It answers "what does this PICO field
refer to," never "is this evidence relevant to the question."

## Which Addendum items this builds

The design doc's Addendum orders ten integration points by what's
buildable now versus what needs a Phase 4/5 dependency. Items 1-4 are
buildable now; item 1 (drug-identity display grouping) was already
addressed as a boundary-tightening exercise on PR #180. M45 builds the
other three:

- **Item 2, coverage-gap flag.** When a PICO field has no reference-layer
  match, the attached result still carries `found: false` explicitly
  rather than the field being silently omitted.
- **Item 3, provenance footer discipline.** Every attached reference-layer
  result carries its own `source_url`/`license`/`retrieved_at` --
  already true of `RxNormLookupResult`/`MeshLookupResult` themselves, so
  this item required no new data, only wiring.
- **Item 4, reviewer aid in `ke extraction-review-promote`'s workflow.**
  A term's reference-layer definition is surfaced inline, in the same
  JSONL file the reviewer edits to add `research_question`/
  `evidence_direction`, before running `ke extraction-review-promote`.

## What it does

`ke extraction-review-annotate` reads the draft-review JSONL `ke
extraction-review-generate`/`extraction-review-batch-generate` already
produced and writes an annotated copy where every draft item carries a
new `reference_context` object with four keys: `intervention`,
`comparator`, `population`, `outcome` -- M28's four PICO fields.

Field-to-source mapping follows each lookup source's own established
purpose: `intervention`/`comparator` (PICO's two treatment-role fields)
route through M42's RxNorm lookup, since both name a drug or treatment;
`population`/`outcome` route through M43's MeSH lookup, since both
describe a medical concept rather than a drug.

**A PICO field is not an isolated term -- Codex review on PR #184 caught
this as a real, confirmed P1, and the fix required real redesign, not a
patch.** The first version of this module passed a PICO field's raw
value directly to RxNorm's/MeSH's *exact*-match lookups, on the
(incorrect) assumption that M28 stores an isolated term. Re-sampling the
real 951-paper corpus -- not just this module's own hand-written test
fixtures -- showed real field values are routinely entire multi-line,
citation-laden paragraphs (`pico.py`'s own docstring calls a field "the
first cue-matching sentence," but `sentence_split`'s span boundaries do
not reliably track real PDF-extracted punctuation). Verified live:
passing "Participants received semaglutide once weekly for 68 weeks." to
RxNorm's exact-name endpoint returns an empty result, even though
"semaglutide" alone resolves immediately. This meant the original
version returned `found: false` for nearly every real draft item.

The fix: the raw field text is scanned for a small, bounded set of
single-word candidate terms (first 30 alphabetic tokens, common
stopwords and short tokens dropped, capped at 20 distinct candidates per
field), and each candidate is tried against the *unchanged* exact-match
lookup. A bad candidate word simply resolves `found: false` -- no fuzzy
matching was added, so this can never produce a wrong-but-confident
answer, only a safe non-match. If more than one *distinct* concept
resolves among the candidates tried (a real, observed case: a comparator
field mentioning both "semaglutide" and "placebo" in the same paragraph),
the field declines (`found: false`) rather than guessing which one is
"the" term -- the same ambiguity discipline M43's MeSH lookup and M44's
PubChem fix already established. Multi-word candidate phrases (e.g.
"type 2 diabetes") are a known, deliberate gap this version does not
attempt -- no real match in the corpus sample this fix was verified
against required one, and guessing multi-word windows without further
real-corpus tuning would repeat the same "ship an unverified pattern"
mistake this fix exists to correct.

Live-verified against the real corpus after the fix (not just synthetic
test fixtures): a comparator field naming both "semaglutide" and
"placebo" together correctly declines; a paper about fisetin
supplementation correctly resolves `comparator: "fisetin"` to its RxNorm
ingredient (RxCUI 2667741) and `population: "screening"` to its MeSH
descriptor (`D008403`, "Mass Screening") across every draft item drawn
from that paper.

A PICO field that is itself `None` (M28 detected nothing) gets a `None`
`reference_context` entry -- distinct from a field that resolved but
found no reference-layer match (`found: false`), which is written out
explicitly. A blank or whitespace-only field is treated the same as
`None`: no lookup is attempted.

## Why this stays a separate, opt-in step -- and what it really costs

`ke extraction-review-generate`/`extraction-review-batch-generate` must
stay network-free: M40 ran the batch command against the corpus's real
scale, producing 13,588 draft items across 943 papers. Wiring live
reference-layer lookups into that pipeline directly would mean an
unbounded number of live API calls on every batch run, not a bounded,
reviewer-initiated cost. `ke extraction-review-annotate` runs as an
explicit, separate command a reviewer invokes by hand against the
specific paper(s) they are actually about to review -- the same
"explicit network access, never automatic" posture every M41-M44 lookup
command's console warning already established.

Within one run, identical candidate terms are looked up once and reused
across every draft item that shares them, bounding network calls to the
number of *distinct* candidate words actually tried, not the number of
items or the raw text length. **"Bounded" is not "fast," measured
honestly**: live-verified against two real papers (38 and 41 draft
items), even after cross-item caching, annotating one paper's full
draft-item set produced 29-34 distinct MeSH terms and 31-33 distinct
RxNorm terms to look up -- on the order of a minute or more of live
network calls per paper. This is disclosed plainly rather than
understated.

## Command

```bash
ke extraction-review-annotate --input draft.jsonl --output annotated.jsonl
```

`--force` overwrites an existing output file, matching every other
output-producing command's `--force` shape. Rejects a missing input
file, invalid JSON, or a non-object JSON line outright rather than
silently skipping it. An input file with no draft items still overwrites
an existing `--output` with an empty file (clearing any stale prior
run's results) rather than leaving it untouched -- a real gap Codex
review on PR #184 also caught: a `--force` rerun that now produces an
empty queue must not leave an earlier run's records looking current at
the same path.

## Network boundary

Contacts only `rxnav.nlm.nih.gov` (via M42's `UrllibRxNavTransport`) and
`eutils.ncbi.nlm.nih.gov` (via M43's `UrllibNcbiTransport`, reused
unchanged) -- no new transport module. Both already enforce the same
HTTPS/host-allowlist/no-redirect discipline every prior lookup module
established; this milestone adds no new network code, only a new
orchestration layer over the two existing services.

## Output contract

Every field the input draft item already carried is preserved unchanged;
one field is added: `reference_context`, an object with keys
`intervention`/`comparator`/`population`/`outcome`, each either `null`
(nothing to look up) or a full `RxNormLookupResult`/`MeshLookupResult`
JSON object (via `dataclasses.asdict`) plus a `source` key (`"rxnorm"` or
`"mesh"`) naming which service answered. `term` on a resolved entry is
the specific candidate word that matched, not the raw PICO field text; on
a `found: false` entry it is the original raw field text, for reviewer
context. `research_question` and `evidence_direction` are never touched.

## What is deliberately not built yet

- Addendum items 5-9 -- still need a Phase 5 report renderer to exist
  first, per the design doc's own ordering.
- Addendum item 10 -- still needs Phase 4's Knowledge Graph to exist
  first.
- No multi-word candidate phrases -- see above; a real, deliberate gap,
  not an oversight.
- No Wikipedia (M41) or PubChem (M44) context attached here -- PICO's
  four fields map onto RxNorm (treatments) and MeSH (medical concepts);
  extracting a lookup-worthy term from a claim's free-text
  `claim_text`/`result_summary` for Wikipedia/PubChem would need the same
  kind of candidate-scan treatment this milestone just built for PICO,
  not yet attempted for those fields.
- No caching or persistence across separate `ke
  extraction-review-annotate` invocations -- the in-run term cache only
  bounds cost *within* one call; running the command twice against the
  same file re-queries every candidate term. Given the real observed cost
  (a minute or more per paper), a future milestone persisting results
  keyed by term would have real value, but is not built here.
