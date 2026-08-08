"""Statistical Verification Readiness Gate for a curated golden evidence map.

Validates a hand-curated readiness classification
(`statistical_readiness_map.json`) against the actual reviewed golden
evidence map, Evidence Records, and typed statistical inputs, then renders
a deterministic Markdown report. See
`docs/glp1_statistical_readiness_gate_plan.md` and
`docs/reviews/glp1_statistical_readiness_gate/` for the approved
pre-implementation design this module implements.

This module never pools studies, performs meta-analysis, harmonizes
effects, infers a missing classification, parses numbers from prose, or
determines scientific truth. It only validates that a curated
classification is internally consistent with already-reviewed structured
facts, and reports the result.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_engine.binary_statistical_verification import BinaryStatisticalVerification
from knowledge_engine.statistical_verification import StatisticalVerification

READINESS_SCHEMA_VERSION = 1

ALLOWED_READINESS_CATEGORIES = {
    "exactly_verified",
    "bounded_approximation",
    "derived_not_source_equivalent",
    "display_only",
    "insufficient_numerical_detail",
    "not_selected_for_verification",
    "not_applicable",
}
"""Every possible primary readiness category a golden-map Evidence Record
can carry. A record's primary category does not preclude it from also
carrying additional verification facets (see `RecordFacets`) -- STEP 5 is
`exactly_verified` for its continuous arithmetic while also carrying a
bounded interval approximation and a derived, non-source-equivalent binary
risk ratio."""

READY_VERDICT = "ready_for_pooling_design_review"
NOT_READY_VERDICT = "not_ready_for_pooling_design"
_MINIMUM_BINARY_INPUTS_FOR_POOLING = 2


class StatisticalReadinessError(RuntimeError):
    """A readiness-map file could not be loaded."""


@dataclass(frozen=True)
class ReadinessRecord:
    """One curated readiness classification for one golden-map Evidence Record."""

    evidence_record_id: str
    readiness_category: str
    continuous_input_ids: tuple[str, ...]
    binary_input_ids: tuple[str, ...]
    compatibility_group: str | None
    incompatibility_reasons: tuple[str, ...]
    review_note: str
    line_number: int


@dataclass(frozen=True)
class CompatibilityGroupResult:
    """One named pooling-compatibility group and its deterministic status."""

    label: str
    evidence_record_ids: tuple[str, ...]
    status: str
    """One of "candidate", "no", or "undetermined"."""
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class StatisticalReadinessResult:
    """Complete deterministic readiness-gate validation result."""

    research_question: str | None = None
    golden_evidence_map_id: str | None = None
    category_counts: dict[str, int] = None  # type: ignore[assignment]
    continuous_input_count: int = 0
    binary_input_count: int = 0
    compatibility_groups: tuple[CompatibilityGroupResult, ...] = ()
    readiness_verdict: str | None = None
    blockers: tuple[str, ...] = ()
    records: tuple[ReadinessRecord, ...] = ()
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.category_counts is None:
            object.__setattr__(self, "category_counts", {})

    @property
    def valid(self) -> bool:
        return not self.errors


def load_statistical_readiness_map(path: Path) -> dict[str, Any]:
    """Load one readiness-map JSON object without interpreting its science."""

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StatisticalReadinessError(
            f"Could not read statistical readiness map: {path.name}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise StatisticalReadinessError(
            f"Statistical readiness map is not valid JSON: {path.name}"
        ) from exc
    if not isinstance(payload, dict):
        raise StatisticalReadinessError("Statistical readiness map root must be a JSON object.")
    return payload


def validate_statistical_readiness(
    payload: Mapping[str, Any],
    *,
    golden_map_evidence_record_ids: set[str],
    evidence_records_by_id: Mapping[str, Mapping[str, Any]],
    continuous_input_ids: set[str],
    binary_input_ids: set[str],
) -> StatisticalReadinessResult:
    """Validate a curated readiness map against already-reviewed structured facts.

    Every golden-map Evidence Record must receive exactly one classification
    row; every referenced statistical input id must exist in the already-
    validated continuous/binary input sets and be assigned to at most one
    record. This function never infers a missing classification -- an
    uncovered golden-map record is a validation error, not a silent gap.
    """

    errors: list[str] = []
    warnings: list[str] = []

    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != READINESS_SCHEMA_VERSION:
        errors.append("schema_version must be integer 1.")

    research_question = _optional_text(payload, "research_question")
    golden_evidence_map_id = _optional_text(payload, "golden_evidence_map")

    declared_continuous_ids = _string_list(payload, "continuous_inputs", errors)
    declared_binary_ids = _string_list(payload, "binary_inputs", errors)
    for input_id in declared_continuous_ids:
        if input_id not in continuous_input_ids:
            errors.append(
                f"continuous_inputs references unknown or unvalidated input id {input_id!r}."
            )
    for input_id in declared_binary_ids:
        if input_id not in binary_input_ids:
            errors.append(f"binary_inputs references unknown or unvalidated input id {input_id!r}.")

    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        errors.append("records must be a nonempty list.")
        raw_records = []

    records: list[ReadinessRecord] = []
    seen_evidence_ids: set[str] = set()
    assigned_continuous_ids: dict[str, str] = {}
    assigned_binary_ids: dict[str, str] = {}

    for line_number, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            errors.append(f"records[{line_number}]: must be a JSON object.")
            continue

        evidence_record_id = _required_text(raw_record, "evidence_record_id", line_number, errors)
        readiness_category = _required_text(raw_record, "readiness_category", line_number, errors)
        review_note = _required_text(raw_record, "review_note", line_number, errors)
        continuous_ids = _string_list(
            raw_record, "continuous_input_ids", errors, context=line_number
        )
        binary_ids = _string_list(raw_record, "binary_input_ids", errors, context=line_number)
        incompatibility_reasons = _string_list(
            raw_record, "incompatibility_reasons", errors, context=line_number
        )
        compatibility_group = raw_record.get("compatibility_group")
        if compatibility_group is not None and not isinstance(compatibility_group, str):
            errors.append(f"records[{line_number}]: compatibility_group must be a string or null.")
            compatibility_group = None
        elif compatibility_group == "":
            errors.append(f"records[{line_number}]: compatibility_group must not be blank.")
            compatibility_group = None

        if evidence_record_id is None:
            continue
        if evidence_record_id in seen_evidence_ids:
            errors.append(
                f"records[{line_number}]: duplicate evidence_record_id {evidence_record_id!r}."
            )
            continue
        seen_evidence_ids.add(evidence_record_id)

        if evidence_record_id not in golden_map_evidence_record_ids:
            errors.append(
                f"records[{line_number}]: evidence_record_id {evidence_record_id!r} "
                "is not selected by the reviewed golden evidence map."
            )
        evidence_record = evidence_records_by_id.get(evidence_record_id)
        if evidence_record is None:
            errors.append(
                f"records[{line_number}]: evidence_record_id {evidence_record_id!r} "
                "was not found among validated Evidence Records."
            )
        elif evidence_record.get("review_status") != "reviewed":
            errors.append(
                f"records[{line_number}]: evidence_record_id {evidence_record_id!r} "
                "is not a reviewed Evidence Record."
            )

        if (
            readiness_category is not None
            and readiness_category not in ALLOWED_READINESS_CATEGORIES
        ):
            errors.append(
                f"records[{line_number}]: readiness_category "
                f"{readiness_category!r} is not a supported category."
            )

        for input_id in continuous_ids:
            if input_id not in continuous_input_ids:
                errors.append(
                    f"records[{line_number}]: continuous_input_ids references unknown "
                    f"input id {input_id!r}."
                )
            elif input_id in assigned_continuous_ids:
                errors.append(
                    f"records[{line_number}]: continuous input id {input_id!r} is already "
                    f"assigned to {assigned_continuous_ids[input_id]!r}."
                )
            else:
                assigned_continuous_ids[input_id] = evidence_record_id
        for input_id in binary_ids:
            if input_id not in binary_input_ids:
                errors.append(
                    f"records[{line_number}]: binary_input_ids references unknown "
                    f"input id {input_id!r}."
                )
            elif input_id in assigned_binary_ids:
                errors.append(
                    f"records[{line_number}]: binary input id {input_id!r} is already "
                    f"assigned to {assigned_binary_ids[input_id]!r}."
                )
            else:
                assigned_binary_ids[input_id] = evidence_record_id

        if not errors or evidence_record_id:
            records.append(
                ReadinessRecord(
                    evidence_record_id=evidence_record_id,
                    readiness_category=readiness_category or "",
                    continuous_input_ids=tuple(continuous_ids),
                    binary_input_ids=tuple(binary_ids),
                    compatibility_group=compatibility_group,
                    incompatibility_reasons=tuple(incompatibility_reasons),
                    review_note=review_note or "",
                    line_number=line_number,
                )
            )

    missing_coverage = golden_map_evidence_record_ids - seen_evidence_ids
    for missing_id in sorted(missing_coverage):
        errors.append(
            f"Reviewed golden-map Evidence Record {missing_id!r} has no readiness classification."
        )

    if errors:
        return StatisticalReadinessResult(
            research_question=research_question,
            golden_evidence_map_id=golden_evidence_map_id,
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    category_counts = dict(Counter(record.readiness_category for record in records))
    compatibility_groups = _compute_compatibility_groups(records)
    readiness_verdict = _compute_readiness_verdict(compatibility_groups)
    blockers = _compute_blockers(
        compatibility_groups,
        readiness_verdict=readiness_verdict,
        binary_input_count=len(declared_binary_ids),
    )

    return StatisticalReadinessResult(
        research_question=research_question,
        golden_evidence_map_id=golden_evidence_map_id,
        category_counts=category_counts,
        continuous_input_count=len(declared_continuous_ids),
        binary_input_count=len(declared_binary_ids),
        compatibility_groups=compatibility_groups,
        readiness_verdict=readiness_verdict,
        blockers=blockers,
        records=tuple(records),
        errors=(),
        warnings=tuple(warnings),
    )


def _compute_compatibility_groups(
    records: Sequence[ReadinessRecord],
) -> tuple[CompatibilityGroupResult, ...]:
    """Group records by their declared `compatibility_group` and compute status.

    A group reaches "candidate" only when it has at least two members and
    every member declares zero `incompatibility_reasons` -- an explicit
    reason on any member is exactly why that member does not cleanly pool,
    so its presence alone is sufficient to keep the whole group at "no".
    A group with fewer than two members cannot be a pooling pair yet, so it
    is "undetermined" rather than "no" (there is no known incompatibility,
    only an as-yet-insufficient candidate count).
    """

    grouped: dict[str, list[ReadinessRecord]] = {}
    for record in records:
        if record.compatibility_group is not None:
            grouped.setdefault(record.compatibility_group, []).append(record)

    results: list[CompatibilityGroupResult] = []
    for label in sorted(grouped):
        members = grouped[label]
        reasons: tuple[str, ...]
        if len(members) < 2:
            status = "undetermined"
            reasons = ("Fewer than two candidate studies are assigned to this group.",)
        elif all(not member.incompatibility_reasons for member in members):
            status = "candidate"
            reasons = ()
        else:
            status = "no"
            reasons = tuple(
                sorted({reason for member in members for reason in member.incompatibility_reasons})
            )
        results.append(
            CompatibilityGroupResult(
                label=label,
                evidence_record_ids=tuple(member.evidence_record_id for member in members),
                status=status,
                reasons=reasons,
            )
        )
    return tuple(results)


def _compute_readiness_verdict(compatibility_groups: Sequence[CompatibilityGroupResult]) -> str:
    if any(group.status == "candidate" for group in compatibility_groups):
        return READY_VERDICT
    return NOT_READY_VERDICT


def _compute_blockers(
    compatibility_groups: Sequence[CompatibilityGroupResult],
    *,
    readiness_verdict: str,
    binary_input_count: int,
) -> tuple[str, ...]:
    if readiness_verdict == READY_VERDICT:
        return ()

    blockers: list[str] = [
        "No pair of independently source-audited primary-study inputs currently "
        "satisfies the complete compatibility gate."
    ]
    for group in compatibility_groups:
        if group.status == "no":
            reason_text = "; ".join(group.reasons)
            blockers.append(f"Compatibility group {group.label!r}: {reason_text}.")
        elif group.status == "undetermined":
            blockers.append(
                f"Compatibility group {group.label!r} has too few candidate studies "
                "to evaluate pooling compatibility."
            )
    if binary_input_count < _MINIMUM_BINARY_INPUTS_FOR_POOLING:
        blockers.append(
            f"Only {binary_input_count} production binary statistical input(s) exist; "
            "binary pooling design requires at least two independently source-audited "
            "primary studies."
        )
    return tuple(blockers)


def render_statistical_readiness_report(
    result: StatisticalReadinessResult,
    *,
    continuous_verifications: Sequence[StatisticalVerification] = (),
    binary_verifications: Sequence[BinaryStatisticalVerification] = (),
) -> str:
    """Render the readiness gate's deterministic Markdown report.

    Displays stored classifications, actual coverage counts, compatibility
    decisions, and the readiness verdict. It never pools studies, performs
    meta-analysis, or determines scientific truth.
    """

    continuous_by_evidence_id: dict[str, list[StatisticalVerification]] = {}
    for continuous_verification in continuous_verifications:
        continuous_by_evidence_id.setdefault(
            continuous_verification.record.evidence_record_id, []
        ).append(continuous_verification)
    binary_by_evidence_id: dict[str, list[BinaryStatisticalVerification]] = {}
    for binary_verification in binary_verifications:
        binary_by_evidence_id.setdefault(binary_verification.record.evidence_record_id, []).append(
            binary_verification
        )

    lines: list[str] = []
    lines.append("# Statistical Verification Readiness Gate")
    lines.append("")
    lines.append("## Scope")
    lines.append("")
    lines.append(f"Research question: {_md_text(result.research_question or 'not recorded')}")
    lines.append(
        f"Golden evidence map: {_md_code(result.golden_evidence_map_id or 'not recorded')}"
    )
    lines.append(
        "This report validates a curated readiness classification against the reviewed "
        "golden evidence map and already-verified typed statistical inputs. It does not "
        "pool studies, perform meta-analysis, or determine scientific truth."
    )
    lines.append("")

    lines.append("## Coverage Summary")
    lines.append("")
    lines.append(f"Golden-map records classified: {len(result.records)}")
    for category in sorted(ALLOWED_READINESS_CATEGORIES):
        lines.append(f"- {category}: {result.category_counts.get(category, 0)}")
    lines.append(f"Continuous statistical inputs: {result.continuous_input_count}")
    lines.append(f"Binary statistical inputs: {result.binary_input_count}")
    lines.append("")

    lines.append("## Verification Inventory")
    lines.append("")
    for record in sorted(result.records, key=lambda r: r.evidence_record_id):
        lines.append(f"### `{_md_code(record.evidence_record_id)}`")
        lines.append("")
        lines.append(f"Primary readiness category: `{record.readiness_category}`")
        facets: list[str] = []
        for continuous_verification in continuous_by_evidence_id.get(record.evidence_record_id, ()):
            facets.append(
                f"Exact continuous arithmetic reproduction "
                f"(`{_md_code(continuous_verification.record.statistical_input_id)}`): "
                f"{continuous_verification.status}."
            )
            if continuous_verification.interval_approximation is not None:
                facets.append(
                    "Bounded confidence-interval approximation: "
                    f"{continuous_verification.interval_approximation.status} "
                    "(explicitly not a reconstruction of the source model)."
                )
        for binary_verification in binary_by_evidence_id.get(record.evidence_record_id, ()):
            facets.append(
                f"Derived crude binary risk ratio "
                f"(`{_md_code(binary_verification.record.binary_input_id)}`): "
                f"{binary_verification.status} "
                "(explicitly not equivalent to any source-adjusted estimate)."
            )
        if facets:
            for facet in facets:
                lines.append(f"- {facet}")
        if record.compatibility_group:
            lines.append(f"Compatibility group: `{_md_code(record.compatibility_group)}`")
        if record.incompatibility_reasons:
            lines.append("Incompatibility reasons:")
            for reason in record.incompatibility_reasons:
                lines.append(f"- {_md_text(reason)}")
        lines.append(f"Review note: {_md_text(record.review_note)}")
        lines.append("")

    lines.append("## Compatibility Groups")
    lines.append("")
    if result.compatibility_groups:
        for group in result.compatibility_groups:
            members = ", ".join(f"`{_md_code(member)}`" for member in group.evidence_record_ids)
            lines.append(f"### `{_md_code(group.label)}`")
            lines.append("")
            lines.append(f"Members: {members}")
            lines.append(f"Status: `{group.status}`")
            if group.reasons:
                lines.append("Reasons:")
                for reason in group.reasons:
                    lines.append(f"- {_md_text(reason)}")
            lines.append("")
    else:
        lines.append("No compatibility groups are declared in the current readiness map.")
        lines.append("")

    lines.append("## Readiness Decision")
    lines.append("")
    lines.append(f"Verdict: `{result.readiness_verdict}`")
    lines.append("")

    lines.append("## Blockers")
    lines.append("")
    if result.blockers:
        for blocker in result.blockers:
            lines.append(f"- {_md_text(blocker)}")
    else:
        lines.append("None recorded.")
    lines.append("")

    lines.append("## Boundaries")
    lines.append("")
    lines.append("- No studies were pooled.")
    lines.append("- No meta-analysis was performed.")
    lines.append("- No scientific synthesis was performed.")
    lines.append("- No treatment conclusion was generated.")
    lines.append("- Verification does not establish scientific truth or clinical guidance.")
    lines.append("- Missing numerical detail was not inferred.")
    lines.append("")

    return "\n".join(lines) + "\n"


def _md_text(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").replace("\\", "\\\\")
    for character in ("*", "_", "[", "]", "<", ">", "#"):
        text = text.replace(character, f"\\{character}")
    return text


def _md_code(value: object) -> str:
    return str(value).replace("`", "\\`").replace("\n", " ").replace("\r", " ")


def _optional_text(payload: Mapping[str, Any], field: str) -> str | None:
    value = payload.get(field)
    return value if isinstance(value, str) and value else None


def _required_text(
    payload: Mapping[str, Any], field: str, line_number: int, errors: list[str]
) -> str | None:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        errors.append(f"records[{line_number}]: {field} must be a nonblank string.")
        return None
    return value


def _string_list(
    payload: Mapping[str, Any],
    field: str,
    errors: list[str],
    *,
    context: int | None = None,
) -> list[str]:
    value = payload.get(field, [])
    prefix = f"records[{context}]: " if context is not None else ""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{prefix}{field} must be a list of strings.")
        return []
    if len(set(value)) != len(value):
        errors.append(f"{prefix}{field} contains a duplicate.")
    return value
