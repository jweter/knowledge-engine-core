# M36 Unpaywall OA-Location/License Evidence Lookup

## Purpose

Following M34 (Europe PMC) and M35 (CORE), the project owner asked to keep
adding evidence sources without pausing for permission at each step. M36
adds Unpaywall (https://unpaywall.org) as a fourth source -- but in a
deliberately different shape from the three discovery-and-adjudication
pipelines that came before it. **M36 is evidence lookup only.** It makes no
accept/reject/hold decision, is not wired into acquisition, and using it
does not resume corpus growth. The corpus remains intentionally frozen at
605 papers by the project owner's prior decision.

## Why this is a lookup tool, not a fourth discovery pipeline

Two facts, both verified empirically against the live API before writing
any code, ruled out mirroring M14/M34/M35's `--query` discovery shape:

- **Unpaywall's topic-search endpoint is broken.** `GET
  https://api.unpaywall.org/v2/search?query=...&email=...` returned a
  consistent `HTTP 500 Internal Server Error` across multiple distinct
  queries (`semaglutide obesity`, `obesity`, `cancer`) and repeated retries.
  The route exists -- it is not a `404` -- so this reads as the service
  being broken or deprecated server-side, not a transient blip or a query
  I got wrong. There is no reliable `--query` endpoint to build a
  discovery command against.
- **Even the working endpoint carries no scientific-scope signal.**
  Unpaywall's real, reliable capability is `GET
  https://api.unpaywall.org/v2/{doi}?email=...` -- a per-DOI lookup, not a
  search. Its response includes a bare `title` but no abstract, so
  `scientific_scope.py`'s evaluation would be working from much weaker
  evidence than any of the three discovery pipelines. And every URL it
  returns points to some third-party publisher or repository (arXiv,
  Harvard DASH, PMC, a publisher's own site, etc.) -- there is no single
  "Unpaywall's own host" the way CORE has `core.ac.uk` or Europe PMC has
  `europepmc.org`, so a full-text host-allowlist rule (the backbone of
  every prior pipeline's `full_text_rule_result`) does not apply here.

Given a user-provided AskUserQuestion decision, this module was scoped as
an **evidence lookup for DOIs already known** -- typically DOIs already
surfaced, and possibly `held`, by `pubmed_discovery.py`,
`europepmc_discovery.py`, or `core_discovery.py` -- rather than a fresh
source of new candidates. This matches what Unpaywall's API actually
supports today.

## What it does

`UnpaywallLookupService.lookup(doi)` queries Unpaywall's per-DOI endpoint
and reports: `is_oa`, `oa_status`, the best OA location's URL and license,
every OA location Unpaywall has on file (for transparency), and this
project's own `license_rule_result` (via the shared `license_rules.py`) so
a human reviewer can see at a glance whether Unpaywall's reported license
would clear this project's reusable-license bar. `lookup_many` runs a
bounded batch (max 100) of individual per-DOI lookups -- Unpaywall has no
bulk endpoint, so this is not a single more-efficient request, just a
convenience wrapper with the same per-DOI evidence shape.

It does **not** produce a `decision` field, reason codes, or an
`accepted`/`rejected`/`held` verdict. That remains the responsibility of
whichever pipeline's candidate this evidence is being used to re-examine --
Unpaywall provides evidence, not a verdict.

### License token normalization

Unpaywall's real, confirmed license format is lowercase and hyphenated
(e.g. `"cc-by"`, `"cc-by-nc-nd"`), unlike PMC/Europe PMC's `"CC BY 4.0"`-
style strings. `_normalize_license` maps the known Creative Commons tokens
to the format `license_rules.evaluate_license` expects before evaluating;
non-CC tokens (e.g. `"publisher-specific-oa"`, `"implied-oa"`) pass through
unchanged and correctly evaluate as unsupported, since they are not
unrestricted-reuse licenses this project accepts.

## Commands

```bash
ke unpaywall-doi-lookup \
  --doi 10.1038/nature12373 \
  --output work/m36/lookup-000.json
```

```bash
ke unpaywall-batch-lookup \
  --dois-file work/m36/dois.json \
  --output work/m36/lookup-batch-000.json
```

`work/m36/dois.json` is `{"dois": ["10.x/...", ...]}` (max 100 entries).
Both commands refuse to overwrite an existing output unless `--force` is
supplied. Symbolic-link inputs and outputs are rejected. Both require
`KE_UNPAYWALL_EMAIL` to be set -- Unpaywall's usage policy requires a
contact email on every request, and this project does not bake in a
default contact for every installation; the commands fail cleanly before
any network access if it is unset.

## Network boundary

Both commands contact only `api.unpaywall.org` (Unpaywall's official REST
API host) over HTTPS. Redirects, URL credentials, non-HTTPS URLs,
nonstandard ports, oversized responses, and unsupported hosts are
rejected, mirroring `core_http.py`'s transport (`unpaywall_http.py`).

## Output contract

A single lookup's JSON: the normalized DOI, `found` (whether Unpaywall has
a record for it -- a `404` is a legitimate business outcome, not an
error), and, when found, a `record` with `title`, `is_oa`, `oa_status`,
`best_oa_location_url`, `best_oa_location_license`, `license_rule_result`,
and the full `oa_locations` list (each with `url`, `host_type`, `license`,
`is_best`).

Batch JSON adds `requested_count`, `found_count`, `not_found_count`, and a
`results` array of the same per-DOI shape.

## What is deliberately not built yet

- No topic-search discovery command -- see above; Unpaywall's `/v2/search`
  is broken as of this writing. If Unpaywall's search service is restored,
  a `pubmed`/`europepmc`/`core`-style discovery pipeline could be revisited
  as a separate milestone.
- No automatic feedback loop into `europepmc_candidate_review.py` or
  `core_candidate_review.py`'s worksheets -- this milestone deliberately
  keeps discovery providers as separate evidence categories (per
  `docs/roadmap.md`), so Unpaywall evidence is a standalone artifact a
  human reviewer consults, not an automated re-adjudication of another
  pipeline's `held` decision.
- Acquisition (actually downloading a PDF from any of these third-party
  hosts) is out of scope, as it was for M14, M34, and M35.
