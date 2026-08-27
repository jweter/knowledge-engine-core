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
