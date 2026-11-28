# Online evidence contract (KEC-1)

Status: implemented as `knowledge_engine/online_evidence.py` (schema `ke-online-evidence/v1`) with the
`ke online-evidence-validate` command. Roadmap: `docs/OWNER_APPROVED_ROADMAP_2026-10-25.md`, next slice 1.

`docs/schemas/online_evidence_v1.schema.json` is this contract's formal, machine-checkable JSON Schema,
printed by `ke online-evidence-schema` (`--output PATH` to write it to a file instead of stdout; an existing file is kept unless `--force` is given, and a symbolic link is always refused). It is
generated from `knowledge_engine/online_evidence_schema.py`, so a consumer repository (AI, Web) can
validate its own parser against Core's canonical contract instead of hand-copying field names that can
drift out of sync with Core. The schema's `required` lists are a **pinned v1 baseline**, written as
literal tuples in that module rather than derived from `online_evidence.py`'s current `dataclasses.fields`:
deriving `required` live would silently break the additive-only rule the moment a new, optional,
defaulted field was added to one of these dataclasses, since that field would instantly become required
on the wire. A field only leaves the pinned baseline when `ke-online-evidence/v1` is replaced by a new
major schema version. What *is* checked live against the dataclasses is coverage: every field a dataclass
currently carries must be a declared schema property (so a new field can never go undocumented), without
that property ever being forced into `required`. `tests/test_online_evidence_schema.py` checks the golden
fixture against this schema and fails if a required field is missing, renamed or retyped, if the committed
schema's `required`/`properties` diverge from the pinned baseline/dataclasses respectively, or if a newly
added optional field would stop an older bundle from validating. Changes within `ke-online-evidence/v1`
are additive only: a field already declared is never removed, renamed or retyped, and a newly added field
is always optional.

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
| — optional `provider_coverage` (`ProviderCoverage[]`: `provider`, `outcome`, `attempted`, `result_count`, `latency_ms`, `reason`) and `completeness` (`complete`/`partial`/`failed`/absent) | — | Additive-only (2026-11): the federated discovery providers actually attempted for this question, mirroring `federated_discovery.ProviderStatus`/`FederatedSearchResult.completeness`. A consumer reading the bundle alone can now learn a provider was skipped, rate-limited or failed, via the computed `OnlineEvidenceBundle.degraded_providers` property, without a second CLI call against Core's internal FRD ledger. Closes issue #433 item 2 ("federated provider latency/degradation") for the online-research path and unblocks `knowledge-engine-ai`'s documented `provider_coverage`/`degraded_providers` ResearchReport fields (`docs/roadmap/research_report_v1.md`). |

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

## Exporting the contract for consumer repos

`ke online-evidence-export-contract DIRECTORY` writes the committed golden
bundle fixture (`bundle.json` plus its `contents/` retrieval texts) and the
committed JSON Schema document into `DIRECTORY` in one deterministic call,
creating it if it does not exist. It refuses to write into an existing,
non-empty `DIRECTORY` and fails closed unless `--force` is given, so it never
silently overwrites or mixes in with something already there. The written
files are byte-identical to Core's own committed
`tests/fixtures/online_evidence/` and `docs/schemas/online_evidence_v1.schema.json`,
because the underlying `knowledge_engine.online_evidence_export.export_online_evidence_contract`
helper reuses `online_golden.write_golden_fixture` and
`online_evidence_schema.render_schema` rather than hand-copying files.

This is the integration surface `knowledge-engine-ai` and `knowledge-engine-web`
use to refresh their own contract-test fixtures from Core's exact current
contract artifacts, instead of the undocumented hand-copy each repo did
independently before. Running it again after a Core change and diffing the
result against what a consumer repo has committed detects drift the moment
Core's fixture or schema changes, rather than silently falling out of sync.
See `tests/test_online_evidence_export.py` for the regression coverage: byte
identity against the committed fixture/schema, the no-overwrite refusal
without `--force`, and that the exported bundle still validates with both
`ke online-evidence-validate` and the JSON Schema checker.

## End-to-end CLI proof

`tests/test_online_cli_end_to_end.py` runs `ke online-research` and `ke online-evidence-validate` as
subprocesses against a loopback HTTP source, with no corpus and the vector stack unimported (asserted).
It checks exact excerpt offsets against the cached bytes, recorded `failed` reasons for an HTTP 500 and an
over-limit response, no corpus/database/PDF artefacts, and fail-closed validation once the cache is cleared.
The subprocess runs the shipped app; `tests/test_online_cli_harness.py` only swaps in a stub discovery
provider and a loopback connection beneath the production `SafeHttpsFetcher`, so production keeps no bypass
of its public-HTTPS policy. This proves the Core half only; it is not live-provider or AI/Web evidence.

## Standalone integration fixture server

