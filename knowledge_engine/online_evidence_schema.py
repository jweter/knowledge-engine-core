"""Machine-checkable JSON Schema for the ``ke-online-evidence/v1`` bundle (KEC-1).

``knowledge_engine/online_evidence.py`` is the canonical contract: its
dataclasses, enums and ``OnlineEvidenceBundle.to_dict`` already enforce every
field, type and enum a bundle must have. Independent consumer implementations
(``knowledge-engine-ai``'s ``online_evidence_adapter.py``,
``knowledge-engine-web``'s ``online_evidence_orchestration.py``) parse the same
JSON by hand-copying those field names, which can silently drift out of sync
with Core. This module exports that contract as a JSON Schema document and a
minimal pure-stdlib checker, so a consumer can validate its own parser against
Core's canonical contract instead.

The "required" field lists below are derived from the dataclasses themselves
(``dataclasses.fields``), not hand-copied, so a field added, removed or
renamed on ``OnlineSource``, ``EvidenceExcerpt``, ``Citation``,
``EvidenceClaim`` or ``OnlineEvidenceBundle`` changes this module's output
without any further edit here. The committed
``docs/schemas/online_evidence_v1.schema.json`` must still be regenerated to
match -- see ``tests/test_online_evidence_schema.py``.

Changes within ``ke-online-evidence/v1`` are additive only
(``docs/core_interface_contract.md``): a field already declared here is never
removed, renamed or retyped, and a newly added field is always optional.
Removing or retyping a field requires a new schema version.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from knowledge_engine.online_evidence import (
    ONLINE_EVIDENCE_SCHEMA,
    Citation,
    ClaimStatus,
    EvidenceClaim,
    EvidenceExcerpt,
    EvidenceStance,
    OnlineEvidenceBundle,
    OnlineSource,
    RetrievalStatus,
)

SCHEMA_ID = "https://knowledge-engine.internal/schemas/online_evidence_v1.schema.json"

_STRING: dict[str, Any] = {"type": "string"}
_NULLABLE_STRING: dict[str, Any] = {"type": ["string", "null"]}
_NULLABLE_INTEGER: dict[str, Any] = {"type": ["integer", "null"]}


def _dataclass_field_names(cls: type) -> list[str]:
    return [field.name for field in dataclasses.fields(cls)]


def required_fields_for_bundle() -> list[str]:
    """The wire-format fields `OnlineEvidenceBundle.to_dict` always emits.

    ``schema`` is the module constant `ONLINE_EVIDENCE_SCHEMA`, not a dataclass
    field, so it is listed explicitly alongside the bundle's own fields.
    """

    return ["schema", *_dataclass_field_names(OnlineEvidenceBundle)]


def required_fields_for_source() -> list[str]:
    return _dataclass_field_names(OnlineSource)


def required_fields_for_excerpt() -> list[str]:
    return _dataclass_field_names(EvidenceExcerpt)


def required_fields_for_citation() -> list[str]:
    return _dataclass_field_names(Citation)


def required_fields_for_claim() -> list[str]:
    """The wire-format fields `OnlineEvidenceBundle.to_dict` always emits for a claim.

    ``status`` is computed (`EvidenceClaim.status`), never a stored field, but
    is always serialized, so it is listed explicitly alongside the claim's own
    fields.
    """

    return [*_dataclass_field_names(EvidenceClaim), "status"]


def _enum_schema(values: Iterable[StrEnum]) -> dict[str, Any]:
    return {"type": "string", "enum": [value.value for value in values]}


def build_schema() -> dict[str, Any]:
    """Build the ``ke-online-evidence/v1`` JSON Schema from Core's own types."""

    source_properties: dict[str, Any] = {
        "source_id": _STRING,
        "url": _STRING,
        "retrieved_at": _STRING,
        "status": _enum_schema(RetrievalStatus),
        "provider": _STRING,
        "title": _NULLABLE_STRING,
        "doi": _NULLABLE_STRING,
        "pmcid": _NULLABLE_STRING,
        "pmid": _NULLABLE_STRING,
        "arxiv_id": _NULLABLE_STRING,
        "content_sha256": _NULLABLE_STRING,
        "failure_reason": _NULLABLE_STRING,
        "license": _NULLABLE_STRING,
    }
    excerpt_properties: dict[str, Any] = {
        "excerpt_id": _STRING,
        "source_id": _STRING,
        "text": _STRING,
        "char_start": _NULLABLE_INTEGER,
        "char_end": _NULLABLE_INTEGER,
        "locator": _NULLABLE_STRING,
    }
    citation_properties: dict[str, Any] = {
        "excerpt_id": _STRING,
        "stance": _enum_schema(EvidenceStance),
    }
    claim_properties: dict[str, Any] = {
        "claim_id": _STRING,
        "text": _STRING,
        "status": _enum_schema(ClaimStatus),
        "citations": {"type": "array", "items": {"$ref": "#/$defs/Citation"}},
    }

    required_source = required_fields_for_source()
    required_excerpt = required_fields_for_excerpt()
    required_citation = required_fields_for_citation()
    required_claim = required_fields_for_claim()
    assert set(source_properties) == set(required_source), (
        "online_evidence_schema.py's OnlineSource properties must match its own dataclass fields"
    )
    assert set(excerpt_properties) == set(required_excerpt), (
        "online_evidence_schema.py's EvidenceExcerpt properties must match its own dataclass fields"
    )
    assert set(citation_properties) == set(required_citation), (
        "online_evidence_schema.py's Citation properties must match its own dataclass fields"
    )
    assert set(claim_properties) == set(required_claim), (
        "online_evidence_schema.py's EvidenceClaim properties must match its own dataclass fields"
    )

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Online evidence bundle (ke-online-evidence/v1)",
        "description": (
            "Machine-checkable contract for the ke-online-evidence/v1 bundle produced by "
            "`ke online-research` and checked by `ke online-evidence-validate` "
            "(docs/online_evidence_contract.md, docs/core_interface_contract.md section "
            "'Online Research Report evidence bundle'). Changes are additive only: a field "
            "declared here is never removed, renamed or retyped, and a newly added field is "
            "always optional -- readers must ignore unknown fields."
        ),
        "type": "object",
        "required": required_fields_for_bundle(),
        "properties": {
            "schema": {"const": ONLINE_EVIDENCE_SCHEMA},
            "question": _STRING,
            "sources": {"type": "array", "items": {"$ref": "#/$defs/OnlineSource"}},
            "excerpts": {"type": "array", "items": {"$ref": "#/$defs/EvidenceExcerpt"}},
            "claims": {"type": "array", "items": {"$ref": "#/$defs/EvidenceClaim"}},
        },
        "additionalProperties": True,
        "$defs": {
            "OnlineSource": {
                "type": "object",
                "required": required_source,
                "properties": source_properties,
                "additionalProperties": True,
            },
            "EvidenceExcerpt": {
                "type": "object",
                "required": required_excerpt,
                "properties": excerpt_properties,
                "additionalProperties": True,
            },
            "Citation": {
                "type": "object",
                "required": required_citation,
                "properties": citation_properties,
                "additionalProperties": True,
            },
            "EvidenceClaim": {
                "type": "object",
                "required": required_claim,
                "properties": claim_properties,
                "additionalProperties": True,
            },
        },
    }


