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
promote a record missing either. It answers "what does this PICO field's
term refer to," never "is this evidence relevant to the question."

## Which Addendum items this builds

The design doc's Addendum orders ten integration points by what's
buildable now versus what needs a Phase 4/5 dependency. Items 1-4 are
buildable now; item 1 (drug-identity display grouping) was already
addressed as a boundary-tightening exercise on PR #180. M45 builds the
other three:

- **Item 2, coverage-gap flag.** When a PICO field's term has no
  reference-layer match, the attached result still carries `found:
  false` explicitly rather than the field being silently omitted.
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
`comparator`, `population`, `outcome` -- exactly M28's four PICO fields,
no new term-extraction logic added.

Field-to-source mapping follows each lookup source's own established
purpose: `intervention`/`comparator` (PICO's two treatment-role fields)
route through M42's RxNorm lookup, since both name a drug or treatment;
`population`/`outcome` route through M43's MeSH lookup, since both
describe a medical concept rather than a drug. Live-verified:
`intervention: "semaglutide"` and `intervention: "Ozempic"` both resolve
through RxNorm to the same underlying ingredient RxCUI (1991302), the
same brand/generic recognition M42 built; `population: "obesity"`
resolves through MeSH to descriptor `D009765` with its full scope note;
`outcome: "type 2 diabetes"` resolves to descriptor `D003924` with 30
entry-term synonyms attached; and a nonsense population term correctly
returns `found: false` rather than a guess.

A PICO field that is itself `None` (M28 detected nothing) gets a `None`
`reference_context` entry -- distinct from a field that resolved but
found no reference-layer match (`found: false`), which is written out
explicitly. A blank or whitespace-only field is treated the same as
`None`: no lookup is attempted.

## Why this stays a separate, opt-in step

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

Within one run, identical terms are looked up once and reused across
every draft item that shares them (verified: two draft items both citing
`intervention: "semaglutide"` produce exactly one RxNorm call, not two),
bounding network calls to the number of *distinct* terms in the file,
not the number of items.

## Command

```bash
ke extraction-review-annotate --input draft.jsonl --output annotated.jsonl
```

`--force` overwrites an existing output file, matching every other
output-producing command's `--force` shape. Rejects a missing input
file, invalid JSON, or a non-object JSON line outright rather than
silently skipping it.

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
`"mesh"`) naming which service answered. `research_question` and
`evidence_direction` are never touched.

## What is deliberately not built yet

- Addendum items 5-9 -- still need a Phase 5 report renderer to exist
  first, per the design doc's own ordering.
- Addendum item 10 -- still needs Phase 4's Knowledge Graph to exist
  first.
- No Wikipedia (M41) or PubChem (M44) context attached here -- PICO's
  four fields map cleanly onto RxNorm (treatments) and MeSH (medical
  concepts); a claim's free-text `claim_text`/`result_summary` might
  benefit from broader Wikipedia/PubChem context too, but extracting
  *which* term in free text to look up is a new term-extraction problem
  this milestone does not solve, unlike PICO's fields which M28 already
  isolates cleanly.
- No caching or persistence across separate `ke
  extraction-review-annotate` invocations -- the in-run term cache only
  bounds cost *within* one call; running the command twice against the
  same file re-queries every term. A future milestone could persist
  results keyed by term, but that is not built here.
