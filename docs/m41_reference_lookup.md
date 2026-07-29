# M41 Reference Knowledge Layer: Live Wikipedia Lookup

## Purpose

`docs/reference_knowledge_layer_design.md` sketched three options for
grounding a paper's claim text against background scientific knowledge it
assumes but never restates -- stored open-license textbooks, live lookups
against free APIs, or both -- and named live lookup as the better
starting point: it needs no storage decision and no per-title license
verification, sidestepping both real open questions the stored-text path
would require. M41 builds that first slice: a live lookup against
Wikipedia's public REST summary API.

**M41 is background context only, exactly like M36's evidence-not-verdict
posture.** A lookup result is never evidence, is never routed through
`EvidenceRecord` promotion, and is never merged into the evidence corpus's
own search commands (`ke search`/`ke answer`/`ke vector-search`/
`ke fused-search`). It answers "what does this term mean," not "what does
a paper say about it."

## Why Wikipedia first

`docs/reference_knowledge_layer_design.md` named RxNorm, MeSH, PubChem,
Wikipedia/Wiktionary, and UniProt as candidate live sources. Wikipedia's
REST summary API (`https://en.wikipedia.org/api/rest_v1/page/summary/
{term}`) was chosen first because:

- No API key or contact email is required (unlike Unpaywall's
  `KE_UNPAYWALL_EMAIL` requirement) -- one fewer piece of setup friction.
- One well-known, stable response shape, verified live against real terms
  (`semaglutide`, `SGLT2 inhibitor`, a disambiguation page, and a
  not-found term) before writing the parser, the same empirical-first
  discipline `docs/m36_unpaywall_lookup.md` used.
- Its content is licensed CC BY-SA -- a license family
  `license_rules.py` already recognizes -- while covering any scientific
  term at all (drug names, lab techniques, statistical terms, chemistry
  concepts), not one narrow domain the way RxNorm (pharmacology-only) or
  PubChem (chemistry-only) would.

RxNorm/MeSH/PubChem remain named, real candidates for a later milestone if
a narrower, more structured lookup (e.g. a drug's RxNorm identifier) turns
out to be needed -- not ruled out, just not built first.

## What it does

`ReferenceLookupService.lookup(term)` queries Wikipedia's summary endpoint
for one term and returns its `title`, short `description`, plain-language
`extract`, `page_type` (`"standard"`, `"disambiguation"`, etc. -- surfaced
so a reviewer can tell an ambiguous term list from a clean definition),
`source_url`, `license` (always `"CC BY-SA"` when found), the page's own
`page_last_modified` timestamp, and this lookup's own `retrieved_at`
timestamp. A term with no Wikipedia article returns `found: false` rather
than a guess -- the same "absence is never guessed into a value" posture
every extraction module in this project already holds to.

`retrieved_at`/`page_last_modified` exist for the reproducibility reason
the design doc named: a Wikipedia article can change between two lookups
of the same term, unlike a hash-verified stored PDF. Recording both is the
"ordinary engineering" hook the design doc pointed to -- if a future
consumer needs to cite a specific lookup's result reproducibly (e.g. as
part of extraction provenance), the timestamp to snapshot against already
exists; this milestone does not need to guess that need or build caching
speculatively ahead of an actual consumer.

## Command

```bash
ke reference-lookup "GLP-1 receptor agonist"
```

Prints the term's title, description, extract, source URL, and license to
the console. `--output <path>` optionally also saves the full result as
JSON (`--force` to overwrite); unlike the Unpaywall commands, `--output`
is optional here since this command's primary use is an interactive,
one-off "what does this term mean" lookup, not a pipeline step producing
an artifact for later reuse.

## Network boundary

Contacts only `en.wikipedia.org` (Wikipedia's own REST API host) over
HTTPS. Redirects, URL credentials, non-HTTPS URLs, nonstandard ports,
oversized responses, and unsupported hosts are rejected -- the same
transport discipline `unpaywall_http.py`/`core_http.py`/`ncbi_http.py`
already established, mirrored here in `reference_lookup_http.py`.

## Output contract

`{"term", "found", "title", "description", "extract", "page_type",
"source_url", "revision", "permanent_url", "license",
"page_last_modified", "retrieved_at"}`. When `found` is `false`, every
field past `term`/`found`/`retrieved_at` is `null` -- never a guessed or
partial value.

`page_last_modified` (Wikipedia's edit timestamp, second-resolution) and
`source_url` (Wikipedia's canonical page URL, which always resolves to
the *current* revision) are not enough on their own to pin down exactly
what content a given lookup returned -- two rapid edits can share a
timestamp, and a later visit to `source_url` can show newer content than
what this result actually captured. `revision` (Wikipedia's own stable
revision ID) and `permanent_url` (`{source_url}?oldid={revision}`,
verified to resolve to that exact revision) exist so a future consumer
that needs this lookup's own reproducibility -- e.g. citing it as part of
extraction provenance -- has that hook without this module needing to
guess the need in advance. Both are `null` when Wikipedia's response
omits a revision ID or a `content_urls.desktop.page` URL.

## What is deliberately not built yet

- No stored-textbook path -- that remains the other named option in
  `docs/reference_knowledge_layer_design.md`, pending the project owner's
  own storage/hosting/per-title-licensing decisions, none of which this
  milestone needed to make.
- No RxNorm/MeSH/PubChem/UniProt lookups -- named candidates for a later
  milestone if Wikipedia's coverage proves insufficient for some domain.
- No integration into the extraction pipeline (M16-M28) or
  `ke extraction-review-generate`/`ke extraction-review-batch-generate` --
  this is a standalone lookup tool a human runs directly, not yet wired
  into any automated step that would look up terms found in a paper's own
  claim text. That wiring is real future work, not assumed here.
- No caching or persistence of lookup results -- `retrieved_at` exists so
  a future caching layer has the field it would need, but nothing
  persists a lookup today; every call queries Wikipedia live.
