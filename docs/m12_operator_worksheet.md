# M12 100-Paper Rehearsal Operator Worksheet

This worksheet records measurements that are not stored by the current database schema. Complete it locally during the real legally usable 100-paper rehearsal. Replace private machine paths, usernames, hostnames, and restricted source details before committing any reviewed aggregate findings.

## Rehearsal identity

- Date:
- Operator:
- Git branch:
- Git commit:
- Corpus ID:
- Manifest snapshot SHA-256:
- Fresh import run ID:
- Resume/rerun run ID:
- Retry run ID, when applicable:

## Corpus preflight

- Included and importable rows: `100`
- Manifest validity:
- Import readiness:
- Present local PDFs:
- Missing local PDFs:
- Rows with unresolved legal status:
- Rows with missing source URL:
- Rows with missing access date:
- Rows with missing inclusion reason:
- Known expected duplicates:
- Preflight command:
- Preflight result reviewed by:

Do not begin the real import unless exactly 100 included rows are legally usable, locally present, and import-ready.

## Environment

Record versions without private installation paths.

- Operating system and version:
- CPU model / logical cores:
- Installed memory:
- Python version:
- Poetry version:
- Knowledge Engine version/commit:
- PyMuPDF version:
- SQLAlchemy version:
- SQLite version:
- Filesystem type, when known:
- Power mode / notable resource constraints:

## Fresh run measurements

- Command:
- Wall-clock start timestamp:
- Wall-clock end timestamp:
- Elapsed duration:
- Database size before:
- Database size after:
- Peak memory, when externally measured:
- Average/peak CPU, when externally measured:
- Manual interventions:
- Terminal or application errors observed:

### Fresh run persisted outcomes

Copy these from `ke corpus-run-report <run-id>` rather than calculating them from terminal prose.

- Declared source rows:
- Persisted import items:
- Imported:
- Duplicates:
- Failed:
- Skipped:
- Needs review:
- Matched paper records:
- Matched prior import items:
- Retry-linked items:
- Warning issues:
- Manifest-blocking issues:
- Import-blocking issues:

## Resume or idempotent rerun

- Command:
- Parent run ID:
- Child run ID:
- Start timestamp:
- End timestamp:
- Elapsed duration:
- Newly created paper records:
- Previously successful items linked/skipped:
- Duplicate outcomes:
- Unexpected reimports:
- Reconciliation result:

Acceptance requires no duplicate creation of papers that were already imported successfully.

## Failed-item retry

Complete this section only when real retryable failures exist. Do not manufacture failures in the real corpus.

- Original failed-item count:
- Corrected local/environmental cause:
- Retry command:
- Retry run ID:
- Retried item count:
- Recovered item count:
- Still-failed item count:
- Successful items incorrectly retried:
- Parent/retry lineage verified:

When no real retryable failures occur, state that retry behavior remains verified by synthetic automated tests only.

## Technical-debt findings

Use one block per observed finding.

### Finding ID

- Category:
- Evidence:
- Affected run/item IDs:
- Operational impact:
- Reproduction steps:
- Smallest proposed fix:
- M12 blocker: yes/no
- Recommended milestone: M12/M13/later

Required categories to consider:

- parser failure;
- empty or malformed document;
- duplicate ambiguity;
- legal or provenance gap;
- metadata conflict/reporting gap;
- performance bottleneck;
- resume or retry defect;
- reporting or schema gap.

## Review and sanitization

Before committing aggregate results:

- [ ] No PDFs or extracted full text are staged.
- [ ] No SQLite databases or journal files are staged.
- [ ] No private absolute paths remain.
- [ ] No usernames, hostnames, tokens, or credentials remain.
- [ ] No raw provider responses remain.
- [ ] Every count reconciles with a generated run report.
- [ ] Operator-recorded measurements are labeled separately from persisted measurements.
- [ ] Synthetic results are not represented as the real rehearsal.
- [ ] Scientific validation or synthesis is not claimed.

## Acceptance decision

- Real 100-paper preflight passed: yes/no
- Fresh run completed with understandable partial success: yes/no
- Idempotent rerun demonstrated: yes/no
- Retry behavior verified: real/synthetic/not verified
- Technical-debt blockers resolved: yes/no
- Exact final PR head Quality gate passed: yes/no
- Ready to mark PR for review: yes/no

Reviewer notes:
