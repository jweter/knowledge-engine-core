# M55: Scheduled Discovery-Cycle Orchestration

## Purpose

Every corpus-growth batch through M54 was driven by hand: run `ke
pubmed-candidate-discover` for the next `retstart` page, prepare an
adjudication worksheet, manually cross-check against
`data/corpora/glp1_weight_loss/README.md`'s prose exclusion history (the
structural gap M53's rejected-PMID ledger closed), and manually track
which `retstart` offset came next. The project owner's stated end state
is a live, connected system that keeps discovering new evidence on its
own, not a one-time corpus snapshot -- see
`docs/roadmap/long_term_vision.md`'s "The Finished Product Is Not an
Offline PDF Archive" section. `ke discovery-cycle-run`
(`knowledge_engine/discovery_cycle.py`) is the piece that makes the
*mechanical* part of that loop schedulable.

## What it does, and does not do

Each cycle:

1. Discovers the next page of PubMed/PMC OA candidates at a persisted
   `retstart` offset (0 on a first run for a given `--state` file).
2. Deterministically adjudicates each candidate with M14's existing
   scope/identity/license/full-text rules, unchanged.
3. Cross-checks every deterministically "accepted" candidate against
   the M53 rejected-PMID ledger, dropping any this project has already
   reviewed and rejected.
4. Advances the `--state` file's `retstart` offset by `--limit` for the
   next cycle.

It deliberately **stops before acquisition**. M14's deterministic scope
adjudication alone has a measured, real residual false-accept rate: this
project's own growth-batch history (see the README's `retstart=3000`/
`retstart=3250` correction episodes) found roughly a fifth of
deterministically "accepted" candidates in several real batches were
still off-topic on a human/AI title-and-abstract read (busulfan
pharmacokinetics, off-target primary diseases, diagnostic-only studies,
and similar). That is a materially different risk than, say, M52's
evidence-direction classification: an admitted-then-extracted wrong
paper contaminates the corpus in a way that is expensive to find and
reverse -- this project has already run a full fresh reimport twice to
correct exactly that. So each cycle writes a bounded `ready_for_scope_review`
list of net-new accepted candidates to `--output`, for a human or agent
to give the same final scope screen this project has always required.
Running `ke pmc-oa-acquire` against the reviewed result remains a
separate, explicit step this command never triggers itself.

## Usage

```bash
ke discovery-cycle-run \
  --query "GLP-1 receptor agonist AND obesity" \
  --state data/corpora/glp1_weight_loss/discovery_state.json \
  --ledger data/corpora/glp1_weight_loss/rejected_candidates.csv \
  --output data/corpora/glp1_weight_loss/cycles/cycle-$(date +%Y%m%d-%H%M%S).json \
  --limit 25
```

`--state` is keyed to one `--query` string; pointing an existing state
file at a different query is a hard error (never silently reuses or
resets pagination for the wrong query -- see
`knowledge_engine.discovery_cycle.load_discovery_cycle_state`). Use a
different `--state` path to run more than one query concurrently.

The full pipeline from here, still each an explicit, separate step:

```
ke discovery-cycle-run          # this command: discover, adjudicate, ledger-check
  -> (human/agent scope review of ready_for_scope_review)
ke pmc-oa-acquire                # M9: download PDFs for the reviewed candidates
ke corpus-import                 # persist papers, parse, dedupe
ke extraction-review-batch-generate
ke extraction-review-autoclassify  # M52: automated research_question/evidence_direction
ke extraction-review-promote       # append to evidence_records.jsonl
ke graph-build                     # M54: incremental -- only new records cost network calls
ke graph-citations-build
```

## Scheduling it

`ke discovery-cycle-run` is a plain CLI command with no daemon of its
own -- schedule it with whatever mechanism the host environment already
uses. Two concrete examples for a self-hosted Linux server (the "local
server to start" deployment target):

**crontab** (`crontab -e`), once daily at a quiet hour:

```cron
7 3 * * * cd /path/to/knowledge-engine-core && /path/to/poetry run ke discovery-cycle-run --query "GLP-1 receptor agonist AND obesity" --state data/corpora/glp1_weight_loss/discovery_state.json --ledger data/corpora/glp1_weight_loss/rejected_candidates.csv --output "data/corpora/glp1_weight_loss/cycles/cycle-$(date +\%Y\%m\%d).json" --limit 25 >> /var/log/knowledge-engine/discovery-cycle.log 2>&1
```

**systemd timer** (`/etc/systemd/system/ke-discovery-cycle.service`):

```ini
[Unit]
Description=Knowledge Engine discovery cycle (M55)

[Service]
Type=oneshot
WorkingDirectory=/path/to/knowledge-engine-core
ExecStart=/path/to/poetry run ke discovery-cycle-run \
  --query "GLP-1 receptor agonist AND obesity" \
  --state data/corpora/glp1_weight_loss/discovery_state.json \
  --ledger data/corpora/glp1_weight_loss/rejected_candidates.csv \
  --output data/corpora/glp1_weight_loss/cycles/cycle-%%Y%%m%%d.json \
  --limit 25
```

`/etc/systemd/system/ke-discovery-cycle.timer`:

```ini
[Unit]
Description=Run the Knowledge Engine discovery cycle daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

Enable with `systemctl enable --now ke-discovery-cycle.timer`.

Neither example is installed by this project -- they are deliberately
left as documentation, not automatically applied, since the actual
deployment host, its Python/Poetry path, and its log destination are
all environment-specific decisions for whoever operates the server.

## What was live-verified

Against the real PubMed/PMC APIs (read-only, small `--limit`, no
acquisition): a first cycle at `retstart=0` correctly discovered,
adjudicated, and wrote a `ready_for_scope_review` worksheet; a second
cycle resumed from the persisted `retstart=5` and advanced to `10`;
adding the first cycle's one accepted PMID to a real rejected-PMID
ledger and re-running the same `retstart=0` page correctly excluded it
from `ready_for_scope_review` (`already_in_rejected_ledger: 1`,
`ready_for_scope_review: []`).

## What is deliberately not built here

- **Acquisition, import, and extraction remain manual, separate steps.**
  Automating the scope-precision judgment call itself (not just the
  mechanical parts around it) is a real, larger decision about how much
  residual corpus-quality risk this project is willing to accept
  unattended -- flagged here, not decided here, matching this project's
  established practice for exactly this kind of tradeoff (see M52's
  "seam" revision in `docs/core_interface_contract.md` for the shape
  that decision took when the project owner did make it explicitly for
  evidence-direction classification).
- **No daemon, no built-in scheduler, no retry/alerting logic.** This
  command does one cycle and exits; wiring it to actually run
  unattended (cron, systemd, a cloud scheduler, container orchestration)
  is an operator decision for the actual deployment host, documented
  above as examples, not shipped as infrastructure this project owns.
- **Multi-corpus / multi-query orchestration.** One `--state` file
  tracks one query's pagination; running several queries or corpora
  concurrently means invoking this command multiple times with
  different `--state`/`--ledger`/`--output` paths, which the scheduling
  examples above do not attempt to show.
