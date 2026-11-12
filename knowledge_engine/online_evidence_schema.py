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

The "required" field lists are a **pinned v1 baseline**, not a live
reflection of whatever fields the dataclasses happen to carry today.
Deriving "required" from current ``dataclasses.fields`` would silently
break the additive-only rule the moment a new, optional, defaulted field
was added to one of these dataclasses: that new field would instantly
become *required* on the wire, even though old bundles never had it and
new ones may omit it. So a field only ever leaves the pinned required
tuples below when ``ke-online-evidence/v1`` itself is replaced by a new
major schema version -- never merely because a dataclass grew a field.

What *is* checked live against the dataclasses is coverage: `build_schema`
asserts every field `OnlineSource`/`EvidenceExcerpt`/`Citation`/
`EvidenceClaim`/`OnlineEvidenceBundle` currently carries has a declared
schema property (so a newly added field can never go undocumented), while
leaving it up to a human to decide whether that new property also belongs
in the properties dict as optional -- it must never be added to a
``required`` tuple. The committed
``docs/schemas/online_evidence_v1.schema.json`` must still be regenerated
to match a properties change -- see ``tests/test_online_evidence_schema.py``.

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


def _dataclass_field_names(cls: type) -> set[str]:
    return {field.name for field in dataclasses.fields(cls)}


# Pinned ke-online-evidence/v1 required field sets -- see the module docstring
# for why these are literal tuples rather than live `dataclasses.fields`
# introspection. Today they equal every field each dataclass carries (plus the
# "schema"/claim "status" extras that are constants/computed, not dataclass
# fields); that is a coincidence of v1's current shape, not a rule these
# tuples must track. A future additive field joins the relevant *properties*
# dict in `build_schema`, never one of these tuples.
_BUNDLE_REQUIRED: tuple[str, ...] = ("schema", "question", "sources", "excerpts", "claims")
_SOURCE_REQUIRED: tuple[str, ...] = (
    "source_id",
    "url",
    "retrieved_at",
    "status",
    "provider",
    "title",
    "doi",
    "pmcid",
    "pmid",
    "arxiv_id",
    "content_sha256",
    "failure_reason",
    "license",
)
_EXCERPT_REQUIRED: tuple[str, ...] = (
    "excerpt_id",
    "source_id",
    "text",
    "char_start",
    "char_end",
    "locator",
)
_CITATION_REQUIRED: tuple[str, ...] = ("excerpt_id", "stance")
_CLAIM_REQUIRED: tuple[str, ...] = ("claim_id", "text", "citations", "status")


def required_fields_for_bundle() -> list[str]:
    """The pinned ke-online-evidence/v1 required top-level bundle fields."""

    return list(_BUNDLE_REQUIRED)


def required_fields_for_source() -> list[str]:
    """The pinned ke-online-evidence/v1 required OnlineSource fields."""

    return list(_SOURCE_REQUIRED)


def required_fields_for_excerpt() -> list[str]:
    """The pinned ke-online-evidence/v1 required EvidenceExcerpt fields."""

    return list(_EXCERPT_REQUIRED)


def required_fields_for_citation() -> list[str]:
    """The pinned ke-online-evidence/v1 required Citation fields."""

    return list(_CITATION_REQUIRED)


def required_fields_for_claim() -> list[str]:
    """The pinned ke-online-evidence/v1 required EvidenceClaim fields."""

    return list(_CLAIM_REQUIRED)


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

    required_bundle = required_fields_for_bundle()
    required_source = required_fields_for_source()
    required_excerpt = required_fields_for_excerpt()
    required_citation = required_fields_for_citation()
    required_claim = required_fields_for_claim()

    # Coverage: every field the dataclasses currently carry must be a declared
    # property, so a newly added field is never silently undocumented. This is
    # deliberately a subset check, not equality with `required` -- a new field
    # belongs in `properties` as optional, and must never be forced into one of
    # the pinned `required` tuples above (see module docstring).
    assert _dataclass_field_names(OnlineSource) <= set(source_properties), (
        "online_evidence_schema.py's OnlineSource properties must cover its own dataclass fields"
    )
    assert _dataclass_field_names(EvidenceExcerpt) <= set(excerpt_properties), (
        "online_evidence_schema.py's EvidenceExcerpt properties must cover its own dataclass fields"
    )
    assert _dataclass_field_names(Citation) <= set(citation_properties), (
        "online_evidence_schema.py's Citation properties must cover its own dataclass fields"
    )
    assert ({"status"} | _dataclass_field_names(EvidenceClaim)) <= set(claim_properties), (
        "online_evidence_schema.py's EvidenceClaim properties must cover its own dataclass fields"
    )
    bundle_property_names = {"schema", "question", "sources", "excerpts", "claims"}
    assert ({"schema"} | _dataclass_field_names(OnlineEvidenceBundle)) <= bundle_property_names, (
        "online_evidence_schema.py's top-level properties must cover OnlineEvidenceBundle's own "
        "dataclass fields"
    )

    # Sanity: the pinned required fields must themselves be real, declared
    # properties -- a typo in a `_*_REQUIRED` tuple is still caught here.
    assert set(required_source) <= set(source_properties)
    assert set(required_excerpt) <= set(excerpt_properties)
    assert set(required_citation) <= set(citation_properties)
    assert set(required_claim) <= set(claim_properties)
    assert set(required_bundle) <= bundle_property_names

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
        "required": required_bundle,
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
