from __future__ import annotations

import copy
import dataclasses
import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.online_evidence import (
    Citation,
    EvidenceClaim,
    EvidenceExcerpt,
    OnlineEvidenceBundle,
    OnlineSource,
)
from knowledge_engine.online_evidence_schema import (
    build_schema,
    render_schema,
    required_fields_for_bundle,
    required_fields_for_citation,
    required_fields_for_claim,
    required_fields_for_excerpt,
    required_fields_for_source,
    validate,
)

SCHEMA_PATH = Path(__file__).parent.parent / "docs" / "schemas" / "online_evidence_v1.schema.json"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "online_evidence" / "bundle.json"


def _load_fixture() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(FIXTURE_PATH.read_text("utf-8"))
    return payload


def _load_committed_schema() -> dict[str, Any]:
    schema: dict[str, Any] = json.loads(SCHEMA_PATH.read_text("utf-8"))
    return schema


def test_the_committed_schema_file_is_regenerated_byte_identically() -> None:
    assert SCHEMA_PATH.read_text("utf-8") == render_schema()


def test_the_golden_fixture_validates_against_the_committed_schema() -> None:
    schema = _load_committed_schema()
    bundle = _load_fixture()
    assert validate(bundle, schema) == []


def test_a_missing_required_field_is_rejected() -> None:
    schema = _load_committed_schema()
    bundle = copy.deepcopy(_load_fixture())
    del bundle["sources"][0]["content_sha256"]
    problems = validate(bundle, schema)
    assert any("content_sha256" in problem for problem in problems)


def test_a_renamed_field_is_rejected() -> None:
    schema = _load_committed_schema()
    bundle = copy.deepcopy(_load_fixture())
    bundle["sources"][0]["sourceId"] = bundle["sources"][0].pop("source_id")
    problems = validate(bundle, schema)
    assert any("source_id" in problem for problem in problems)


def test_a_retyped_field_is_rejected() -> None:
    schema = _load_committed_schema()
    bundle = copy.deepcopy(_load_fixture())
    bundle["sources"][0]["retrieved_at"] = 12345
    problems = validate(bundle, schema)
    assert any("retrieved_at" in problem for problem in problems)


def test_an_invalid_enum_value_is_rejected() -> None:
    schema = _load_committed_schema()
    bundle = copy.deepcopy(_load_fixture())
    bundle["sources"][0]["status"] = "downloaded"
    problems = validate(bundle, schema)
    assert any("downloaded" in problem for problem in problems)


def test_additive_optional_fields_are_allowed() -> None:
    schema = _load_committed_schema()
    bundle = copy.deepcopy(_load_fixture())
    bundle["future_top_level_field"] = "x"
    bundle["sources"][0]["future_field"] = "x"
    bundle["excerpts"][0]["future_field"] = "x"
    bundle["claims"][0]["future_field"] = "x"
    bundle["claims"][0]["citations"][0]["future_field"] = "x"
    assert validate(bundle, schema) == []


def test_schema_required_fields_are_pinned_to_the_v1_baseline() -> None:
    """The committed schema's `required` lists are the frozen v1 baseline.

    This is the schema-drift guard for `required`: it reads the committed JSON
    Schema file from disk and compares it against `online_evidence_schema.py`'s
    own pinned `required_fields_for_*` functions (not live `dataclasses.fields`
    introspection -- see that module's docstring for why: deriving `required`
    from whatever fields the dataclasses carry today would silently force a
    future, additive, optional field to become required on the wire the moment
    it was added). A hand-edit of the committed schema file that drifts from
    the pinned baseline fails here.
    """

    schema = _load_committed_schema()
    assert schema["required"] == required_fields_for_bundle()
    assert schema["$defs"]["OnlineSource"]["required"] == required_fields_for_source()
    assert schema["$defs"]["EvidenceExcerpt"]["required"] == required_fields_for_excerpt()
    assert schema["$defs"]["Citation"]["required"] == required_fields_for_citation()
    assert schema["$defs"]["EvidenceClaim"]["required"] == required_fields_for_claim()


def test_schema_properties_cover_every_current_dataclass_field() -> None:
    """The committed schema's declared properties cover Core's live dataclasses.

    This is the complementary schema-drift guard for `properties`: a field
    added, removed or renamed on `OnlineSource`/`EvidenceExcerpt`/`Citation`/
    `EvidenceClaim`/`OnlineEvidenceBundle` must show up as a declared property
    (so it can never go silently undocumented), even though -- per the
    additive-only rule -- a newly added field must never be forced into
    `required` (covered by the test above, not this one).
    """

    schema = _load_committed_schema()
    assert {f.name for f in dataclasses.fields(OnlineSource)} <= set(
        schema["$defs"]["OnlineSource"]["properties"]
    )
    assert {f.name for f in dataclasses.fields(EvidenceExcerpt)} <= set(
        schema["$defs"]["EvidenceExcerpt"]["properties"]
    )
    assert {f.name for f in dataclasses.fields(Citation)} <= set(
        schema["$defs"]["Citation"]["properties"]
    )
    assert {f.name for f in dataclasses.fields(EvidenceClaim)} <= set(
        schema["$defs"]["EvidenceClaim"]["properties"]
    )
    assert {f.name for f in dataclasses.fields(OnlineEvidenceBundle)} <= set(schema["properties"])


def test_a_newly_added_optional_field_remains_optional_on_the_wire() -> None:
    """Simulates the additive-only growth path the pinned `required` baseline exists for.

    A new field joins `properties` as optional (the only way `build_schema`'s
    own helpers ever let a field be added -- `required` is never touched by
    it). This proves the field is genuinely optional, not merely an unknown
    extra tolerated by `additionalProperties` (that case is covered by
    `test_additive_optional_fields_are_allowed`): a declared, typed property
    that is absent validates, present with the declared type validates, and
    present with the wrong type is rejected. Before this module's fix, a
    `required` list derived live from `dataclasses.fields` would have had no
    way to add a field without also making it required -- the exact
    regression this guards against structurally, by keeping `required`
    pinned.
    """

    schema = copy.deepcopy(_load_committed_schema())
    schema["$defs"]["OnlineSource"]["properties"]["retracted"] = {"type": ["boolean", "null"]}
    assert "retracted" not in schema["$defs"]["OnlineSource"]["required"]

    absent = _load_fixture()
    assert "retracted" not in absent["sources"][0]
    assert validate(absent, schema) == []

    present_and_typed = copy.deepcopy(absent)
    present_and_typed["sources"][0]["retracted"] = True
    assert validate(present_and_typed, schema) == []

    present_and_wrongly_typed = copy.deepcopy(absent)
    present_and_wrongly_typed["sources"][0]["retracted"] = "yes"
    problems = validate(present_and_wrongly_typed, schema)
    assert any("retracted" in problem for problem in problems)


def test_build_schema_is_stable() -> None:
    assert build_schema() == build_schema()


def test_cli_prints_the_schema_to_stdout_by_default() -> None:
    result = CliRunner().invoke(entrypoint.app, ["online-evidence-schema"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == build_schema()


def test_cli_writes_the_schema_to_an_output_path(tmp_path: Path) -> None:
    output = tmp_path / "schema.json"
    result = CliRunner().invoke(entrypoint.app, ["online-evidence-schema", "--output", str(output)])
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text("utf-8")) == build_schema()
