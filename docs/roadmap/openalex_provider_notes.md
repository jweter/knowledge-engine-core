# OpenAlex provider integration notes

Status: implementation note, 2026-08-15.

OpenAlex's current API documentation requires an `api_key` query parameter for Works endpoints. Knowledge Engine therefore treats OpenAlex credentials as an explicit provider capability boundary rather than assuming anonymous baseline access.

## Required behavior

- OpenAlex remains optional to the overall federated discovery system.
- If OpenAlex is configured without a usable API key, Core must not issue a network request.
- The provider must return an explicit `disabled` provider status with `attempted=false` and a stable reason such as `missing_api_key`.
- API keys remain secret configuration. They must never be copied into `ProviderObservation`, `FederatedCandidate`, search-run provenance, logs, prompts, evidence records, or serialized output.
- When a key is configured, it may be attached only at the outbound transport boundary.
- Authentication/authorization failures from OpenAlex must be distinguishable from provider outages and rate limiting.
- A missing or invalid OpenAlex credential must never cause PubMed, Crossref, or other providers to fail.

## Citation traversal direction

OpenAlex supports citation-network discovery through work `referenced_works` and the Works `cites` filter. Knowledge Engine will use those capabilities only through bounded, reproducible methods that preserve the seed work, direction, limit/depth, provider outcome, and discovered provider-native identifiers.

This note supersedes earlier wording that described an OpenAlex API key as optional for baseline OpenAlex requests. The provider itself is optional to Knowledge Engine; current OpenAlex access is credential-gated.
