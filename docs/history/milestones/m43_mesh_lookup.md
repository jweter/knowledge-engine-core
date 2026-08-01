# M43 Reference Knowledge Layer: Live MeSH Lookup

## Purpose

M41 built the reference knowledge layer's first live-lookup source
(Wikipedia); M42 added a second (RxNorm, for drug-name normalization).
`docs/reference_knowledge_layer_design.md`'s "third option" section named
RxNorm, MeSH, PubChem, Wikipedia/Wiktionary, and UniProt as candidate
free, no-storage-needed sources -- M43 adds the third: `ke mesh-lookup`,
a live lookup against NLM's public E-utilities API (`db=mesh`) that
resolves a term to its canonical Medical Subject Headings (MeSH)
descriptor.

**M43 is background context only, exactly like M41/M42.** A lookup
result is never evidence, is never routed through `EvidenceRecord`
promotion, and is never merged into the evidence corpus's own search
commands (`ke search`/`ke answer`/`ke vector-search`/`ke fused-search`).
It answers "what medical concept does this term refer to," not "what
does a paper say about it."

## Why MeSH third

Wikipedia's prose is broad but encyclopedic, and RxNorm's coverage is
drug-name-specific. Neither gives a controlled, authoritative vocabulary
for the diseases, procedures, and biomedical concepts a paper's claim
text names beyond drug identity -- "obesity," "type 2 diabetes,"
"metabolic syndrome." MeSH exists specifically for that: NLM's own
controlled medical-concept vocabulary, complete with a concept hierarchy
(parent/child relationships between broader and narrower terms) neither
Wikipedia nor RxNorm provides.

MeSH was chosen over PubChem (the design doc's remaining named
candidate) because:

- No API key is required, matching M41/M42.
- It needed no new transport module. `db=mesh` queries go through
  `eutils.ncbi.nlm.nih.gov`, a host `ncbi_http.py` already allowlists
  for PubMed/PMC literature discovery, so `mesh_lookup.py` reuses
  `UrllibNcbiTransport` directly -- unlike M42's RxNorm lookup, which
  needed its own dedicated transport because RxNav is a different host.
  This is the reuse `docs/reference_knowledge_layer_design.md`'s "third
  option" section specifically anticipated for MeSH.
- Its response shape -- and a real disambiguation problem it posed --
  was verified live (`curl`) against real terms (`obesity`, `type 2
  diabetes`, `SGLT2 inhibitor`, `GLP-1 receptor agonist`, and a
  not-found term) before writing the parser, the same empirical-first
  discipline M36/M41/M42 used.

PubChem remains a named, real candidate for a later milestone -- not
ruled out, just not built yet.

## What it does

`MeshLookupService.lookup(term)` makes two calls against NCBI's
E-utilities: `GET esearch.fcgi?db=mesh&term={term}` to find candidate
MeSH record IDs, then `GET esummary.fcgi?db=mesh&id={ids}` (batched into
one call) for each candidate's full record. A term MeSH does not
recognize returns `found: false` rather than a guess -- the same
"absence is never guessed into a value" posture every extraction module
in this project already holds to.

**Two safety properties, both added after Codex review on PR #182 caught
real gaps in the first version.** First, `esearch` reports a total
candidate count separately from the (bounded) list of IDs it actually
returns; the original version fetched only the first 20 candidates and
returned whichever matched first, when the project's own verification
had already found 37 candidates for "obesity" alone (and "cancer"
returns 409). The fixed version fetches up to
`MESH_SEARCH_MAX_CANDIDATES` (200) candidates and explicitly declines to
resolve -- `found: false`, not an error -- if the reported total exceeds
what was fetched, rather than searching a partial, arbitrarily-ordered
window and risking a false negative for a term whose true descriptor
just wasn't in it. Second, the original version returned the *first*
exact match found while iterating candidates, silently picking one if
more than one candidate happened to be a true descriptor with the exact
same entry term -- contradicting the "resolves only when exactly one
candidate matches" claim already in the code's own docstring. The fixed
version collects every exact match and only resolves when there is
`exactly one`; two or more is treated the same as zero, `found: false`,
never a guess among ambiguous candidates. Verified live afterward that
`obesity`/`type 2 diabetes`/`SGLT2 inhibitor` still resolve correctly
and that `cancer` (409 candidates) now correctly declines instead of
either crashing or guessing.

