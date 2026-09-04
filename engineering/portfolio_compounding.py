from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN"
REPOSITORIES = {
    "knowledge-engine-core": "knowledge-engine",
    "knowledge-engine-web": "knowledge-engine",
    "knowledge-engine-ai": "knowledge-engine",
    "rocksmith-cdlc-generator": "rocksmith",
    "Project-Everward": "everward",
}

def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def load_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 2:
        raise SystemExit(f"{path}: compounding report schema_version must be 2")
    if not isinstance(payload.get("windows"), dict):
        raise SystemExit(f"{path}: windows are required")
    if not isinstance(payload.get("evidence_derived"), dict):
        raise SystemExit(f"{path}: evidence_derived is required")
    return payload


def geometric_mean(values: list[float]) -> float | str:
    if not values or any(value <= 0 for value in values):
        return UNKNOWN
    product = 1.0
    for value in values:
        product *= value
    return round(product ** (1.0 / len(values)), 4)


def weighted_rate(rows: list[tuple[float, int]]) -> float | str:
    usable = [(value, weight) for value, weight in rows if weight > 0]
    if not usable:
        return UNKNOWN
    total = sum(weight for _value, weight in usable)
    return round(sum(value * weight for value, weight in usable) / total, 4)


def repository_summary(name: str, report: dict[str, Any]) -> dict[str, Any]:
    current = report["windows"].get("current") or {}
    evidence = report["evidence_derived"]
    return {
        "repository": name,
        "project": REPOSITORIES[name],
        "sample_size": current.get("sample_size", 0),
        "merged_prs": current.get("merged_prs", 0),
        "throughput_factor": evidence.get("throughput_factor", UNKNOWN),
        "cycle_time_factor": evidence.get("cycle_time_factor", UNKNOWN),
        "engineering_multiplication_factor": evidence.get(
            "engineering_multiplication_factor", UNKNOWN
        ),
        "compounding_rate": evidence.get("compounding_rate", UNKNOWN),
        "repeat_failure_rate": current.get("repeat_failure_rate", UNKNOWN),
        "autonomous_completion_rate": current.get(
            "autonomous_completion_rate", UNKNOWN
        ),
        "dependency_unlock_rate": current.get("dependency_unlock_rate", UNKNOWN),
        "human_intervention_rate": current.get("human_intervention_rate", UNKNOWN),
    }


def aggregate(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected = set(REPOSITORIES)
    missing = sorted(expected - set(reports))
    unexpected = sorted(set(reports) - expected)
    if unexpected:
        raise SystemExit(f"unexpected repositories: {', '.join(unexpected)}")

    summaries = {
        name: repository_summary(name, report)
        for name, report in sorted(reports.items())
    }
    project_groups = {
        "knowledge-engine": [
            name for name, project in REPOSITORIES.items() if project == "knowledge-engine"
        ],
        "rocksmith": ["rocksmith-cdlc-generator"],
        "everward": ["Project-Everward"],
    }

    projects: dict[str, Any] = {}
    for project, members in project_groups.items():
        available = [summaries[name] for name in members if name in summaries]
        complete = len(available) == len(members)
        emfs = [
            value
            for row in available
            if (value := numeric(row["engineering_multiplication_factor"])) is not None
        ]
        projects[project] = {
            "required_repositories": members,
            "evidence_complete": complete,
            "engineering_multiplication_factor": (
                geometric_mean(emfs) if complete and len(emfs) == len(members) else UNKNOWN
            ),
            "repositories": available,
        }

    all_rows = list(summaries.values())
    all_emfs = [
        value
        for row in all_rows
        if (value := numeric(row["engineering_multiplication_factor"])) is not None
    ]
    portfolio_emf = (
        geometric_mean(all_emfs)
        if not missing and len(all_emfs) == len(expected)
        else UNKNOWN
    )

    rates: dict[str, Any] = {}
    for metric in (
        "repeat_failure_rate",
        "autonomous_completion_rate",
        "dependency_unlock_rate",
        "human_intervention_rate",
    ):
        weighted = []
        for row in all_rows:
            value = numeric(row[metric])
            weight = row.get("sample_size")
            if value is not None and isinstance(weight, int) and not isinstance(weight, bool):
                weighted.append((value, weight))
        rates[metric] = weighted_rate(weighted) if not missing else UNKNOWN

    claim = "UNKNOWN"
    reasons = []
    if missing:
        reasons.append("missing repository evidence: " + ", ".join(missing))
    elif portfolio_emf == UNKNOWN:
        reasons.append("one or more repositories lack numeric EMF evidence")
    else:
        reasons.append(
            "portfolio EMF is descriptive only; sustained comparable history is required"
        )

    return {
        "schema_version": 1,
        "evidence_complete": not missing,
        "missing_repositories": missing,
        "repositories": summaries,
        "projects": projects,
        "portfolio": {
            "engineering_multiplication_factor": portfolio_emf,
            **rates,
            "exponential_development_claim": claim,
            "claim_reasons": reasons,
        },
        "guardrails": {
            "missing_evidence_never_imputed": True,
            "knowledge_engine_requires_all_three_components": True,
            "no_guessed_completion_percentages": True,
            "portfolio_emf_is_geometric_mean_of_repository_emfs": True,
            "rate_metrics_are_sample_weighted": True,
            "claim_requires_longitudinal_history": True,
        },
    }


def self_test() -> list[str]:
    errors: list[str] = []
    base = {
        "schema_version": 2,
        "windows": {
            "current": {
                "sample_size": 10,
                "merged_prs": 10,
                "repeat_failure_rate": 0.1,
                "autonomous_completion_rate": 0.8,
                "dependency_unlock_rate": 0.2,
                "human_intervention_rate": 0.2,
            }
        },
        "evidence_derived": {
            "throughput_factor": 1.2,
            "cycle_time_factor": 1.1,
            "engineering_multiplication_factor": 1.32,
            "compounding_rate": 0.1,
        },
    }
    full = {name: dict(base) for name in REPOSITORIES}
    result = aggregate(full)
    if not result["evidence_complete"]:
        errors.append("complete five-repository evidence must be complete")
    if result["portfolio"]["engineering_multiplication_factor"] != 1.32:
        errors.append("equal repository EMFs should preserve the same portfolio EMF")
    if result["portfolio"]["exponential_development_claim"] != UNKNOWN:
        errors.append("single aggregate snapshot must not prove exponential development")

    partial = dict(full)
    partial.pop("knowledge-engine-ai")
    partial_result = aggregate(partial)
    if partial_result["portfolio"]["engineering_multiplication_factor"] != UNKNOWN:
        errors.append("missing repository evidence must force portfolio EMF UNKNOWN")
    if partial_result["projects"]["knowledge-engine"]["evidence_complete"]:
        errors.append("Knowledge Engine must require all three component reports")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate verified repository compounding reports into portfolio evidence."
    )
    parser.add_argument("--input-dir")
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        errors = self_test()
        print(json.dumps({"status": "FAILED" if errors else "GREEN", "errors": errors}, indent=2))
        return 1 if errors else 0

    if not args.input_dir:
        raise SystemExit("--input-dir is required unless --self-test is used")
    root = Path(args.input_dir)
    reports: dict[str, dict[str, Any]] = {}
    for name in REPOSITORIES:
        path = root / name / "engineering-compounding-report.json"
        if path.exists():
            reports[name] = load_report(path)
    result = aggregate(reports)
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
