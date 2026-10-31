# Online evidence contract (KEC-1)

Status: implemented as `knowledge_engine/online_evidence.py` (schema `ke-online-evidence/v1`) with the
`ke online-evidence-validate` command. Roadmap: `docs/OWNER_APPROVED_ROADMAP_2026-10-25.md`, next slice 1.

Research Reports retrieve sources online, on demand: user question → online discovery → source retrieval →
evidence excerpts → claims with citations → report. Nothing in this path requires a preloaded corpus or a PDF
warehouse on the operator's machine. This contract is the hand-off format between those steps (Core extraction,
AI orchestration, Web rendering). It represents and checks evidence; it never fetches, summarizes, scores, or decides
whether a claim is true.

## Data contract

| Record | Required fields | Invariant |
|---|---|---|
| `OnlineSource` | `source_id`, `url` (http/https), `retrieved_at` (ISO-8601 UTC), `status`, `provider` | `source_id` is derived from the strongest identifier: `doi:` > `pmcid:` > `pmid:` > `arxiv:` > `url:<sha256-16>`. The same work gets the same ID in every run. |
| — retrieved | `content_sha256` of the retrieved text | No `failure_reason` |
| — `unavailable` / `not_permitted` / `failed` | `failure_reason` | No content hash; **can never be quoted** |
| `EvidenceExcerpt` | `excerpt_id`, `source_id`, verbatim `text` (≤ 1200 chars); optional `char_start`/`char_end`, `locator` | `excerpt_id = <source_id>#sha256(source, offset, text)[:12]`; offsets span exactly the text |
| `Citation` | `excerpt_id`, `stance` (`supports` / `contradicts` / `inconclusive`) | Must name an excerpt in the bundle |
| `EvidenceClaim` | `claim_id`, `text`, `citations` | `status` is **computed**: supports and contradicts together → `contested`; no supporting or contradicting citation → `insufficient_evidence` |
| `OnlineEvidenceBundle` | `question`, `sources`, `excerpts`, `claims` | Unique IDs; excerpts only from retrieved sources; citations only to known excerpts |

`OnlineSource.from_observation` records the retrieval of a federated-discovery `ProviderObservation`
(`knowledge_engine/federated_discovery.py`), carrying over its identifiers, provider and licence.

**No fabricated citations.** `verify_against_retrieved_content(bundle, contents)` (CLI: `--contents-dir`, files
named `<content_sha256>.txt`) re-hashes each retrieved text and requires every excerpt to occur verbatim in it, at
its offsets when they're given. Fabricated, edited or moved quotes are reported, and so is a retrieved source whose
text isn't supplied.

## Corpus-dependent interfaces and their replacements

| Interface | Corpus dependency today | Replacement in the online path |
|---|---|---|
| Evidence Records' `source_span.local_pdf_path` (`data/corpora/*/evidence_records.jsonl`), resolved by `cli.py` (`_resolve_source_page_text`, around line 998) against `Paper.source_path` | The quote is located through a PDF stored in the local corpus | `EvidenceExcerpt` plus `OnlineSource`: URL, retrieval time, content hash and character offsets |
| `golden_map_grounding.py` | Grounds golden-map claims in locally stored PDFs | `verify_against_retrieved_content` over retrieved text |
| `corpus_readiness.py` / `corpus_readiness_cli.py` | Manifest-plus-receipt readiness of a local PDF corpus before research | Not needed per request: a source either has a retrieval record or a stated failure |
| `corpus_library*.py`, `drive_boundary.py`, `research_workspace.py` | Persistent corpus library seed, backup and restore | Optional offline capability only; never a prerequisite of a Research Report |
| Acquisition CLIs (`reviewed_approval_cli.py`, `europepmc_reviewed_approval_cli.py`, `manifest_curation_cli.py`, `candidate_review_cli.py`, `pdf_calibration_cli.py`) | Curate PDFs into the corpus | Unchanged curation tools; the online path retrieves per request instead |

## Next slices
- **KEC-3:** bounded on-demand extraction that produces `OnlineSource` and `EvidenceExcerpt` records from fetched
  text, using a disk-bounded ephemeral cache keyed by `content_sha256`.
- **KEA-4:** the AI orchestrator emits an `OnlineEvidenceBundle` per request and refuses report claims whose
  `status` is `insufficient_evidence` without saying so.
- **KEW-3:** Web renders citations from the bundle and surfaces `contested` claims and unavailable sources.
