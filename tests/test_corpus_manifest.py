import json
from pathlib import Path

import pytest

from knowledge_engine.corpus import ReadinessState, ValidityState, validate_corpus_manifest
from knowledge_engine.corpus.validation import discover_project_root


def write_project(tmp_path: Path) -> Path:
    (tmp_path / "knowledge_engine").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    return tmp_path


def write_manifest(
    tmp_path: Path,
    *,
    corpus_overrides: dict[str, object] | None = None,
    header: list[str] | None = None,
    rows: list[dict[str, str]] | None = None,
    create_license: bool = True,
) -> Path:
    project_root = write_project(tmp_path)
    corpus_dir = project_root / "data" / "corpora" / "test_corpus"
    corpus_dir.mkdir(parents=True)
    if create_license:
        (corpus_dir / "license_policy.md").write_text("# License\n", encoding="utf-8")

    papers_dir = project_root / "papers" / "corpora" / "test_corpus"
    papers_dir.mkdir(parents=True)
    corpus = {
        "manifest_version": 1,
        "corpus_id": "test_corpus",
        "name": "Test Corpus",
        "description": "A test corpus.",
        "scientific_domain": "test science",
        "research_question": {"question_id": "q_test", "text": "Does the test work?"},
        "created_at": "2026-07-11",
        "updated_at": "2026-07-11T12:00:00",
        "license_policy": "license_policy.md",
        "source_manifest": "sources.csv",
        "default_local_papers_directory": "papers/corpora/test_corpus",
    }
    if corpus_overrides:
        corpus.update(corpus_overrides)

    source_header = header or [
        "source_id",
        "title",
        "publication_year",
        "doi",
        "source_url",
        "local_path",
        "access_date",
        "license_type",
        "license_url",
        "usage_status",
        "inclusion_status",
        "inclusion_reason",
        "exclusion_reason",
        "expected_content_hash",
    ]
    source_rows = rows or [valid_row()]
    lines = [",".join(source_header)]
    for row in source_rows:
        lines.append(",".join(row.get(name, "") for name in source_header))
    (corpus_dir / "sources.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    corpus_path = corpus_dir / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return corpus_path


def valid_row(**overrides: str) -> dict[str, str]:
    row = {
        "source_id": "source-1",
        "title": "Valid Paper",
        "publication_year": "2024",
        "doi": "10.1234/ABC",
        "source_url": "https://example.test/paper",
        "local_path": "paper.pdf",
        "access_date": "2026-07-11",
        "license_type": "CC-BY",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "usage_status": "approved_open_access",
        "inclusion_status": "included",
        "inclusion_reason": "Relevant to the test question.",
        "exclusion_reason": "",
        "expected_content_hash": "",
    }
    row.update(overrides)
    return row


def codes(path: Path, *, check_files: bool = False) -> list[str]:
    result = validate_corpus_manifest(path, check_files=check_files, project_root=path.parents[3])
    return [issue.code for issue in result.issues]


def test_valid_manifest_without_check_files_is_not_evaluated(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.NOT_EVALUATED
    assert result.file_counts.not_checked == 1


def test_utf8_bom_manifest_and_csv_are_accepted(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)
    corpus_path.write_text(corpus_path.read_text(encoding="utf-8"), encoding="utf-8-sig")
    sources_path = corpus_path.parent / "sources.csv"
    sources_path.write_text(sources_path.read_text(encoding="utf-8"), encoding="utf-8-sig")

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID


def test_check_files_present_pdf_is_ready(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)
    (tmp_path / "papers" / "corpora" / "test_corpus" / "paper.pdf").write_text(
        "not parsed", encoding="utf-8"
    )

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.READY
    assert result.file_counts.present == 1


def test_missing_corpus_file_is_structural_error(tmp_path: Path) -> None:
    result = validate_corpus_manifest(tmp_path / "missing.json", project_root=tmp_path)

    assert result.manifest_validity == ValidityState.INVALID
    assert result.issues[0].code == "corpus_json_missing"


def test_malformed_json_is_structural_error(tmp_path: Path) -> None:
    write_project(tmp_path)
    path = tmp_path / "corpus.json"
    path.write_text("{not-json}", encoding="utf-8")

    assert "malformed_json" in codes(path)


@pytest.mark.parametrize(
    ("override", "expected_code"),
    [
        ({"manifest_version": 2}, "unsupported_manifest_version"),
        ({"manifest_version": True}, "invalid_manifest_version_type"),
        ({"name": ""}, "empty_required_field"),
        ({"corpus_id": "Bad ID"}, "invalid_corpus_id"),
        ({"research_question": {"question_id": "q"}}, "invalid_research_question"),
        ({"created_at": "not-a-date"}, "invalid_date"),
        ({"source_manifest": "missing.csv"}, "source_manifest_missing"),
        ({"license_policy": "missing.md"}, "license_policy_missing"),
    ],
)
def test_corpus_json_validation_cases(
    tmp_path: Path, override: dict[str, object], expected_code: str
) -> None:
    corpus_path = write_manifest(tmp_path, corpus_overrides=override)

    assert expected_code in codes(corpus_path)


@pytest.mark.parametrize(
    ("field", "value", "expected_code"),
    [
        ("source_manifest", "/tmp/sources.csv", "absolute_path"),
        ("license_policy", "/tmp/license.md", "absolute_path"),
        ("default_local_papers_directory", "/tmp/papers", "absolute_path"),
        ("source_manifest", "../sources.csv", "path_traversal"),
        ("license_policy", "../license.md", "path_traversal"),
        ("default_local_papers_directory", "../papers", "path_traversal"),
    ],
)
def test_corpus_path_validation(tmp_path: Path, field: str, value: str, expected_code: str) -> None:
    corpus_path = write_manifest(tmp_path, corpus_overrides={field: value})

    assert expected_code in codes(corpus_path)


def test_project_root_discovery_from_subdirectory(tmp_path: Path) -> None:
    write_project(tmp_path)
    subdirectory = tmp_path / "docs" / "nested"
    subdirectory.mkdir(parents=True)

    assert discover_project_root(subdirectory) == tmp_path.resolve()


def test_project_root_discovery_without_project_markers_uses_start_directory(
    tmp_path: Path,
) -> None:
    isolated = tmp_path / "isolated"
    isolated.mkdir()

    assert discover_project_root(isolated) == isolated.resolve()


def test_missing_required_csv_header(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path, header=["source_id", "title"])

    assert "missing_required_header" in codes(corpus_path)


def test_duplicate_header(tmp_path: Path) -> None:
    corpus_path = write_manifest(
        tmp_path,
        header=["source_id", "source_id", "title", "usage_status", "inclusion_status"],
    )

    assert "duplicate_header" in codes(corpus_path)


def test_malformed_csv_row(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)
    sources = corpus_path.parent / "sources.csv"
    sources.write_text("source_id,title,usage_status,inclusion_status\none,t,u,i,extra\n")

    assert "malformed_csv_row" in codes(corpus_path)


@pytest.mark.parametrize(
    ("row", "expected_code"),
    [
        (valid_row(source_id=""), "empty_source_id"),
        (valid_row(source_id="Bad ID"), "invalid_source_id"),
        (valid_row(title=""), "empty_title"),
        (valid_row(usage_status="unclear"), "invalid_usage_status"),
        (valid_row(inclusion_status="maybe"), "invalid_inclusion_status"),
        (valid_row(publication_year="24"), "invalid_publication_year"),
        (valid_row(access_date="July 11"), "invalid_date"),
        (valid_row(expected_content_hash="md5:abc"), "unsupported_hash_algorithm"),
        (valid_row(expected_content_hash="sha256:ABC"), "invalid_hash_format"),
    ],
)
def test_source_row_validation_cases(
    tmp_path: Path, row: dict[str, str], expected_code: str
) -> None:
    corpus_path = write_manifest(tmp_path, rows=[row])

    assert expected_code in codes(corpus_path)


def test_duplicate_source_id_is_structural_error(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path, rows=[valid_row(), valid_row(title="Second")])

    assert "duplicate_source_id" in codes(corpus_path)


YEAR_COMPATIBILITY_BASE_HEADERS = [
    "source_id",
    "title",
    "source_url",
    "access_date",
    "inclusion_reason",
    "license_type",
    "license_url",
    "usage_status",
    "inclusion_status",
]


@pytest.mark.parametrize(
    ("header", "row", "expected_code"),
    [
        (
            [*YEAR_COMPATIBILITY_BASE_HEADERS, "publication_year"],
            valid_row(),
            "",
        ),
        (
            [*YEAR_COMPATIBILITY_BASE_HEADERS, "year"],
            valid_row(year="2024"),
            "deprecated_year_column",
        ),
        (
            [*YEAR_COMPATIBILITY_BASE_HEADERS, "publication_year", "year"],
            valid_row(year="2024"),
            "redundant_year_column",
        ),
        (
            [*YEAR_COMPATIBILITY_BASE_HEADERS, "publication_year", "year"],
            valid_row(publication_year="", year="2024"),
            "year_column_partial_compatibility",
        ),
        (
            [*YEAR_COMPATIBILITY_BASE_HEADERS, "publication_year", "year"],
            valid_row(year="2023"),
            "conflicting_year_columns",
        ),
    ],
)
def test_year_compatibility(
    tmp_path: Path, header: list[str], row: dict[str, str], expected_code: str
) -> None:
    corpus_path = write_manifest(tmp_path, header=header, rows=[row])
    issue_codes = codes(corpus_path)

    if expected_code:
        assert expected_code in issue_codes
    else:
        assert not issue_codes


@pytest.mark.parametrize(
    ("local_path", "expected_code"),
    [
        ("/tmp/paper.pdf", "absolute_path"),
        ("C:/tmp/paper.pdf", "absolute_path"),
        ("\\\\server\\share\\paper.pdf", "absolute_path"),
        ("../paper.pdf", "path_traversal"),
        ("nested/../paper.pdf", "path_traversal"),
        ("papers/corpora/test_corpus/paper.pdf", "repeated_papers_directory"),
    ],
)
def test_local_path_contract(tmp_path: Path, local_path: str, expected_code: str) -> None:
    corpus_path = write_manifest(tmp_path, rows=[valid_row(local_path=local_path)])

    assert expected_code in codes(corpus_path)


def test_nested_local_path_beneath_papers_directory_is_allowed(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path, rows=[valid_row(local_path="nested/paper.PDF")])
    nested = tmp_path / "papers" / "corpora" / "test_corpus" / "nested"
    nested.mkdir()
    (nested / "paper.PDF").write_text("not parsed", encoding="utf-8")

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.READY
    assert result.file_counts.present == 1


def test_symlink_escape_is_structural_error(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)
    papers_dir = tmp_path / "papers" / "corpora" / "test_corpus"
    outside = tmp_path / "outside.pdf"
    outside.write_text("outside", encoding="utf-8")
    link = papers_dir / "paper.pdf"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this environment.")

    assert "path_escape" in codes(corpus_path, check_files=True)


@pytest.mark.parametrize(
    ("row", "expected_code"),
    [
        (valid_row(source_url=""), "missing_source_url"),
        (valid_row(access_date=""), "missing_access_date"),
        (valid_row(inclusion_reason=""), "missing_inclusion_reason"),
        (valid_row(usage_status="needs_legal_review"), "usage_status_not_importable"),
        (valid_row(license_url=""), "missing_license_url"),
        (valid_row(license_type=""), "missing_license_type"),
    ],
)
def test_import_readiness_blockers(tmp_path: Path, row: dict[str, str], expected_code: str) -> None:
    corpus_path = write_manifest(tmp_path, rows=[row])

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.BLOCKED
    assert expected_code in [issue.code for issue in result.issues]


def test_excluded_row_with_reason_is_accepted(tmp_path: Path) -> None:
    row = valid_row(
        usage_status="excluded_legal",
        inclusion_status="excluded",
        source_url="",
        access_date="",
        inclusion_reason="",
        exclusion_reason="Not legally usable.",
    )
    corpus_path = write_manifest(tmp_path, rows=[row])

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.NOT_EVALUATED


@pytest.mark.parametrize("status", ["candidate", "deferred"])
def test_candidate_and_deferred_rows_are_accepted(tmp_path: Path, status: str) -> None:
    corpus_path = write_manifest(
        tmp_path,
        rows=[
            valid_row(
                usage_status="needs_legal_review",
                inclusion_status=status,
                source_url="",
                access_date="",
                inclusion_reason="",
            )
        ],
    )

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID


def test_duplicate_normalized_doi_is_warning(tmp_path: Path) -> None:
    corpus_path = write_manifest(
        tmp_path,
        rows=[
            valid_row(source_id="source-1", doi="https://doi.org/10.1234/ABC"),
            valid_row(source_id="source-2", doi="doi:10.1234/abc"),
        ],
    )

    result = validate_corpus_manifest(corpus_path, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert "duplicate_normalized_doi" in [issue.code for issue in result.warnings]


def test_missing_doi_is_allowed(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path, rows=[valid_row(doi="")])

    assert codes(corpus_path) == []


def test_check_files_missing_pdf_blocks_readiness_not_validity(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert result.import_readiness == ReadinessState.BLOCKED
    assert result.file_counts.missing == 1
    assert "local_file_missing" in [issue.code for issue in result.import_blockers]


def test_check_files_directory_blocks_readiness(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path)
    (tmp_path / "papers" / "corpora" / "test_corpus" / "paper.pdf").mkdir()

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert "local_file_not_file" in [issue.code for issue in result.import_blockers]


def test_check_files_unsupported_extension_blocks_readiness(tmp_path: Path) -> None:
    corpus_path = write_manifest(tmp_path, rows=[valid_row(local_path="paper.txt")])
    (tmp_path / "papers" / "corpora" / "test_corpus" / "paper.txt").write_text(
        "text", encoding="utf-8"
    )

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert "unsupported_file_type" in [issue.code for issue in result.import_blockers]


@pytest.mark.parametrize(
    "row",
    [
        valid_row(usage_status="metadata_only", local_path="", inclusion_status="candidate"),
        valid_row(usage_status="excluded_legal", local_path="", inclusion_status="excluded"),
    ],
)
def test_non_importable_rows_do_not_require_pdf_when_checking(
    tmp_path: Path, row: dict[str, str]
) -> None:
    corpus_path = write_manifest(tmp_path, rows=[row])

    result = validate_corpus_manifest(corpus_path, check_files=True, project_root=tmp_path)

    assert result.manifest_validity == ValidityState.VALID
    assert "missing_local_path" not in [issue.code for issue in result.issues]
