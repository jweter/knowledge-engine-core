# M42 Reference Knowledge Layer: Live RxNorm Lookup

## Purpose

M41 built the reference knowledge layer's first live-lookup source
(Wikipedia). `docs/reference_knowledge_layer_design.md`'s "third option"
section named RxNorm, MeSH, PubChem, Wikipedia/Wiktionary, and UniProt as
candidate free, no-storage-needed sources -- M42 adds the second:
`ke rxnorm-lookup`, a live lookup against NLM's public RxNav REST API
(`https://rxnav.nlm.nih.gov/REST/`) that resolves a drug name to its
RxNorm normalized concept.

**M42 is background context only, exactly like M41.** A lookup result is
never evidence, is never routed through `EvidenceRecord` promotion, and is
never merged into the evidence corpus's own search commands (`ke search`/
`ke answer`/`ke vector-search`/`ke fused-search`). It answers "what drug
concept does this name refer to," not "what does a paper say about it."

## Why RxNorm second

Wikipedia's title-matching lookup treats "semaglutide" and "Ozempic" (its
brand name) as unrelated terms -- each is its own Wikipedia article with
its own title, with no structured link back to a shared underlying
concept. RxNorm exists specifically to solve that problem: rather than
merging a brand name and its generic into one identifier (RxNorm's own
model correctly keeps "Ozempic" and "semaglutide" as two distinct
concepts, since a brand-name product and its active ingredient are not
literally the same thing), RxNorm exposes a stable *ingredient
relationship* between them that a caller can follow to recognize they
name the same underlying drug. For a corpus about GLP-1/weight loss
medications, where papers and their source material use both generic
and brand names interchangeably, that's a concrete, corpus-relevant gap
Wikipedia alone doesn't close.

RxNorm was chosen over MeSH/PubChem/UniProt as the second source because:

- No API key is required, matching M41's Wikipedia lookup and continuing
  to avoid the setup friction `KE_UNPAYWALL_EMAIL` requires for Unpaywall.
- `docs/reference_knowledge_layer_design.md` specifically called out
  RxNorm as reusing NCBI-adjacent infrastructure -- in practice, RxNav
  (`rxnav.nlm.nih.gov`) is a distinct NLM host from the E-utilities hosts
  `ncbi_http.py` already allowlists, so it gets its own dedicated
  transport (`rxnorm_http.py`) rather than widening `ncbi_http.py`'s
  literature-scoped host list, but the same "this project already has
  NLM-adjacent infrastructure experience" rationale applies.
- Its response shape -- including the ingredient-relationship endpoint
  (`related.json?tty=IN`) that actually delivers the brand/generic
  normalization this milestone advertises -- was verified live (`curl`)
  against real terms (`semaglutide`, `Ozempic`, `empagliflozin`,
  `insulin`, `Glyxambi`, and several not-found cases including
  mechanism-class terms like "SGLT2 inhibitor" and "GLP-1", which RxNorm
  -- a drug-name normalizer, not a general encyclopedia -- correctly does
  not match) before writing the parser, the same empirical-first
  discipline M36/M41 used.

MeSH, PubChem, and UniProt remain named, real candidates for a later
milestone -- not ruled out, just not built yet.

## What it does

`RxNormLookupService.lookup(term)` makes three calls against RxNav: first
`GET /REST/rxcui.json?name={term}` to resolve the term to an RxCUI, then
(if found) `GET /REST/rxcui/{rxcui}/properties.json` for that concept's
own normalized `name`, term type (`tty` -- e.g. `"IN"` for an ingredient,
`"BN"` for a brand name), and `synonym`, and finally `GET
/REST/rxcui/{rxcui}/related.json?tty=IN` for the ingredient-level
concept(s) that RxCUI resolves to. A term RxNorm does not recognize
returns `found: false` rather than a guess -- the same "absence is never
guessed into a value" posture every extraction module in this project
already holds to.

