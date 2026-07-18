import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "m14_rehearsal_evidence.schema.json"
EXAMPLE_PATH = ROOT / "docs" / "m14_rehearsal_evidence.example.json"


def _assert_required_keys(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    for key in schema.get("required", []):
        assert key in instance

    properties = schema.get("properties", {})
    for key, value in instance.items():
        property_schema = properties.get(key)
        if isinstance(value, dict) and isinstance(property_schema, dict):
            _assert_required_keys(value, property_schema)


def test_m14_stopped_state_example_has_required_structure() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    _assert_required_keys(example, schema)
    assert example["decision"] in schema["properties"]["decision"]["enum"]
    assert example["execution_state"] in schema["properties"]["execution_state"]["enum"]
    assert example["stop_condition"] is not None
    assert example["unknowns"]


def test_m14_commit_and_manifest_hash_domains_are_distinct() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    commit_pattern = schema["properties"]["repository_commit_sha"]["pattern"]
    digest_pattern = schema["$defs"]["sha256"]["pattern"]

    assert re.fullmatch(commit_pattern, example["repository_commit_sha"])
    assert re.fullmatch(digest_pattern, example["corpus"]["corpus_json_sha256"])
    assert re.fullmatch(digest_pattern, example["corpus"]["sources_csv_sha256"])
    assert len(example["repository_commit_sha"]) == 40
    assert len(example["corpus"]["corpus_json_sha256"]) == 64
    assert len(example["corpus"]["sources_csv_sha256"]) == 64