def render_schema() -> str:
    """The schema as the exact JSON text `ke online-evidence-schema` prints or writes."""

    return json.dumps(build_schema(), indent=2, sort_keys=True) + "\n"


class SchemaCheckError(ValueError):
    """The schema document itself uses an unsupported JSON Schema feature."""


_TYPE_CHECKS: dict[str, Any] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": Mapping,
    "null": type(None),
}


def _matches_type(instance: Any, type_names: Sequence[str]) -> bool:
    for type_name in type_names:
        python_type = _TYPE_CHECKS.get(type_name)
        if python_type is None:
            raise SchemaCheckError(f"Unsupported JSON Schema type: {type_name!r}.")
        if type_name == "integer" and isinstance(instance, bool):
            continue  # bool is a subclass of int; never accepted where "integer" is declared.
        if type_name == "boolean" and not isinstance(instance, bool):
            continue
        if isinstance(instance, python_type):
            return True
    return False


def _resolve(node: Mapping[str, Any], root: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node.get("$ref")
    if ref is None:
        return node
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise SchemaCheckError(f"Unsupported $ref: {ref!r}.")
    resolved: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(resolved, Mapping) or part not in resolved:
            raise SchemaCheckError(f"$ref {ref!r} does not resolve against the schema.")
        resolved = resolved[part]
    if not isinstance(resolved, Mapping):
        raise SchemaCheckError(f"$ref {ref!r} does not resolve to an object.")
    return resolved


def validate(
    instance: Any,
    schema: Mapping[str, Any],
    *,
    root: Mapping[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    """Check `instance` against a minimal (object/array/type/enum/const/$ref) subset of `schema`.

    Returns the problems found; an empty list means it validates. Unknown/extra
    object properties never fail -- the contract is additive-only, so a reader
    (and this checker) must ignore fields it does not recognize. This is a
    deliberately small, dependency-free implementation of exactly the JSON
    Schema vocabulary `build_schema` emits; it is not a general-purpose
    validator.
    """

    root = schema if root is None else root
    node = _resolve(schema, root)
    problems: list[str] = []

    if "const" in node:
        if instance != node["const"]:
            problems.append(f"{path}: expected {node['const']!r}, got {instance!r}.")
        return problems

    type_spec = node.get("type")
    if type_spec is not None:
        type_names = [type_spec] if isinstance(type_spec, str) else list(type_spec)
        if not _matches_type(instance, type_names):
            problems.append(f"{path}: expected type {type_names}, got {type(instance).__name__}.")
            return problems

    if "enum" in node and instance not in node["enum"]:
        problems.append(f"{path}: {instance!r} is not one of {node['enum']}.")

    if "properties" in node or type_spec == "object":
        if not isinstance(instance, Mapping):
            problems.append(f"{path}: expected an object.")
            return problems
        for field in node.get("required", ()):
            if field not in instance:
                problems.append(f"{path}: missing required field {field!r}.")
        for name, subschema in node.get("properties", {}).items():
            if name in instance:
                problems.extend(
                    validate(instance[name], subschema, root=root, path=f"{path}.{name}")
                )

    if "items" in node or type_spec == "array":
        if not isinstance(instance, list):
            problems.append(f"{path}: expected an array.")
            return problems
        items_schema = node.get("items")
        if items_schema is not None:
            for index, item in enumerate(instance):
                problems.extend(validate(item, items_schema, root=root, path=f"{path}[{index}]"))

    return problems


__all__ = [
    "SCHEMA_ID",
    "SchemaCheckError",
    "build_schema",
    "render_schema",
    "required_fields_for_bundle",
    "required_fields_for_citation",
    "required_fields_for_claim",
    "required_fields_for_excerpt",
    "required_fields_for_source",
    "validate",
]
