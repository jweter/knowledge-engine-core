# Cross-Project External Repository Research Ledger

Last reviewed: 2026-08-27

This is the durable cross-project inventory for external repositories, tools, and reference implementations researched for the managed portfolio. It exists so useful discoveries cannot disappear into chat history or be mistaken for completed integrations.

The detailed project-specific integration indexes remain authoritative for implementation boundaries:

- Knowledge Engine: `knowledge-engine-core/docs/integrations/README.md`
- Rocksmith CDLC Generator: `rocksmith-cdlc-generator/docs/integrations/README.md`
- Everward: `Project-Everward/docs/integrations/README.md`

This ledger is the inventory and disposition layer above those project-specific guides.

## Status vocabulary

| Status | Meaning |
|---|---|
| `IMPLEMENTED` | Integration is production-reachable and its intended current scope is complete. |
| `PARTIAL` | Meaningful integration exists, but planned parity/scope remains. |
| `PLANNED` | Approved for evaluation or future implementation behind a project-owned boundary. |
| `REFERENCE_ONLY` | Study architecture/methodology; do not adopt as a runtime dependency without a new decision. |
| `DEFERRED` | Retained intentionally but not currently prioritized. |
| `REJECTED` | Evaluated and intentionally not proceeding. Keep the entry and reason; do not silently delete it. |
| `NEEDS_REVERIFICATION` | Recovered research candidate whose exact upstream identity, license, fit, or disposition must be rechecked before implementation. |

## Governance

1. Every newly researched external repository that may affect a managed project must be added here before substantive integration work begins.
2. An entry is never silently removed. If it is no longer useful, change it to `REJECTED` and record why.
3. `PLANNED` and `NEEDS_REVERIFICATION` are not implementation approval. License, security, maintenance, model/data terms, and architecture must be rechecked at the time of adoption.
4. External systems remain replaceable behind project-owned adapters, subprocesses, services, plugins, or reference-only boundaries.
5. External output is never authoritative merely because a provider generated it. Existing provenance, validation, human-review, simulation, packaging, and scientific-evidence gates remain in force.
6. When implementation begins, record the project issue/PR or project-specific integration guide in this ledger.
7. When implementation materially advances, update the status here in the same development cycle or the next continuity update.

## Knowledge Engine

Source of detailed truth: `docs/integrations/README.md` in `jweter/knowledge-engine-core`.

| Project | Intended role | Status | Current disposition |
|---|---|---|---|
| Docling | Structured document parser | `PLANNED` | Evaluate first behind `DocumentParser`; canonical KE models and provenance remain authoritative. |
| MinerU | Parser/OCR benchmark and fallback candidate | `PLANNED` | Benchmark through an adapter or isolated service. |
| Marker | Structured parser candidate | `PLANNED` | Benchmark behind the canonical parser contract. |
| MORE | Parser benchmark methodology | `REFERENCE_ONLY` | Adopt useful methodology, not upstream architecture as authority. |
| Provenance | Source-span provenance/verifier architecture | `REFERENCE_ONLY` | High-priority study for verifier architecture. |
| Ethos | Citation-region validation and staleness concepts | `REFERENCE_ONLY` | High-priority study; optional verifier adapter only after review. |
| Stirling-PDF | PDF repair/OCR/preprocessing utility | `DEFERRED` | Optional local preprocessing service if a concrete need justifies it. |
| n8n | Cross-project orchestration | `PLANNED` | Architecture evaluation as an external self-hosted control plane. |

## Rocksmith CDLC Generator

Source of detailed truth: `docs/integrations/README.md` in `jweter/rocksmith-cdlc-generator`.

