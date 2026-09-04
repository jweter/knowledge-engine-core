from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def run_step(argv: list[str], root: Path) -> int:
    print("+ " + " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=root, check=False).returncode


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical repository preflight.")
    parser.add_argument("--evidence", default="preflight-evidence.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    control = json.loads(
        (root / "engineering" / "control-plane.json").read_text(encoding="utf-8")
    )
    results = []
    overall = "GREEN"
    for check in control["preflight"]["checks"]:
        returncode = run_step(check["argv"], root)
        results.append(
            {
                "id": check["id"],
                "kind": check["kind"],
                "status": "PASS" if returncode == 0 else "FAIL",
                "returncode": returncode,
            }
        )
        if returncode != 0:
            overall = "FAILED"
            break

    evidence = {
        "schema_version": 1,
        "repository": control["repository"],
        "head_sha": git_head(root),
        "mode": "FULL",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": overall,
        "checks": results,
    }
    path = root / args.evidence
    path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if overall == "GREEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
