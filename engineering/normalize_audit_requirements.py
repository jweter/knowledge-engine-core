"""Normalize Poetry-exported requirements for deterministic vulnerability auditing.

Poetry may emit overlapping markers for one locked package. If multiple markers are
true in the audit environment, pip-audit rejects the export before vulnerability
analysis. Evaluate markers, deduplicate equivalent active requirements, and fail
closed if one package has conflicting active requirements.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def normalize(lines: list[str]) -> list[str]:
    output: list[str] = []
    active_by_name: dict[str, str] = {}

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue

        base = line.split(";", 1)[0].strip()
        normalized = str(Requirement(base))
        name = canonicalize_name(requirement.name)
        previous = active_by_name.get(name)

        if previous is None:
            active_by_name[name] = normalized
            output.append(normalized)
        elif previous != normalized:
            raise ValueError(
                f"conflicting active requirements for {name}: "
                f"{previous!r} versus {normalized!r}"
            )

    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    normalized = normalize(args.input.read_text(encoding="utf-8").splitlines())
    args.output.write_text("\n".join(normalized) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