`ke online-evidence-fixture-server` (`knowledge_engine/online_evidence_fixture_server.py`) starts the exact
same loopback-only HTTP server as a standalone process -- not a private test harness and not a Python
import. It binds an ephemeral loopback port, prints `{"port": <int>, "pages": {"retrievable": <url>,
"http_500": <url>, "oversized": <url>}}` as one JSON line to stdout once it is accepting connections, then
blocks until stdin closes or it receives SIGTERM, shutting down cleanly either way.

The three page shapes are part of the contract and additive-only: `retrievable` is a citable page a
retrieval can quote, `http_500` always fails with HTTP 500, and `oversized` always returns a response over
`MAX_RESPONSE_BYTES`. A future change may add a new page shape, but never remove or change the meaning of
these three.

`oversized` is over the bound relative to `MAX_RESPONSE_BYTES` (100 000 bytes). In fixture mode
(`ke online-research --fixture-server-port`) the retrieval bound is therefore capped at
`MAX_RESPONSE_BYTES` even when `--max-response-mb` is omitted or larger, so consumers such as
knowledge-engine-ai and knowledge-engine-web always see `oversized` fail with
`exceeds 100000 bytes` without having to pass the flag.

This is the **supported integration-test fixture** for knowledge-engine-ai and knowledge-engine-web: a
consumer repository's own CI starts this command, parses its stdout for the port and page URLs, and runs
the real `ke online-research` then `ke online-evidence-validate` against it -- the same CLI boundary
`docs/core_interface_contract.md` already establishes -- instead of mocking the Core CLI boundary entirely.
`tests/test_online_cli_end_to_end.py` and `tests/test_online_cli_harness.py` start and reference this same
server code (`create_server`/`FixtureRequestHandler`, `GOOD_PATH`/`BROKEN_PATH`/`HUGE_PATH`) rather than
keeping a second, private copy of the page-serving logic, so Core's own end-to-end test and the public
command exercise identical server code. `tests/test_online_evidence_fixture_server_cli.py` spawns the
command itself as a subprocess, parses its announcement, runs `online-research`/`online-evidence-validate`
against it, and asserts the server exits cleanly within a bounded timeout once its stdin is closed.

**This proves the Core half only.** Running this fixture server and the two commands against it inside
Core's own test suite shows Core's CLI boundary works end to end against a known server; it does not
exercise knowledge-engine-ai's or knowledge-engine-web's own code at all. AI and Web each still owe their
own non-mocked subprocess test that starts this fixture server and runs their own pipeline against it --
this command only removes the excuse that the fixture logic was private to Core's test suite.

## Next slices
- **KEC-3:** bounded on-demand extraction that produces `OnlineSource` and `EvidenceExcerpt` records from fetched
  text, using a disk-bounded ephemeral cache keyed by `content_sha256`.
- **KEA-4:** the AI orchestrator emits an `OnlineEvidenceBundle` per request and refuses report claims whose
  `status` is `insufficient_evidence` without saying so.
- **KEW-3:** Web renders citations from the bundle and surfaces `contested` claims and unavailable sources.


### Supported integration consumer command (no private pytest harness)

An AI/Web CI job can invoke the **installed** `ke` CLI directly, rather than
importing Core internals or calling `tests/test_online_cli_harness.py`.
Start `ke online-evidence-fixture-server` as a separate process and read its
one-line JSON announcement. Its `port` is the only value supplied to the
next command:

```sh
KE_ALLOW_LOOPBACK_FIXTURE=1 ke online-research \
  "Does semaglutide reduce body weight versus placebo?" \
  --fixture-server-port "$PORT" \
  --cache-dir "$TMP/cache" --ledger-root "$TMP/ledger" \
  --output "$TMP/bundle.json" --max-response-mb 0.1 --cache-max-mb 1
ke online-evidence-validate "$TMP/bundle.json" --contents-dir "$TMP/cache"
```

The opt-in flag is **test-only**, rejects use unless the environment variable
is exactly `1`, and rejects mixing with live provider selections or API keys.
It substitutes a fixed three-page discovery provider and a transport that can
only connect to `127.0.0.1` at the specified port. The HTTP content is
untrusted fixture evidence, **not a real online source**; the separate
`bundle.json.discovery.json` receipt records `test_fixture: true`.
Ordinary `ke online-research` (without this flag) still requires normal
public HTTPS and retains its SSRF and redirect restrictions unchanged.

`tests/test_online_fixture_supported_cli.py` runs both CLI commands via the
production `knowledge_engine.command_surface` entrypoint in separate
subprocesses against the standalone fixture server. It proves successful,
failed and oversized source handling and validates exact cached excerpts,
and it verifies that attempting the fixture command without explicit
opt-in fails before it creates a cache or output. It does not execute
knowledge-engine-ai or knowledge-engine-web code; each consumer must exercise
its own report pipeline against this Core CLI seam before claiming end-to-end
product acceptance.