| Project | Intended role | Status | Current disposition |
|---|---|---|---|
| Editor on Fire (EOF) | Guitar Pro/Rocksmith compatibility oracle and external review surface | `PARTIAL` | Bridge and multiple parity/reference slices are implemented; additional EOF parity work remains. |
| WhisperX | Speech/vocal timing and forced-alignment evidence | `PLANNED` | Evaluate narrowly as an isolated optional analysis provider. |
| Basic Pitch | Audio-to-MIDI / note evidence | `PLANNED` | High-priority evaluation behind `NoteEvidenceProvider`; never arrangement authority. |
| Demucs lineage / StemSplit | Stem separation | `PLANNED` | Compare maintained implementations behind `StemProvider`. |
| librosa | Deterministic DSP primitives | `PLANNED` | Evaluate a direct dependency inside a Rocksmith-owned service wrapper. |
| demixer | End-to-end music-analysis architecture | `REFERENCE_ONLY` | Architecture study only. |

## Everward

Source of detailed truth: `docs/integrations/README.md` in `jweter/Project-Everward`.

| Project | Intended role | Status | Current disposition |
|---|---|---|---|
| ComfyUI | Local generative image/video authoring backend | `PLANNED` | Evaluate for asset ideation/production; Unreal remains runtime authority. |
| Krita AI Diffusion | Artist-in-the-loop image editing | `PLANNED` | Evaluate as an external authoring application/plugin. |
| ViMax | Storyboard/video production reference and optional marketing pipeline | `PLANNED` | Evaluate outside packaged gameplay. |
| Remotion | Programmable trailer/devlog/video compositor | `PLANNED` | Evaluate as a separate media-tool process. |
| SUSS | Utility AI scoring/execution candidate | `PLANNED` | High-priority evaluation behind Everward-owned behavior/state contracts. |
| UE-MCP / Monolith / Hayba | AI-assisted Unreal development tooling | `PLANNED` | Compare and choose only if source-control/CI/review boundaries remain intact. |
| SimWorld | World-observation/action separation reference | `REFERENCE_ONLY` | Architecture study only. |

## Portfolio security / secret-leak research

These candidates were evaluated from the 2026-08-27 GitHub-secret-scanning research batch. The goal is defensive protection of the managed public repositories and their history, not broad third-party reconnaissance. Repository-wide automation must use least-privilege credentials and may scan only repositories/accounts Jeremy owns or is authorized to audit.

| Candidate | Upstream / evidence | Status | Current disposition |
|---|---|---|---|
| TruffleHog | `trufflesecurity/trufflehog`; actively maintained; AGPL-3.0 | `IMPLEMENTED` | PR/push secret gates are deployed across all five managed repos using pinned TruffleHog v3.97.1 and release SHA-256 `f863ea3a8d786f7d097870496c977944cce7372a2fe1e56707d965016e543ece`, read-only access, `--no-verification`, suppressed finding payloads, and an ephemeral synthetic detection self-test. Core #426, Web #91, AI #77, Rocksmith #441, and Everward #119 are merged; post-merge native CI and TruffleHog push scans are green across the portfolio. Scheduled/manual deep-history auditing is a distinct follow-up tracked by Core issue #430. |
| GitHound | `tillson/git-hound`; MIT; maintained into 2026 | `REFERENCE_ONLY` | Useful periodic owner-scoped/public-exposure audit and GitHub-dork reference, but not needed in normal CI now that TruffleHog is adopted. Do not use for unrelated third-party reconnaissance. |
| GitHub-Dorks | `techgaun/github-dorks`; Apache-2.0; maintained into 2025 | `REFERENCE_ONLY` | Retain its search patterns as a manual/periodic defensive audit reference for Jeremy-owned repositories; not a CI dependency. |
| git-secrets | `awslabs/git-secrets`; Apache-2.0; maintained into 2025 | `DEFERRED` | Solid lightweight pre-commit prevention, but materially overlaps the implemented TruffleHog control. Reconsider only if a simpler local hook is needed on machines where TruffleHog is impractical. |
| GitGot | `BishopFox/GitGot`; LGPL-3.0; last pushed 2024 | `REJECTED` | Capable GitHub secret/recon search, but redundant with the newer TruffleHog + GitHound/GitHub-Dorks defensive stack and less current. |
| GitMonitor | `Talkaboutcybersecurity/GitMonitor`; LGPL-3.0; last pushed 2020 | `REJECTED` | Continuous-monitoring idea is useful, but implementation is stale and superseded by maintained scanners and native GitHub controls. |
| GitRob | `michenriksen/gitrob`; MIT; archived | `REJECTED` | Historically useful organization recon tool, but upstream is archived and its role is covered by maintained alternatives. |
| GittyLeaks | `kootenpv/gittyleaks` appears to be the surviving upstream; last pushed 2020; no detected repository license | `REJECTED` | Stale, licensing is unclear, and functionality is redundant with maintained scanners. |
| Watchtower / Nightfall | Current product is Nightfall AI DLP, not an open-source repo | `DEFERRED` | Potential future SaaS DLP for organization-wide GitHub/AI/SaaS monitoring, but it introduces cost, external data processing, and vendor dependence. Not justified for the current portfolio while self-hosted/open-source scanning is sufficient. |

