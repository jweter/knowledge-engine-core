# M11 Metadata Enrichment

M11 adds an optional Crossref metadata preview without changing the default offline ingestion path.

## Command

```text
ke metadata-preview --doi <doi> --provider crossref
```

The command prints a network-access notice before constructing and calling the provider. It then reports one of three outcomes:

- metadata candidates returned by Crossref;
- no matching Crossref record;
- a classified provider failure.

Candidate output is evidence only. The command does not write to the database, update preferred paper metadata, change parser-derived values, or modify import-run state.

## Offline default

`ke corpus-import` does not construct a metadata provider and does not make a Crossref request. External metadata access occurs only through the explicit `metadata-preview` command.

## Network and input controls

The production transport:

- requires HTTPS;
- allows only `api.crossref.org`;
- rejects embedded URL credentials;
- rejects nonstandard ports;
- blocks redirects;
- uses a 10-second request timeout;
- limits response bodies to 1,000,000 bytes;
- checks declared `Content-Length` before reading;
- performs a bounded read of at most the configured limit plus one byte;
- sends a deterministic project User-Agent;
- does not retry automatically.

External response data is treated as untrusted input. Parsed values are bounded, normalized for comparison, and converted into typed candidates. Raw response payloads and raw exception details are not persisted or printed.

## Diagnostic behavior

The provider distinguishes:

- `no_match` — Crossref returned no record for the DOI;
- `rate_limited` — Crossref returned HTTP 429;
- `provider_unavailable` — Crossref returned a 5xx or unsupported non-success status;
- `timeout` — the request exceeded the configured timeout;
- `transport_error` — the request failed before a usable response;
- `malformed_response` — JSON or expected response structure was invalid;
- `oversized_response` — the response exceeded the configured byte limit.

No-match is a successful preview outcome with no candidates. Provider failures return a nonzero CLI exit code. Retryable diagnostics are labeled without initiating an automatic retry.

## Metadata ownership and conflict policy

Crossref values remain external candidates with provenance. They do not silently replace:

- curated manifest metadata;
- parser-derived metadata;
- an existing preferred persisted value.

Candidate comparisons are explicit:

- `corroborates` when normalized values match;
- `fills_missing` when no protected local value exists;
- `conflicts` when a non-empty protected local value differs.

Multiple local owners remain visible independently. One candidate may corroborate one source and conflict with another.

## Persistence decision

M11 intentionally does **not** add a metadata-candidate table, JSON evidence column, or schema version 4 migration.

This decision is based on the current access patterns:

1. M11 only requires an explicit, reviewable preview.
2. No reviewed workflow yet promotes candidates into preferred metadata.
3. No product requirement currently queries historical provider responses or candidate decisions across runs.
4. Persisting external evidence before those workflows are defined would create premature schema and retention obligations.

A future persistence milestone should be considered only when there is a reviewed requirement for one or more of the following:

- durable candidate audit history;
- cross-run conflict review;
- reviewed candidate promotion;
- provider comparison;
- reproducible enrichment jobs tied to import items or papers.

At that point, the preferred design is a normalized candidate table with explicit provenance and review state, introduced through an additive migration. Raw provider payload persistence should remain out of scope unless separately justified.

## Testing policy

The required quality gate uses deterministic fakes and mocked transport responses. It does not depend on live Crossref availability. Live integration checks, if added later, must remain optional and outside the default required test suite.
