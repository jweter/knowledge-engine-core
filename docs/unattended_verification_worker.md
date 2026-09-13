# Knowledge Engine unattended verification worker

Issue: #493

## Purpose

Routine environment verification must be machine-owned. This worker provides the Core-side bounded request/result contract for unattended checks on a local machine without making Jeremy the transport layer for commands, logs, or deterministic PASS/FAIL evidence.

The worker is deliberately narrower than a general remote shell. A request names an exact repository, branch, 40-character commit SHA, and one allow-listed probe. Unknown fields and unknown probes fail closed.

## Current probes

- `preflight` — executes the repository's canonical `engineering/preflight.py` against the exact checkout head and stores its evidence under the private worker state directory.
- `ollama_health` — checks only the loopback Ollama `/api/tags` endpoint and records HTTP status, elapsed time, and model count. It never uploads model names or prompt/content data.

Later research-benchmark and acquisition/re-retrieval probes must be added as explicit allow-listed operations with their own deterministic tests; they must not be implemented as arbitrary command passthrough.

## Request contract

```json
{
  "schema_version": 1,
  "request_id": "ke-ai-154-cold-run-001",
  "repository": "jweter/knowledge-engine-core",
  "branch": "main",
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "probe": "preflight",
  "timeout_seconds": 3600
}
```

Run with:

```text
poetry run ke-unattended-worker --request request.json --repo-root <dedicated-checkout>
```

The worker refuses a checkout whose `origin` is not `jweter/knowledge-engine-core` or whose current `HEAD` is not the requested exact SHA.

## Result contract

Every accepted request writes an atomic JSON result with:

- request id, repository, branch, exact SHA, and probe;
- `PASS`, `FAIL`, `REVIEW_REQUIRED`, `PRODUCT_REALITY_REQUIRED`, `ENVIRONMENT_FAILURE`, or `BUSY`;
- start/finish timestamps and elapsed time;
- bounded environment identity (`python` and platform only);
- probe-specific verification evidence;
- a sanitized reason when the request cannot pass.

Default private state is `%LOCALAPPDATA%\KnowledgeEngine\unattended-worker\` on Windows (or `~/.knowledge-engine/unattended-worker` elsewhere). Detailed logs stay there unless a later reporter explicitly sanitizes an approved subset for GitHub.

## Safety and privacy boundaries

- No arbitrary command execution from request JSON.
- No destructive Git reset/clean in this first slice.
- No secrets, private documents, prompts, model names, unrelated local files, or raw research payloads belong in repository-facing results.
- Paths and common secret assignments are redacted from bounded failure tails.
- A PID lock prevents overlap; stale locks are reclaimed after crashes/reboots.
- Missing tooling, wrong checkout identity, timeouts, and unavailable Ollama fail closed rather than becoming PASS.
- A local machine/environment dependency is not a human dependency. The scheduler should leave independent work live while an environment probe is pending.

## Next slices

1. Dedicated disposable-checkout bootstrap and current-user idle scheduling on Windows.
2. Sanitized GitHub result reporting tied to the requesting issue/PR.
3. Explicit persistent-store cold/warm research benchmark probes for AI #154.
4. Acquisition -> promotion -> re-retrieval acceptance probes with source-link evidence.
5. Web #160 browser/service probes consuming the same request/result semantics.

Human attention remains reserved for product direction, privacy/security boundary decisions, and genuinely subjective acceptance. Routine commands, benchmark reruns, service checks, and log relay are automation debt.