### TruffleHog rollout boundary

- Use TruffleHog as an external security tool; do not copy its AGPL source into managed repositories.
- The current rollout pins the official v3.97.1 Linux amd64 release archive by SHA-256 rather than using a mutable `latest` action/image.
- Give the workflow read-only repository contents/history access unless a later remediation feature is explicitly approved.
- Do not upload findings as public artifacts; logs must avoid printing discovered secret values.
- PR/push scanning is focused on introduced history and is deployed across all five managed repos.
- Credential verification can cause outbound requests to credential providers. The current portfolio gate uses `--no-verification`.
- Each workflow generates an ephemeral synthetic private-key fixture outside Git history and requires TruffleHog exit 183, proving detection is live without committing a credential fixture.
- A finding is a security incident/gate, not an auto-remediation authority. Rotate/revoke any real exposed credential and remove it from reachable history through an explicit incident process.
- Native GitHub secret-scanning/push-protection settings, where available, should complement this control rather than be disabled.
- Core issue #430 tracks the distinct scheduled/manual deep-history audit and baseline-finding triage; that follow-up does not weaken or make incomplete the currently implemented PR/push gate scope.

## Recovered secondary research batch

These names were researched during the broader media/AI repository survey but were not promoted into any durable project integration index. They are preserved here now so they cannot be lost again. They are **not approved dependencies**. Exact upstream repository identity, current license, maintenance status, project fit, and intended boundary must be re-verified before any implementation decision.

| Candidate | Research bucket | Status | Next action |
|---|---|---|---|
| Toonflow | Media / AI workflow research | `NEEDS_REVERIFICATION` | Re-identify the exact upstream repo, license, and whether it adds anything beyond the canonical Everward media stack. |
| Jellyfish | Media / AI workflow research | `NEEDS_REVERIFICATION` | Re-identify upstream and evaluate role/overlap before assigning to a project. |
| Moyin Creator | Media / AI workflow research | `NEEDS_REVERIFICATION` | Re-identify upstream, license, and media-pipeline value. |
| Pallaidium | Media / AI workflow research | `NEEDS_REVERIFICATION` | Re-identify upstream and determine whether it belongs in asset, 3D, or media tooling. |
| KrillinAI | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify upstream and evaluate localization/media applicability. |
| FunClip | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify upstream and evaluate editing/subtitle/media applicability. |
| MultiTalk | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify upstream and evaluate whether it has any useful non-runtime media role. |
| MMAudio | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify upstream and evaluate audio-generation/sound-design applicability and licensing. |
| Helios | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify the exact project before assigning any role. |
| Medusa | Secondary AI/media research | `NEEDS_REVERIFICATION` | Re-identify the exact project before assigning any role. |

ViMax is not duplicated in this recovered table because it was successfully promoted into Everward's canonical integration index.

## Update checklist

When a candidate changes state, record:

- exact upstream repository/project identity;
- reviewed version/commit;
- license and model/data-license notes where relevant;
- owning project(s);
- adapter/service/plugin/reference boundary;
- issue or PR implementing/evaluating it;
- regression/Product Reality requirements;
- current status and next action.

The purpose of this ledger is continuity, not accumulation. Keep candidates visible, but only promote them when they measurably improve capability, reliability, development speed, or maintainability without weakening project-owned authority and safety boundaries.
