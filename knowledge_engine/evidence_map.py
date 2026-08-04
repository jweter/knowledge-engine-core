"""Validation for a curated, reference-only scientific evidence map.

An evidence map selects and groups existing Evidence Records and reviewed
Relationship Records. It does not create claims, infer relationships, score
consensus, or decide whether a scientific statement is true.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowledge_engine.utils import normalize_doi

EVIDENCE_MAP_SCHEMA_VERSION = 1
ALLOWED_MAP_STATUSES = {"provisional", "reviewed"}
ALLOWED_REVIEW_STATUSES = {"secondary_review_required", "reviewed"}
ALLOWED_EVIDENCE_ROLES = {
    "landmark_trial",
    "evidence_synthesis",
    "population_extension",
    "active_comparator_context",
    "durability_qualifier",
    "endpoint_qualifier",
    "agent_population_qualifier",
    "safety_qualifier",
}
ALLOWED_CONTRADICTION_STATUSES = {
    "identified",
    "none_identified_in_bounded_map",
    "not_evaluated",
}


class EvidenceMapError(RuntimeError):
    """An evidence-map file could not be loaded."""


@dataclass(frozen=True)
class EvidenceMapValidationResult:
    """Deterministic structural and reference validation result."""

    map_id: str | None
    map_status: str | None
    evidence_node_count: int
    relationship_count: int
    citation_count: int
    role_counts: dict[str, int]
    relationship_type_counts: dict[str, int]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


def load_evidence_map(path: Path) -> dict[str, Any]:
    """Load one evidence-map JSON object without interpreting its science."""

    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceMapError(f"Could not read evidence map: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceMapError(f"Evidence map is not valid JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise EvidenceMapError("Evidence map root must be a JSON object.")
    return payload


def validate_evidence_map(
    payload: Mapping[str, Any],
    *,
    evidence_records: Sequence[Mapping[str, Any]],
    relationship_records: Sequence[Mapping[str, Any]],
    citation_dois: set[str],
) -> EvidenceMapValidationResult:
    """Validate map structure and references to already-validated records.

    This function deliberately does not determine whether an inclusion,
    relationship, or contradiction assessment is scientifically correct. Those
    are reviewable statements authored in the versioned map and source records.
    """

    errors: list[str] = []
    warnings: list[str] = []
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or schema_version != EVIDENCE_MAP_SCHEMA_VERSION:
        errors.append("schema_version must be integer 1.")

    map_id = _required_text(payload, "map_id", "map", errors)
    _required_text(payload, "title", "map", errors)
    _required_text(payload, "research_question", "map", errors)
    map_status = _required_text(payload, "map_status", "map", errors)
    if map_status and map_status not in ALLOWED_MAP_STATUSES:
        errors.append(f"map_status must be one of: {', '.join(sorted(ALLOWED_MAP_STATUSES))}.")

    scope = payload.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object.")
    else:
        for field in ("population", "intervention", "outcome", "exclusions"):
            _required_text(scope, field, "scope", errors)

    evidence_by_id = {
        str(record.get("evidence_record_id")): record
        for record in evidence_records
        if isinstance(record.get("evidence_record_id"), str)
    }
    relationships_by_id = {
        str(record.get("relationship_id")): record
        for record in relationship_records
        if isinstance(record.get("relationship_id"), str)
    }

    raw_nodes = payload.get("evidence_nodes")
    nodes = raw_nodes if isinstance(raw_nodes, list) else []
    if not nodes:
        errors.append("evidence_nodes must be a non-empty list.")
    selected_ids: list[str] = []
    role_counts: Counter[str] = Counter()
    citation_count = 0
    for index, raw_node in enumerate(nodes, start=1):
        context = f"evidence_nodes[{index}]"
        if not isinstance(raw_node, dict):
            errors.append(f"{context} must be an object.")
            continue
        evidence_id = _required_text(raw_node, "evidence_record_id", context, errors)
        role = _required_text(raw_node, "role", context, errors)
        _required_text(raw_node, "inclusion_rationale", context, errors)
        if not evidence_id:
            continue
        if evidence_id in selected_ids:
            errors.append(f"{context} repeats evidence_record_id {evidence_id!r}.")
            continue
        selected_ids.append(evidence_id)
        if role:
            role_counts[role] += 1
            if role not in ALLOWED_EVIDENCE_ROLES:
                errors.append(
                    f"{context}.role must be one of: {', '.join(sorted(ALLOWED_EVIDENCE_ROLES))}."
                )
        record = evidence_by_id.get(evidence_id)
        if record is None:
            errors.append(f"{context} references unknown Evidence Record {evidence_id!r}.")
            continue
        limitations = record.get("limitations")
        if not isinstance(limitations, list) or not any(
            isinstance(value, str) and value.strip() for value in limitations
        ):
            errors.append(f"{context} references a record without stated limitations.")
        doi = record.get("source_doi")
        normalized_doi = normalize_doi(doi) if isinstance(doi, str) else ""
        if not normalized_doi:
            errors.append(f"{context} references a record without a source DOI.")
        elif normalized_doi not in citation_dois:
            errors.append(f"{context} has no complete citation row for DOI {normalized_doi!r}.")
        else:
            citation_count += 1

    selected_set = set(selected_ids)
    raw_relationship_ids = payload.get("relationship_ids")
    relationship_ids = raw_relationship_ids if isinstance(raw_relationship_ids, list) else []
    if not relationship_ids:
        errors.append("relationship_ids must be a non-empty list.")
    seen_relationship_ids: set[str] = set()
    relationship_type_counts: Counter[str] = Counter()
    selected_relationships: list[Mapping[str, Any]] = []
    for index, relationship_id in enumerate(relationship_ids, start=1):
        context = f"relationship_ids[{index}]"
        if not isinstance(relationship_id, str) or not relationship_id.strip():
            errors.append(f"{context} must be non-empty text.")
            continue
        relationship_id = relationship_id.strip()
        if relationship_id in seen_relationship_ids:
            errors.append(f"{context} repeats relationship_id {relationship_id!r}.")
            continue
        seen_relationship_ids.add(relationship_id)
        relationship = relationships_by_id.get(relationship_id)
        if relationship is None:
            errors.append(f"{context} references unknown Relationship Record {relationship_id!r}.")
            continue
        selected_relationships.append(relationship)
        relationship_type = relationship.get("relationship_type")
        if isinstance(relationship_type, str):
            relationship_type_counts[relationship_type] += 1
        for endpoint in ("source_evidence_record_id", "target_evidence_record_id"):
            evidence_id = relationship.get(endpoint)
            if evidence_id not in selected_set:
                errors.append(
                    f"{context} endpoint {evidence_id!r} is not selected in evidence_nodes."
                )

    population_refs = _validate_groups(
        payload.get("population_groups"), "population_groups", selected_set, errors
    )
    comparator_refs = _validate_groups(
        payload.get("comparator_groups"), "comparator_groups", selected_set, errors
    )
    for group_name, references in (
        ("population_groups", population_refs),
        ("comparator_groups", comparator_refs),
    ):
        missing = sorted(selected_set - references)
        if missing:
            errors.append(f"{group_name} do not classify: {', '.join(missing)}.")

    contradiction = payload.get("contradiction_assessment")
    contradiction_status: str | None = None
    if not isinstance(contradiction, dict):
        errors.append("contradiction_assessment must be an object.")
    else:
        contradiction_status = _required_text(
            contradiction, "status", "contradiction_assessment", errors
        )
        _required_text(contradiction, "statement", "contradiction_assessment", errors)
        contradiction_refs = _text_list(
            contradiction.get("evidence_record_ids"),
            "contradiction_assessment.evidence_record_ids",
            errors,
            allow_empty=True,
        )
        for evidence_id in contradiction_refs:
            if evidence_id not in selected_set:
                errors.append(
                    "contradiction_assessment references unselected Evidence Record "
                    f"{evidence_id!r}."
                )
        if contradiction_status not in ALLOWED_CONTRADICTION_STATUSES:
            errors.append(
                "contradiction_assessment.status must be one of: "
                f"{', '.join(sorted(ALLOWED_CONTRADICTION_STATUSES))}."
            )
        if contradiction_status == "identified" and not contradiction_refs:
            errors.append(
                "An identified contradiction must reference at least one Evidence Record."
            )
        if contradiction_status == "none_identified_in_bounded_map" and contradiction_refs:
            errors.append("A no-contradiction assessment cannot reference contradictory records.")

    has_contradicts_edge = any(
        relationship.get("relationship_type") == "contradicts"
        for relationship in selected_relationships
    )
    if contradiction_status == "identified" and not has_contradicts_edge:
        errors.append("An identified contradiction requires a selected contradicts relationship.")
    if contradiction_status == "none_identified_in_bounded_map" and has_contradicts_edge:
        errors.append("The map selects a contradicts relationship but declares none identified.")

    _text_list(payload.get("limitations"), "limitations", errors)
    _text_list(payload.get("known_gaps"), "known_gaps", errors)
    review = payload.get("review")
    review_status: str | None = None
    if not isinstance(review, dict):
        errors.append("review must be an object.")
    else:
        _required_text(review, "method", "review", errors)
        review_status = _required_text(review, "status", "review", errors)
        _required_text(review, "notes", "review", errors)
        if review_status and review_status not in ALLOWED_REVIEW_STATUSES:
            errors.append(
                f"review.status must be one of: {', '.join(sorted(ALLOWED_REVIEW_STATUSES))}."
            )
        if review_status == "reviewed":
            _required_text(review, "reviewed_by", "review", errors)
            _required_text(review, "reviewer_type", "review", errors)
            _required_text(review, "review_date", "review", errors)

    if map_status == "reviewed" and review_status != "reviewed":
        errors.append("A reviewed map must have review.status set to 'reviewed'.")
    if map_status == "provisional" and review_status == "reviewed":
        errors.append("A provisional map cannot have review.status set to 'reviewed'.")

    draft_ids = sorted(
        evidence_id
        for evidence_id in selected_set
        if evidence_by_id.get(evidence_id, {}).get("review_status") != "reviewed"
    )
    if map_status == "reviewed" and draft_ids:
        errors.append(
            "A reviewed map cannot reference Evidence Records still awaiting review: "
            + ", ".join(draft_ids)
            + "."
        )
    elif draft_ids:
        warnings.append(
            f"{len(draft_ids)} selected Evidence Records remain draft; "
            "secondary review is required."
        )

    return EvidenceMapValidationResult(
        map_id=map_id,
        map_status=map_status,
        evidence_node_count=len(selected_set),
        relationship_count=len(selected_relationships),
        citation_count=citation_count,
        role_counts=dict(sorted(role_counts.items())),
        relationship_type_counts=dict(sorted(relationship_type_counts.items())),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _required_text(
    payload: Mapping[str, Any], field: str, context: str, errors: list[str]
) -> str | None:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{context}.{field} must be non-empty text.")
        return None
    return value.strip()


def _text_list(
    value: Any,
    context: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        qualifier = "a list" if allow_empty else "a non-empty list"
        errors.append(f"{context} must be {qualifier} of non-empty text values.")
        return []
    if not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{context} must contain only non-empty text values.")
        return []
    return [item.strip() for item in value]


def _validate_groups(
    value: Any,
    context: str,
    selected_ids: set[str],
    errors: list[str],
) -> set[str]:
    if not isinstance(value, list) or not value:
        errors.append(f"{context} must be a non-empty list.")
        return set()
    references: set[str] = set()
    seen_labels: set[str] = set()
    for index, raw_group in enumerate(value, start=1):
        group_context = f"{context}[{index}]"
        if not isinstance(raw_group, dict):
            errors.append(f"{group_context} must be an object.")
            continue
        label = _required_text(raw_group, "label", group_context, errors)
        _required_text(raw_group, "interpretation_boundary", group_context, errors)
        if label in seen_labels:
            errors.append(f"{group_context} repeats label {label!r}.")
        elif label:
            seen_labels.add(label)
        evidence_ids = _text_list(
            raw_group.get("evidence_record_ids"),
            f"{group_context}.evidence_record_ids",
            errors,
        )
        if len(set(evidence_ids)) != len(evidence_ids):
            errors.append(f"{group_context}.evidence_record_ids contains duplicates.")
        for evidence_id in evidence_ids:
            if evidence_id not in selected_ids:
                errors.append(f"{group_context} references unselected record {evidence_id!r}.")
            references.add(evidence_id)
    return references
