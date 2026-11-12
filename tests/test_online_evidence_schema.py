from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
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


def test_schema_required_fields_match_cores_own_dataclasses() -> None:
    """The committed schema's required fields must match Core's live dataclasses.

    This is the schema-drift guard: it reads the committed JSON Schema file
    from disk and compares it against `dataclasses.fields` introspection of
    `OnlineEvidenceBundle`/`OnlineSource`/`EvidenceExcerpt`/`Citation`/
    `EvidenceClaim` themselves, independent of `build_schema`'s own internal
    consistency assertions. A field added, removed or renamed on one of those
    dataclasses without regenerating the committed schema file fails here.
    """

    schema = _load_committed_schema()
    assert set(schema["required"]) == set(required_fields_for_bundle())
    assert set(schema["$defs"]["OnlineSource"]["required"]) == set(required_fields_for_source())
    assert set(schema["$defs"]["EvidenceExcerpt"]["required"]) == set(required_fields_for_excerpt())
    assert set(schema["$defs"]["Citation"]["required"]) == set(required_fields_for_citation())
    assert set(schema["$defs"]["EvidenceClaim"]["required"]) == set(required_fields_for_claim())


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