**`rxcui`/`name`/`term_type` describe the looked-up term's own concept;
`ingredients` is what actually normalizes a brand name to its generic.**
Live-verified: `ke rxnorm-lookup semaglutide` and `ke rxnorm-lookup
Ozempic` return different `rxcui` values (`1991302` vs `1991307`, as
RxNorm's own model requires) but the *same* `ingredients` entry
(`semaglutide`, RxCUI `1991302`) -- that shared entry is what a caller
compares to recognize the two names as the same underlying drug, not the
top-level `rxcui`. A combination-drug brand resolves to more than one
ingredient: `ke rxnorm-lookup Glyxambi` returns both `linagliptin` and
`empagliflozin`. A concept with no ingredient relationship (e.g. a bare
dose-form concept) returns an empty `ingredients` tuple rather than an
error.

(An earlier version of this milestone claimed brand/generic
normalization in its docs and `CHANGELOG.md` without the code actually
following this relationship -- the top-level `rxcui` was returned
unchanged regardless of whether the input was a brand or generic name.
Caught by Codex review on PR #179 before merge and fixed by adding the
`related.json?tty=IN` call and `ingredients` field above, verified live
against the same `semaglutide`/`Ozempic` pair the original, inaccurate
claim named.)

RxNorm's default exact-match endpoint returns at most one RxCUI for
every term verified live during this milestone; the service takes the
first entry if more than one is ever returned, rather than raising, so an
edge case in RxNorm's own matching behavior cannot make this lookup
fail outright.

Unlike M41's Wikipedia lookup, there is no separate `revision`/
`permanent_url` pair here: RxNav's concept-search permalink
(`https://mor.nlm.nih.gov/RxNav/search?searchBy=RXCUI&searchTerm={rxcui}`,
verified to resolve) is already keyed to the specific RxCUI this lookup
returned, so `source_url` alone is a stable citation target -- there is
no "canonical URL always shows the current version" problem to solve the
way Wikipedia's page URL has.

## Command

```bash
ke rxnorm-lookup semaglutide
ke rxnorm-lookup Ozempic
```

Prints the resolved name, term type, synonym (if any), ingredient(s),
RxCUI, source URL, and license to the console. `--output <path>`
optionally also saves the full result as JSON (`--force` to overwrite),
matching M41's optional `--output` shape -- this is an interactive,
one-off lookup tool, not a pipeline step producing an artifact for later
reuse.

## Network boundary

Contacts only `rxnav.nlm.nih.gov` (RxNav's own REST API host) over HTTPS.
Redirects, URL credentials, non-HTTPS URLs, nonstandard ports, oversized
responses, and unsupported hosts are rejected -- the same transport
discipline `unpaywall_http.py`/`reference_lookup_http.py`/`ncbi_http.py`
already established, mirrored here in `rxnorm_http.py`.

## Output contract

`{"term", "found", "rxcui", "name", "term_type", "synonym", "ingredients",
"source_url", "license", "retrieved_at"}`. `ingredients` is a list of
`{"rxcui", "name"}` objects -- empty when the concept has no RxNorm
ingredient relationship, one entry for a single-ingredient drug, more
than one for a combination product. When `found` is `false`, every field
past `term`/`found`/`retrieved_at` is `null` (or `[]` for `ingredients`)
-- never a guessed or partial value.

`license` records RxNav's own phrase for its content -- "non-proprietary
content" from NLM, per RxNav's published Terms of Service
(`https://lhncbc.nlm.nih.gov/RxNav/TermsofService.html`) -- rather than a
Creative Commons license string. This deliberately does not run through
`license_rules.py`'s `ALLOWED_LICENSE_PATTERN`: that pattern governs the
separate paper corpus's CC BY/CC0 adjudication, and this reference layer
is explicitly not part of that corpus (see
`docs/reference_knowledge_layer_design.md`'s "What this is not" section).

## What is deliberately not built yet

- No MeSH/PubChem/UniProt lookups -- named candidates for a later
  milestone if a corpus-relevant gap in RxNorm/Wikipedia's combined
  coverage turns up.
- No stored-textbook path -- unchanged from M41; still pending the
  project owner's own storage/hosting/per-title-licensing decisions.
- No integration into the extraction pipeline (M16-M28) or
  `ke extraction-review-generate`/`ke extraction-review-batch-generate` --
  same as M41, this is a standalone lookup tool a human runs directly.
- No caching or persistence of lookup results -- `retrieved_at` exists so
  a future caching layer has the field it would need, but nothing
  persists a lookup today; every call queries RxNav live.
- No use of RxNorm's richer relationship data beyond the ingredient
  (`"IN"`) relationship -- `allrelated.json`'s brand names, dose forms,
  and packaged products (see the raw structure this milestone verified
  live for "Ozempic": brand names, dose forms, dose-form groups, and
  specific branded/packaged products, in addition to the ingredient this
  milestone does surface) remain unbuilt. Real future work if a
  consumer needs the reverse direction (an ingredient's known brand
  names) or the fuller product graph, not assumed here.
