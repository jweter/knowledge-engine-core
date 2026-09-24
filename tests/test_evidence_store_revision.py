import json
from pathlib import Path

from knowledge_engine.evidence_store_revision import (
    evidence_records_revision,
    evidence_store_revision,
)


def _valid_records(path: Path) -> tuple[dict[str, object], ...]:
    records: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        record_id = record.get("evidence_record_id")
        if not isinstance(record_id, str) or record_id in seen:
            continue
        seen.add(record_id)
        records.append(record)
    return tuple(records)


def test_revision_is_stable_for_formatting_only_changes(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    first.write_text('{"evidence_record_id":"a","value":1}\n', encoding="utf-8")
    second.write_text('{  "value": 1, "evidence_record_id": "a" }\n', encoding="utf-8")

    assert evidence_store_revision(first, valid_records=_valid_records) == evidence_store_revision(
        second, valid_records=_valid_records
    )


def test_revision_changes_when_usable_evidence_changes(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text('{"evidence_record_id":"a"}\n', encoding="utf-8")
    before = evidence_store_revision(evidence, valid_records=_valid_records)
    evidence.write_text(
        '{"evidence_record_id":"a"}\n{"evidence_record_id":"b"}\n', encoding="utf-8"
    )
    assert evidence_store_revision(evidence, valid_records=_valid_records) != before


def test_invalid_and_duplicate_lines_do_not_affect_revision(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text('{"evidence_record_id":"a"}\n', encoding="utf-8")
    before = evidence_store_revision(evidence, valid_records=_valid_records)
    evidence.write_text(
        '{"evidence_record_id":"a"}\nnot-json\n{"evidence_record_id":"a"}\n', encoding="utf-8"
    )
    assert evidence_store_revision(evidence, valid_records=_valid_records) == before


def test_empty_records_have_a_deterministic_revision() -> None:
    assert evidence_records_revision(()) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
