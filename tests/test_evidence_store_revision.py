from pathlib import Path

from knowledge_engine.evidence_store_revision import evidence_store_revision


def test_revision_is_stable_for_identical_content(tmp_path: Path) -> None:
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    payload = '{"evidence_record_id":"a"}\n{"evidence_record_id":"b"}\n'
    first.write_text(payload, encoding="utf-8")
    second.write_text(payload, encoding="utf-8")

    assert evidence_store_revision(first) == evidence_store_revision(second)
    assert evidence_store_revision(first).startswith("sha256:")


def test_revision_changes_when_evidence_changes(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text('{"evidence_record_id":"a"}\n', encoding="utf-8")
    before = evidence_store_revision(evidence)

    evidence.write_text(
        '{"evidence_record_id":"a"}\n{"evidence_record_id":"b"}\n',
        encoding="utf-8",
    )

    assert evidence_store_revision(evidence) != before


def test_empty_store_has_a_deterministic_revision(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_bytes(b"")

    assert evidence_store_revision(evidence) == (
        "sha256:e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )
