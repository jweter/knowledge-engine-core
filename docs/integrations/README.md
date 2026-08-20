# Third-Party Integration Guide Index

Last reviewed: 2026-08-20

This directory is the canonical planning surface for third-party systems being evaluated for Knowledge Engine or cross-project development infrastructure.

## Governing rules

1. Third-party projects do not become architectural authorities by being adopted. Knowledge Engine owns its canonical domain models, provenance rules, persistence contracts, validation semantics, and scientific-review boundaries.
2. Prefer adapters, subprocess/service boundaries, and replaceable provider interfaces over importing third-party object models throughout the codebase.
3. Pin and record versions before implementation. Re-check upstream license, security posture, release notes, model licenses, and transitive dependencies before every material upgrade.
4. Never copy upstream source into this repository unless a separate review explicitly approves the license, attribution, update burden, and reason for vendoring.
5. Preserve offline-first behavior where practical. Any network dependency must be explicit and fail closed rather than silently changing scientific results.
6. Generated or parsed output is untrusted input. Validate it before persistence or downstream scientific use.
7. No integration may bypass Knowledge Engine provenance, legal-use gating, duplicate handling, human-review state, or reproducibility requirements.

## Planned integrations

| Project | Role | Default boundary | Status |
|---|---|---|---|
| Docling | Structured document parser | Python adapter behind `DocumentParser` | Evaluate first |
| MinerU | Alternate parser/OCR benchmark and fallback candidate | Adapter or isolated service | Benchmark |
| Stirling-PDF | PDF repair/OCR/preprocessing utility | External local REST/process service | Optional preprocessing |
| n8n | Cross-project orchestration | External self-hosted control plane | Architecture evaluation |

See the project-specific guides in this directory before implementing any of these systems.

## Decision rule

An evaluation is successful only if the external project measurably improves capability, reliability, development speed, or maintainability without weakening provenance, determinism, licensing safety, or the ability to replace it later.
