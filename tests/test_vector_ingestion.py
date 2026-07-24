import json
from pathlib import Path

from knowledge_engine.vector_search import (
    EXTERNAL_VECTOR_INGESTION_RULES_VERSION,
    load_external_vectors,
)


def write_vectors(tmp_path: Path, records: list[dict[str, object]]) -> Path:
    path = tmp_path / "vectors.jsonl"
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    return path


def test_external_vector_ingestion_rules_version_is_stable() -> None:
    assert EXTERNAL_VECTOR_INGESTION_RULES_VERSION == "m30-external-vector-ingestion-v1"


def test_load_external_vectors_accepts_well_formed_file(tmp_path: Path) -> None:
    path = write_vectors(
        tmp_path,
        [
            {"paper_id": 1, "vector": [0.1, 0.2, 0.3], "embedding_model": "external:test-v1"},
            {"paper_id": 2, "vector": [0.4, 0.5, 0.6], "embedding_model": "external:test-v1"},
        ],
    )

    result = load_external_vectors(path)

    assert result.errors == ()
    assert result.dimension == 3
    assert len(result.records) == 2
    assert result.records[0].paper_id == 1
    assert result.records[0].vector == (0.1, 0.2, 0.3)
    assert result.records[0].embedding_model == "external:test-v1"


def test_load_external_vectors_rejects_missing_file(tmp_path: Path) -> None:
    result = load_external_vectors(tmp_path / "does_not_exist.jsonl")

    assert result.records == ()
    assert len(result.errors) == 1
    assert "does not exist" in result.errors[0]


def test_load_external_vectors_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    result = load_external_vectors(path)

    assert result.records == ()
    assert "no records" in result.errors[0]


def test_load_external_vectors_reports_invalid_json_by_line(tmp_path: Path) -> None:
    path = tmp_path / "vectors.jsonl"
    path.write_text("not json\n", encoding="utf-8")

    result = load_external_vectors(path)

    assert result.records == ()
    assert "Line 1: invalid JSON." in result.errors


def test_load_external_vectors_reports_missing_fields(tmp_path: Path) -> None:
    path = write_vectors(tmp_path, [{"paper_id": 1, "vector": [0.1]}])

    result = load_external_vectors(path)

    assert result.records == ()
    assert "missing required field(s): embedding_model" in result.errors[0]


def test_load_external_vectors_rejects_non_integer_paper_id(tmp_path: Path) -> None:
    path = write_vectors(tmp_path, [{"paper_id": "1", "vector": [0.1], "embedding_model": "test"}])

    result = load_external_vectors(path)

    assert "paper_id must be an integer" in result.errors[0]


def test_load_external_vectors_rejects_empty_embedding_model(tmp_path: Path) -> None:
    path = write_vectors(tmp_path, [{"paper_id": 1, "vector": [0.1], "embedding_model": "  "}])

    result = load_external_vectors(path)

    assert "embedding_model must be a non-empty string" in result.errors[0]


def test_load_external_vectors_rejects_empty_vector(tmp_path: Path) -> None:
    path = write_vectors(tmp_path, [{"paper_id": 1, "vector": [], "embedding_model": "test"}])

    result = load_external_vectors(path)

    assert "vector must be a non-empty array of numbers" in result.errors[0]


def test_load_external_vectors_rejects_non_numeric_vector_component(tmp_path: Path) -> None:
    path = write_vectors(
        tmp_path, [{"paper_id": 1, "vector": [0.1, "x"], "embedding_model": "test"}]
    )

    result = load_external_vectors(path)

    assert "vector must contain only numbers" in result.errors[0]


def test_load_external_vectors_rejects_dimension_mismatch_across_records(tmp_path: Path) -> None:
    path = write_vectors(
        tmp_path,
        [
            {"paper_id": 1, "vector": [0.1, 0.2], "embedding_model": "test"},
            {"paper_id": 2, "vector": [0.1, 0.2, 0.3], "embedding_model": "test"},
        ],
    )

    result = load_external_vectors(path)

    assert len(result.records) == 1
    assert "dimension 3, expected 2" in result.errors[0]


def test_load_external_vectors_rejects_duplicate_paper_id(tmp_path: Path) -> None:
    path = write_vectors(
        tmp_path,
        [
            {"paper_id": 1, "vector": [0.1], "embedding_model": "test"},
            {"paper_id": 1, "vector": [0.2], "embedding_model": "test"},
        ],
    )

    result = load_external_vectors(path)

    assert len(result.records) == 1
    assert "duplicate paper_id: 1" in result.errors[0]


def test_load_external_vectors_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "vectors.jsonl"
    record = json.dumps({"paper_id": 1, "vector": [0.1], "embedding_model": "test"})
    path.write_text(f"\n{record}\n\n", encoding="utf-8")

    result = load_external_vectors(path)

    assert result.errors == ()
    assert len(result.records) == 1
