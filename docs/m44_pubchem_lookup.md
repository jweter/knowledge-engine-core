# M44 Reference Knowledge Layer: Live PubChem Lookup

## Purpose

M41 built the reference knowledge layer's first live-lookup source
(Wikipedia); M42 added a second (RxNorm, drug-name normalization); M43
added a third (MeSH, controlled medical-concept vocabulary).
`docs/reference_knowledge_layer_design.md`'s "third option" section
named RxNorm, MeSH, PubChem, Wikipedia/Wiktionary, and UniProt as
candidate free, no-storage-needed sources -- M44 adds the fourth and
last named live-lookup candidate: `ke pubchem-lookup`, a live lookup
against NLM/NCBI's public PubChem PUG REST API that resolves a chemical
compound name to its PubChem Compound ID (CID) and structured chemical
identifiers.

**M44 is background context only, exactly like M41/M42/M43.** A lookup
result is never evidence, is never routed through `EvidenceRecord`
promotion, and is never merged into the evidence corpus's own search
commands (`ke search`/`ke answer`/`ke vector-search`/`ke fused-search`).
It answers "what compound does this name refer to, and what is its
chemical structure," not "what does a paper say about it."

## Why PubChem fourth

Wikipedia's prose is broad but encyclopedic, RxNorm normalizes drug
names, and MeSH gives a controlled medical-concept vocabulary -- none of
the three cover real chemical-structure data: a compound's molecular
formula, molecular weight, or SMILES string. PubChem exists specifically
for that: NLM/NCBI's public chemistry database, one exact-name lookup
away from a compound's canonical identifiers.

PubChem was chosen as the fourth and, per the design doc's "third
option" section, last named live-lookup candidate because:

- No API key is required, matching M41/M42/M43.
- Its response shape -- and two real API quirks -- was verified live
  (`curl`) against real compounds (metformin, semaglutide,
  empagliflozin, a not-found name, and "GLP-1 receptor agonist") before
  writing the parser, the same empirical-first discipline M36/M41/M42/
  M43 used.
- It needed its own dedicated transport module (`pubchem_http.py`):
  `pubchem.ncbi.nlm.nih.gov` is a distinct NLM/NCBI host from both
  `eutils.ncbi.nlm.nih.gov` (M43's MeSH lookup reuses `ncbi_http.py`
  directly) and `rxnav.nlm.nih.gov` (M42's RxNorm lookup) -- the same
  one-source-one-transport shape `rxnorm_http.py` already established.

## What it does

`PubchemLookupService.lookup(term)` makes one call against PubChem's PUG
REST API: `GET
compound/name/{term}/property/Title,IUPACName,MolecularFormula,
MolecularWeight,ConnectivitySMILES/JSON`. Unlike MeSH's full-text
`esearch`, this is an exact-name lookup like RxNorm's: a name PubChem
does not recognize returns a clean `404`, mapped to `found: false`
rather than a guess -- the same "absence is never guessed into a value"
posture every extraction module in this project already holds to.

**One real API quirk, verified live before writing any parsing code.**
Requesting the `CanonicalSMILES` property name -- PubChem's older, still
publicly documented name -- returns the result under a *different*
response key, `ConnectivitySMILES`; PubChem renamed the underlying
property internally but kept the old request-parameter name aliased
without renaming the response key to match. Verified by requesting
`CanonicalSMILES` alone vs. `ConnectivitySMILES` alone against the same
compound (metformin, CID 4091): both returned identical JSON keyed
`ConnectivitySMILES`. This module requests `ConnectivitySMILES` directly
rather than relying on that alias.

**PubChem indexes whatever name strings were actually deposited
alongside real compounds, not a curated concept vocabulary.** Verified
live: querying "GLP-1 receptor agonist" (a mechanism class, not a
specific drug) resolves to a real, specific small-molecule compound (CID
177864544) that happens to have been deposited under that literal name
-- confirmed via a full property fetch showing a real, distinct
molecular formula, SMILES string, and IUPAC name, not an empty
placeholder. This module reports whatever PubChem actually returns
rather than guessing what a caller "probably" meant, the same posture
M43 documented for MeSH's plural-only "GLP-1 Receptor Agonists" entry
term.

`MolecularWeight` was also observed returned as a JSON number in real
API responses, not always a string; the module's optional-field parser
tolerates both, with a dedicated regression test proving it.

## Command

```bash
ke pubchem-lookup metformin
ke pubchem-lookup empagliflozin
```

Prints the compound's title, molecular formula, molecular weight, IUPAC
name, SMILES string, CID, source URL, and license to the console.
`--output <path>` optionally also saves the full result as JSON
(`--force` to overwrite), matching M41/M42/M43's optional `--output`
shape -- this is an interactive, one-off lookup tool, not a pipeline
step producing an artifact for later reuse.

## Network boundary

Contacts only `pubchem.ncbi.nlm.nih.gov` over HTTPS, via a dedicated
`UrllibPubchemTransport` in `pubchem_http.py`. Redirects, URL
credentials, non-HTTPS URLs, nonstandard ports, oversized responses, and
unsupported hosts are rejected -- the same transport discipline every
other lookup module in this project already established.

## Output contract

`{"term", "found", "cid", "title", "iupac_name", "molecular_formula",
"molecular_weight", "smiles", "source_url", "license", "retrieved_at"}`.
When `found` is `false`, every field past `term`/`found`/`retrieved_at`
is `null` -- never a guessed or partial value.

`license` records NCBI/NLM's general public-domain policy for
government-created content on its sites ("information created by or for
the US government on this site is within the public domain,"
`https://www.ncbi.nlm.nih.gov/home/about/policies/`) -- the same
public-domain basis PubMed/PMC metadata already carries, not a Creative
Commons license string. This deliberately does not run through
`license_rules.py`'s `ALLOWED_LICENSE_PATTERN`: that pattern governs the
separate paper corpus's CC BY/CC0 adjudication, and this reference layer
is explicitly not part of that corpus (see
`docs/reference_knowledge_layer_design.md`'s "What this is not"
section).

## What is deliberately not built yet

- No UniProt lookup -- the design doc's one remaining unnamed-in-detail
  candidate source; not scoped or verified live yet.
- No stored-textbook path -- unchanged from M41/M42/M43; still pending
  the project owner's own storage/hosting/per-title-licensing decisions.
- No integration into the extraction pipeline (M16-M28) or
  `ke extraction-review-generate`/`ke extraction-review-batch-generate` --
  same as M41/M42/M43, this is a standalone lookup tool a human runs
  directly.
- No caching or persistence of lookup results -- `retrieved_at` exists
  so a future caching layer has the field it would need, but nothing
  persists a lookup today; every call queries PubChem live.
- No use of PubChem's PUG View endpoint (a separate, richer
  human-readable description/synonym service) or its structure-search
  endpoints (similarity/substructure search) -- this milestone resolves
  an exact compound name to its own property record only, not a broader
  chemical-search capability. Real future work if a consumer needs it,
  not assumed here.
