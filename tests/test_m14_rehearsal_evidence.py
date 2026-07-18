import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "m14_rehearsal_evidence.schema.json"
EXAMPLE_PATH = ROOT / "docs" / "m14_rehearsal_evidence.example.json"


def test_m14_stopped_state_example_matches_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)


def test_m14_commit_and_manifest_hash_domains_are_distinct() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    assert len(example["repository_commit_sha"]) == 40
    assert len(example["corpus"]["corpus_json_sha256"]) == 64
    assert len(example["corpus"]["sources_csv_sha256"]) == 64
    assert schema["properties"]["repository_commit_sha"]["pattern"] == "^[0-9a-f]{40}$"
