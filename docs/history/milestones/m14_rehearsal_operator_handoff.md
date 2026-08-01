# M14 Operator Handoff

The next operator must have local access to the legally curated 500-paper corpus and an external writable database location.

Before running any import, the operator must verify the entry gate in `m14_controlled_rehearsal_runbook.md`, preserve the manifest hashes, and confirm the working tree is clean. If any entry condition fails, populate the stopped-state evidence and do not attempt a reduced or synthetic rehearsal.

During execution, record only sanitized aggregate evidence. Do not commit source PDFs, local database files, raw logs, raw exception messages, absolute paths, or environment identifiers.

After execution, validate the evidence JSON against `m14_rehearsal_evidence.schema.json`, complete the report template, run the exact-head quality suite, inspect the full diff, and update Issue #21 with the measured decision and exact continuation point.