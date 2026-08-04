# Documentation Index

Start with the root `README.md` for setup and CLI usage. This index maps
what's here in `docs/` for anyone navigating the project for the first
time. Historical, point-in-time documents (milestone build logs, the
original prototype narrative, one-off status reports) live in
`history/`, out of the way of what's still current -- see
`history/README.md`.

## Start here

- **`roadmap.md`** -- the roadmap index: phase status, completed
  milestones, and what's next. The best single entry point.
- **`architecture.md`** -- what this system is and isn't today.
- **`project_principles.md`** -- the standing principles the project
  holds itself to.
- **`glossary.md`** -- core terminology, defined precisely.
- **`decisions.md`** -- a lightweight index of significant project
  decisions and why they were made.

## Interfaces and contracts

- **`core_interface_contract.md`** -- the CLI surface, config, and
  record schemas `core` exposes to consumers like `knowledge-engine-web`
  and `knowledge-engine-ai`.
- **`scientific_data_model.md`** -- the canonical conceptual data model.
- **`google_drive_adapter_contract.md`**, **`google_drive_project_boundary.md`**,
  **`google_drive_backup_pilot.md`** -- the Google Drive backup
  integration's boundaries and the `ke-drive-backup-pilot` command.
- **`sqlite_backup_bundle.md`** -- the only approved way to back up the
  live SQLite database.
- **`corpus_pdf_backup.md`** -- the `ke-corpus-pdf-backup` command.

## Design and phase docs

- **`phase1_design.md`** / **`phase2_design.md`** / **`phase3_design.md`** /
  **`phase4_design.md`** -- the implementation-ready design for each
  roadmap phase (corpus ingestion, evidence records, search, knowledge
  graph). `roadmap/` holds the higher-level phase goal statements these
  designs implement.
- **`reference_knowledge_layer_design.md`** -- the reference-lookup
  layer (Wikipedia, RxNorm, MeSH, PubChem) design.
- **`stability_and_tracking_design.md`** -- the relationship-edge
  stability model and "tracking the unknown" principle behind
  `ke graph-unconfirmed-claims`.
- **`ai_interface_layer_scoping.md`** / **`ai_layer_architecture.md`**
  -- scoping and architecture notes for the future `knowledge-engine-ai`
  judgment layer. Records of ideas, not implementation-ready designs.
- **`evidence_intelligence_design.md`** -- the deterministic,
  no-LLM confidence-scoring formula (Evidence Quality / Evidence
  Consensus / Claim Confidence) both documents above named as their own
  trigger condition. Implementation-ready, unlike its two predecessors.
- **`glp1_body_weight_golden_evidence_map.md`** -- the reviewed first golden
  map and its validation and deterministic cross-study reporting contracts.
- **`glp1_cross_study_comparison_plan.md`** -- the written Goal 4 handoff from
  the reviewed map to `ke evidence-map-report`, including the boundary before
  typed statistical inputs and effect recomputation.
- **`glp1_typed_statistical_inputs_plan.md`** -- the implementation contract
  for source-linked statistical inputs and the first deterministic STEP 5
  reported-effect verification.
- **`founding_vision.md`** -- the project's original founding proposal,
  preserved verbatim.
- **`future_ideas.md`** -- promising ideas parked outside the current
  roadmap.

## Ongoing trackers

- **`technical_debt.md`** -- known technical debt, kept current.
- **`error_resolution_ledger.md`** -- the authoritative record of
  recurring repository/CI failures and their verified fixes. Add an
  entry here whenever you resolve a non-obvious failure.

## Subdirectories

- **`roadmap/`** -- phase-by-phase goal statements (`phase0.md`
  through `phase3.md`) and `long_term_vision.md`, the multi-package
  ecosystem plan `founding_vision.md` translates into concrete scope.
- **`architecture/`** -- Architecture Decision Records (`adr/`) and
  diagrams.
- **`releases/`** -- versioned release notes.
- **`research/`** -- reserved for future research notes; empty today.
- **`history/`** -- point-in-time record: milestone build logs, the
  original vertical-slice prototype, and standalone status/audit
  reports. See `history/README.md`.