**MeSH's search is full-text, not exact-match, and naively trusting it
would have been wrong.** Live-verified: searching `obesity` returns 37
loosely related candidates, and the *first* one is "Anti-Obesity
Agents" -- not the disease concept at all. Searching `SGLT2 inhibitor`
and `GLP-1 receptor agonist` (plural "Agonists") each returns two
candidates sharing nearly identical entry-term lists, one a true
`"descriptor"` record and one a `"pharmacological-action"` record for
the same drug class. `mesh_lookup.py` resolves a term only when exactly
one candidate is both a true descriptor (`ds_recordtype ==
"descriptor"`, excluding `pharmacological-action` and
`supplemental-record` candidates) *and* has the queried term as one of
its own entry-term synonyms (`ds_meshterms`), matched case-insensitively.
Verified this correctly resolves `obesity` -> `Obesity` (MeSH ID
`D009765`) and `type 2 diabetes` -> `Diabetes Mellitus, Type 2` (MeSH ID
`D003924`, matched via the entry-term synonym "Type 2 Diabetes" even
though the query doesn't match the canonical heading's own word order),
and correctly returns `found: false` for `GLP-1 receptor agonist`
(singular) -- MeSH's own entry terms only record the plural form
("GLP-1 Receptor Agonists"), so a caller needs that exact phrasing; this
module does not guess the closest candidate.

## Command

```bash
ke mesh-lookup obesity
ke mesh-lookup "type 2 diabetes"
```

Prints the resolved heading, scope note (definition), synonyms, MeSH
ID, source URL, and license to the console. `--output <path>`
optionally also saves the full result as JSON (`--force` to overwrite),
matching M41/M42's optional `--output` shape -- this is an interactive,
one-off lookup tool, not a pipeline step producing an artifact for later
reuse.

## Network boundary

Contacts only `eutils.ncbi.nlm.nih.gov` over HTTPS, via the same
`UrllibNcbiTransport` `ncbi_http.py` already provides for PubMed/PMC
literature discovery. Redirects, URL credentials, non-HTTPS URLs,
nonstandard ports, oversized responses, and unsupported hosts are
rejected -- the same transport discipline every other lookup module in
this project already established.

## Output contract

`{"term", "found", "mesh_id", "heading", "scope_note", "synonyms",
"source_url", "license", "retrieved_at"}`. `synonyms` is a list of
alternate entry terms for the same concept, excluding the preferred
`heading` itself -- empty when MeSH records no additional synonyms.
When `found` is `false`, every field past `term`/`found`/`retrieved_at`
is `null` (or `[]` for `synonyms`) -- never a guessed or partial value.

`license` records NLM's own published terms for MeSH data -- "free,
non-proprietary content," per NLM's MeSH Terms and Conditions
(`https://www.nlm.nih.gov/databases/download/terms_and_conditions_mesh.html`)
-- rather than a Creative Commons license string. This deliberately does
not run through `license_rules.py`'s `ALLOWED_LICENSE_PATTERN`: that
pattern governs the separate paper corpus's CC BY/CC0 adjudication, and
this reference layer is explicitly not part of that corpus (see
`docs/reference_knowledge_layer_design.md`'s "What this is not"
section).

## What is deliberately not built yet

- No PubChem lookup -- built next, in M44
  (`docs/m44_pubchem_lookup.md`), which fills exactly this gap
  (chemical-compound structure/property data).
- No stored-textbook path -- unchanged from M41/M42; still pending the
  project owner's own storage/hosting/per-title-licensing decisions.
- No integration into `ke extraction-review-generate`/
  `ke extraction-review-batch-generate` themselves -- those stay
  network-free by design. **M45** added a separate, opt-in step,
  `ke extraction-review-annotate`, that attaches this lookup's results
  (via PICO's `population`/`outcome` fields) onto a draft review queue
  after generation -- see `docs/m45_extraction_review_annotate.md`.
- No caching or persistence of lookup results -- `retrieved_at` exists
  so a future caching layer has the field it would need, but nothing
  persists a lookup today; every call queries NCBI live.
- No use of MeSH's own concept hierarchy (`ds_idxlinks`'s parent/child
  tree, verified present live but not surfaced here) -- this milestone
  resolves a term to its own descriptor and its entry-term synonyms
  only, not its broader/narrower concept relationships. Real future work
  if a consumer needs the hierarchy (e.g. for Phase 4's Knowledge
  Graph), not assumed here.
