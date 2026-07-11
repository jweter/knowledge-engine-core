"""Validation service for versioned corpus manifests."""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from knowledge_engine.corpus.models import CorpusValidationResult, Issue, IssueSeverity
from knowledge_engine.utils import normalize_doi

MANIFEST_VERSION = 1
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
APPROVED_FULL_TEXT_STATUSES = {
    "approved_open_access",
    "approved_public_domain",
    "approved_author_manuscript",
    "approved_local_only",
}
USAGE_STATUSES = APPROVED_FULL_TEXT_STATUSES | {
    "metadata_only",
    "needs_legal_review",
    "excluded_legal",
}
INCLUSION_STATUSES = {"included", "candidate", "excluded", "deferred"}
REQUIRED_CORPUS_FIELDS = {
    "manifest_version",
    "corpus_id",
    "name",
    "description",
    "scientific_domain",
    "research_question",
    "created_at",
    "updated_at",
    "license_policy",
    "source_manifest",
    "default_local_papers_directory",
}
REQUIRED_CSV_HEADERS = {"source_id", "title", "usage_status", "inclusion_status"}
PDF_SUFFIX = ".pdf"


def validate_corpus_manifest(
    corpus_path: Path,
    *,
    check_files: bool = False,
    project_root: Path | None = None,
) -> CorpusValidationResult:
    """Validate a corpus JSON file and its version 1 source CSV."""

    root = (project_root or discover_project_root()).resolve()
    result = CorpusValidationResult(check_files=check_files)
    corpus_path = corpus_path.expanduser()

    if not corpus_path.exists():
        _add_manifest_error(
            result,
            "corpus_json_missing",
            f"Corpus JSON does not exist: {_display_path(corpus_path, root)}.",
        )
        return result
    if not corpus_path.is_file():
        _add_manifest_error(
            result,
            "corpus_json_not_file",
            f"Corpus JSON is not a file: {_display_path(corpus_path, root)}.",
        )
        return result

    corpus_dir = corpus_path.parent
    corpus_data = _load_json(corpus_path, result, root)
    if not isinstance(corpus_data, dict):
        return result

    _validate_corpus_fields(corpus_data, result)
    source_manifest = _metadata_path(
        corpus_data.get("source_manifest"),
        field="source_manifest",
        corpus_dir=corpus_dir,
        result=result,
        root=root,
        must_exist=True,
    )
    _metadata_path(
        corpus_data.get("license_policy"),
        field="license_policy",
        corpus_dir=corpus_dir,
        result=result,
        root=root,
        must_exist=True,
    )
    papers_dir = _papers_directory(
        corpus_data.get("default_local_papers_directory"),
        result=result,
        root=root,
    )

    if source_manifest is None:
        return _finalize_valid_rows(result)

    rows = _load_source_rows(source_manifest, result, root)
    _validate_rows(rows, result, papers_dir=papers_dir, root=root, check_files=check_files)
    return _finalize_valid_rows(result)


def discover_project_root(start: Path | None = None) -> Path:
    """Discover a project root by walking upward from ``start`` or the cwd."""

    current = (start or Path.cwd()).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (candidate / "knowledge_engine").exists():
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return current


def _load_json(
    corpus_path: Path,
    result: CorpusValidationResult,
    root: Path,
) -> dict[str, Any] | None:
    try:
        loaded = json.loads(corpus_path.read_text(encoding="utf-8-sig"))
    except JSONDecodeError as exc:
        _add_manifest_error(
            result,
            "malformed_json",
            f"Malformed corpus JSON at line {exc.lineno}, column {exc.colno}.",
        )
        return None
    except OSError as exc:
        _add_manifest_error(
            result,
            "corpus_json_unreadable",
            f"Could not read corpus JSON {_display_path(corpus_path, root)}: {exc.strerror}.",
        )
        return None

    if not isinstance(loaded, dict):
        _add_manifest_error(result, "corpus_json_not_object", "Corpus JSON must be an object.")
        return None
    return loaded


def _validate_corpus_fields(data: dict[str, Any], result: CorpusValidationResult) -> None:
    missing = sorted(REQUIRED_CORPUS_FIELDS.difference(data))
    for field in missing:
        _add_manifest_error(
            result, "missing_required_field", f"Missing required field: {field}.", field
        )

    version = data.get("manifest_version")
    if isinstance(version, bool) or not isinstance(version, int):
        _add_manifest_error(
            result,
            "invalid_manifest_version_type",
            "manifest_version must be integer 1.",
            "manifest_version",
        )
    elif version != MANIFEST_VERSION:
        _add_manifest_error(
            result,
            "unsupported_manifest_version",
            f"Unsupported manifest_version {version}; supported value is 1.",
            "manifest_version",
        )
    else:
        result.manifest_version = version

    corpus_id = _optional_text(data.get("corpus_id"))
    result.corpus_id = corpus_id
    if corpus_id and not IDENTIFIER_RE.fullmatch(corpus_id):
        _add_manifest_error(
            result,
            "invalid_corpus_id",
            "corpus_id must match ^[a-z0-9][a-z0-9_-]*$.",
            "corpus_id",
        )

    result.corpus_name = _optional_text(data.get("name"))
    for field in [
        "corpus_id",
        "name",
        "description",
        "scientific_domain",
        "created_at",
        "updated_at",
        "license_policy",
        "source_manifest",
        "default_local_papers_directory",
    ]:
        if field in data and not _optional_text(data.get(field)):
            _add_manifest_error(
                result,
                "empty_required_field",
                f"{field} must not be empty.",
                field,
            )

    research_question = data.get("research_question")
    if not isinstance(research_question, dict):
        _add_manifest_error(
            result,
            "invalid_research_question",
            "research_question must be an object with question_id and text.",
            "research_question",
        )
    else:
        for field in ["question_id", "text"]:
            if not _optional_text(research_question.get(field)):
                _add_manifest_error(
                    result,
                    "invalid_research_question",
                    f"research_question.{field} is required.",
                    f"research_question.{field}",
                )

    for field in ["created_at", "updated_at"]:
        value = _optional_text(data.get(field))
        if value and not _is_iso_date_or_datetime(value):
            _add_manifest_error(
                result,
                "invalid_date",
                f"{field} must be a valid ISO 8601 date or datetime.",
                field,
            )


def _metadata_path(
    value: Any,
    *,
    field: str,
    corpus_dir: Path,
    result: CorpusValidationResult,
    root: Path,
    must_exist: bool,
) -> Path | None:
    raw = _optional_text(value)
    if not raw:
        return None
    path = Path(raw)
    if _looks_absolute(path):
        _add_manifest_error(
            result, "absolute_path", f"{field} must be relative to corpus.json.", field
        )
        return None
    if _has_traversal(path):
        _add_manifest_error(result, "path_traversal", f"{field} must not contain '..'.", field)
        return None
    resolved = _resolve_under(corpus_dir, path)
    if not _is_relative_to(resolved, corpus_dir.resolve()):
        _add_manifest_error(
            result,
            "path_escape",
            f"{field} escapes the directory containing corpus.json.",
            field,
        )
        return None
    if field == "source_manifest":
        result.source_manifest_path = raw
    if must_exist and not resolved.is_file():
        _add_manifest_error(
            result,
            f"{field}_missing",
            f"{field} does not exist: {raw}.",
            field,
        )
        return None
    return resolved


def _papers_directory(value: Any, *, result: CorpusValidationResult, root: Path) -> Path | None:
    raw = _optional_text(value)
    if not raw:
        return None
    path = Path(raw)
    if _looks_absolute(path):
        _add_manifest_error(
            result,
            "absolute_path",
            "default_local_papers_directory must be relative to the project root.",
            "default_local_papers_directory",
        )
        return None
    if _has_traversal(path):
        _add_manifest_error(
            result,
            "path_traversal",
            "default_local_papers_directory must not contain '..'.",
            "default_local_papers_directory",
        )
        return None
    resolved = _resolve_under(root, path)
    if not _is_relative_to(resolved, root):
        _add_manifest_error(
            result,
            "path_escape",
            "default_local_papers_directory escapes the project root.",
            "default_local_papers_directory",
        )
        return None
    return resolved


def _load_source_rows(
    source_manifest: Path,
    result: CorpusValidationResult,
    root: Path,
) -> list[dict[str, str]]:
    try:
        lines = source_manifest.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        _add_manifest_error(
            result,
            "source_manifest_unreadable",
            (
                f"Could not read source manifest {_display_path(source_manifest, root)}: "
                f"{exc.strerror}."
            ),
        )
        return []

    if not lines:
        _add_manifest_error(result, "csv_header_missing", "Source CSV is empty.")
        return []

    header = next(csv.reader([lines[0]]), [])
    if not header:
        _add_manifest_error(result, "csv_header_missing", "Source CSV header is missing.")
        return []
    duplicate_headers = _duplicates([name.strip() for name in header if name.strip()])
    for name in duplicate_headers:
        _add_manifest_error(
            result,
            "duplicate_header",
            f"Duplicate CSV header: {name}.",
            field=name,
            line_number=1,
        )

    missing_headers = sorted(REQUIRED_CSV_HEADERS.difference(header))
    for name in missing_headers:
        _add_manifest_error(
            result,
            "missing_required_header",
            f"Missing required CSV header: {name}.",
            field=name,
            line_number=1,
        )

    rows: list[dict[str, str]] = []
    reader = csv.reader(lines)
    headers = next(reader)
    for line_number, row_values in enumerate(reader, start=2):
        if not any(value.strip() for value in row_values):
            continue
        if len(row_values) > len(headers):
            _add_manifest_error(
                result,
                "malformed_csv_row",
                f"Row has {len(row_values)} fields but header has {len(headers)}.",
                line_number=line_number,
            )
            continue
        row = dict(zip(headers, row_values, strict=False))
        row["_line_number"] = str(line_number)
        rows.append(row)

    result.total_source_rows = len(rows)
    return rows


def _validate_rows(
    rows: list[dict[str, str]],
    result: CorpusValidationResult,
    *,
    papers_dir: Path | None,
    root: Path,
    check_files: bool,
) -> None:
    seen_source_ids: dict[str, int] = {}
    dois_by_normalized: dict[str, list[tuple[str, int]]] = defaultdict(list)

    for row in rows:
        line_number = int(row["_line_number"])
        source_id = _row_text(row, "source_id")
        usage_status = _row_text(row, "usage_status")
        inclusion_status = _row_text(row, "inclusion_status")

        result.usage_status_counts[usage_status or "unspecified"] += 1
        result.inclusion_status_counts[inclusion_status or "unspecified"] += 1

        _validate_source_identity(source_id, seen_source_ids, result, line_number)
        _require_row_text(row, "title", result, source_id, line_number)
        _validate_controlled_statuses(
            usage_status, inclusion_status, result, source_id, line_number
        )
        _validate_year(row, result, source_id, line_number)
        _validate_iso_row_date(row, "access_date", result, source_id, line_number)
        _validate_hash(row, result, source_id, line_number)
        _validate_conditional_fields(row, result, source_id, line_number)
        _validate_local_file(row, result, papers_dir, root, check_files, source_id, line_number)

        doi = _row_text(row, "doi")
        if doi:
            dois_by_normalized[normalize_doi(doi)].append((source_id or "unknown", line_number))

    for normalized_doi in sorted(dois_by_normalized):
        matches = dois_by_normalized[normalized_doi]
        if normalized_doi and len(matches) > 1:
            affected = ", ".join(f"{source_id} (line {line})" for source_id, line in matches)
            result.issues.append(
                Issue(
                    code="duplicate_normalized_doi",
                    severity=IssueSeverity.WARNING,
                    category="identifier",
                    message=f"Duplicate normalized DOI '{normalized_doi}' appears in: {affected}.",
                    field="doi",
                )
            )


def _validate_source_identity(
    source_id: str,
    seen_source_ids: dict[str, int],
    result: CorpusValidationResult,
    line_number: int,
) -> None:
    if not source_id:
        _add_row_error(
            result,
            "empty_source_id",
            "source_id must not be empty.",
            source_id,
            "source_id",
            line_number,
        )
        return
    if not IDENTIFIER_RE.fullmatch(source_id):
        _add_row_error(
            result,
            "invalid_source_id",
            "source_id must match ^[a-z0-9][a-z0-9_-]*$.",
            source_id,
            "source_id",
            line_number,
        )
    if source_id in seen_source_ids:
        _add_row_error(
            result,
            "duplicate_source_id",
            f"Duplicate source_id also appears on line {seen_source_ids[source_id]}.",
            source_id,
            "source_id",
            line_number,
        )
    else:
        seen_source_ids[source_id] = line_number


def _validate_controlled_statuses(
    usage_status: str,
    inclusion_status: str,
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    if usage_status not in USAGE_STATUSES:
        _add_row_error(
            result,
            "invalid_usage_status",
            f"usage_status must be one of: {', '.join(sorted(USAGE_STATUSES))}.",
            source_id,
            "usage_status",
            line_number,
        )
    if inclusion_status not in INCLUSION_STATUSES:
        _add_row_error(
            result,
            "invalid_inclusion_status",
            f"inclusion_status must be one of: {', '.join(sorted(INCLUSION_STATUSES))}.",
            source_id,
            "inclusion_status",
            line_number,
        )


def _validate_year(
    row: dict[str, str],
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    publication_year = _row_text(row, "publication_year")
    publication_year_present = "publication_year" in row
    legacy_year_present = "year" in row
    legacy_year = _row_text(row, "year")

    if publication_year and not re.fullmatch(r"\d{4}", publication_year):
        _add_row_error(
            result,
            "invalid_publication_year",
            "publication_year must be four digits when present.",
            source_id,
            "publication_year",
            line_number,
        )
    if legacy_year and not re.fullmatch(r"\d{4}", legacy_year):
        _add_row_error(
            result,
            "invalid_publication_year",
            "year must be four digits when present.",
            source_id,
            "year",
            line_number,
        )

    if legacy_year_present and not publication_year_present and legacy_year:
        _add_row_warning(
            result,
            "deprecated_year_column",
            "year is deprecated; rename it to publication_year in manifest version 1.",
            source_id,
            "year",
            line_number,
        )
    elif (
        legacy_year_present
        and publication_year_present
        and bool(legacy_year) != bool(publication_year)
    ):
        _add_row_warning(
            result,
            "year_column_partial_compatibility",
            (
                "year and publication_year are both present but one is empty; "
                "using the non-empty value."
            ),
            source_id,
            "year",
            line_number,
        )
    elif (
        legacy_year_present and legacy_year and publication_year and legacy_year == publication_year
    ):
        _add_row_warning(
            result,
            "redundant_year_column",
            "year is redundant because publication_year has the same value.",
            source_id,
            "year",
            line_number,
        )
    elif legacy_year and publication_year and legacy_year != publication_year:
        _add_row_error(
            result,
            "conflicting_year_columns",
            "year and publication_year have conflicting values.",
            source_id,
            "publication_year",
            line_number,
        )


def _validate_iso_row_date(
    row: dict[str, str],
    field: str,
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    value = _row_text(row, field)
    if value and not _is_iso_date_or_datetime(value):
        _add_row_error(
            result,
            "invalid_date",
            f"{field} must be a valid ISO 8601 date or datetime.",
            source_id,
            field,
            line_number,
        )


def _validate_hash(
    row: dict[str, str],
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    value = _row_text(row, "expected_content_hash")
    if not value:
        return
    algorithm = value.split(":", 1)[0] if ":" in value else ""
    if algorithm != "sha256":
        _add_row_error(
            result,
            "unsupported_hash_algorithm",
            "expected_content_hash must use sha256:<64 lowercase hexadecimal characters>.",
            source_id,
            "expected_content_hash",
            line_number,
        )
        return
    if not HASH_RE.fullmatch(value):
        _add_row_error(
            result,
            "invalid_hash_format",
            "expected_content_hash must match sha256:<64 lowercase hexadecimal characters>.",
            source_id,
            "expected_content_hash",
            line_number,
        )


def _validate_conditional_fields(
    row: dict[str, str],
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    inclusion_status = _row_text(row, "inclusion_status")
    usage_status = _row_text(row, "usage_status")

    if inclusion_status == "included":
        for field in ["source_url", "access_date", "inclusion_reason"]:
            if not _row_text(row, field):
                _add_import_blocker(
                    result,
                    f"missing_{field}",
                    f"included rows must include {field}.",
                    source_id,
                    field,
                    line_number,
                )
        if usage_status not in APPROVED_FULL_TEXT_STATUSES:
            _add_import_blocker(
                result,
                "usage_status_not_importable",
                f"usage_status '{usage_status or 'unspecified'}' does not permit full-text import.",
                source_id,
                "usage_status",
                line_number,
            )

    if usage_status == "approved_open_access":
        if not _row_text(row, "license_type"):
            _add_import_blocker(
                result,
                "missing_license_type",
                "approved_open_access rows must include license_type.",
                source_id,
                "license_type",
                line_number,
            )
        if not _row_text(row, "license_url"):
            _add_import_blocker(
                result,
                "missing_license_url",
                "approved_open_access rows must include license_url.",
                source_id,
                "license_url",
                line_number,
            )


def _validate_local_file(
    row: dict[str, str],
    result: CorpusValidationResult,
    papers_dir: Path | None,
    root: Path,
    check_files: bool,
    source_id: str,
    line_number: int,
) -> None:
    local_path = _row_text(row, "local_path")
    usage_status = _row_text(row, "usage_status")
    inclusion_status = _row_text(row, "inclusion_status")
    needs_file = inclusion_status == "included" and usage_status in APPROVED_FULL_TEXT_STATUSES

    if not local_path:
        if check_files and needs_file:
            result.file_counts.missing += 1
            _add_import_blocker(
                result,
                "missing_local_path",
                "included full-text rows require local_path when --check-files is used.",
                source_id,
                "local_path",
                line_number,
            )
        elif not check_files:
            result.file_counts.not_checked += 1
        return

    path = Path(local_path)
    configured_prefix = _display_path(papers_dir, root) if papers_dir else ""
    if _looks_absolute(path):
        _add_row_error(
            result,
            "absolute_path",
            "local_path must be relative to default_local_papers_directory.",
            source_id,
            "local_path",
            line_number,
        )
        result.file_counts.invalid += 1
        return
    if _has_traversal(path):
        _add_row_error(
            result,
            "path_traversal",
            "local_path must not contain '..'.",
            source_id,
            "local_path",
            line_number,
        )
        result.file_counts.invalid += 1
        return
    if configured_prefix and local_path.replace("\\", "/").startswith(
        configured_prefix.replace("\\", "/").rstrip("/") + "/"
    ):
        _add_row_error(
            result,
            "repeated_papers_directory",
            "local_path must not repeat default_local_papers_directory.",
            source_id,
            "local_path",
            line_number,
        )
        result.file_counts.invalid += 1
        return
    if papers_dir is None:
        result.file_counts.invalid += 1
        return

    resolved = _resolve_under(papers_dir, path)
    if not _is_relative_to(resolved, papers_dir.resolve(strict=False)):
        _add_row_error(
            result,
            "path_escape",
            "local_path escapes default_local_papers_directory.",
            source_id,
            "local_path",
            line_number,
        )
        result.file_counts.invalid += 1
        return

    if not check_files:
        result.file_counts.not_checked += 1
        return

    if not needs_file:
        result.file_counts.not_checked += 1
        return
    if not resolved.exists():
        result.file_counts.missing += 1
        _add_import_blocker(
            result,
            "local_file_missing",
            f"Local file is missing: {local_path}.",
            source_id,
            "local_path",
            line_number,
        )
        return
    if not resolved.is_file():
        result.file_counts.invalid += 1
        _add_import_blocker(
            result,
            "local_file_not_file",
            f"Local path is not a regular file: {local_path}.",
            source_id,
            "local_path",
            line_number,
        )
        return
    if resolved.suffix.lower() != PDF_SUFFIX:
        result.file_counts.invalid += 1
        _add_import_blocker(
            result,
            "unsupported_file_type",
            "Only .pdf files are supported for Phase 1 local file readiness.",
            source_id,
            "local_path",
            line_number,
        )
        return
    result.file_counts.present += 1


def _finalize_valid_rows(result: CorpusValidationResult) -> CorpusValidationResult:
    invalid_lines = {issue.line_number for issue in result.structural_errors if issue.line_number}
    result.valid_source_rows = max(result.total_source_rows - len(invalid_lines), 0)
    result.issues.sort(
        key=lambda issue: (
            issue.line_number or 0,
            issue.source_id or "",
            issue.category,
            issue.severity,
            issue.code,
            issue.field or "",
        )
    )
    return result


def _require_row_text(
    row: dict[str, str],
    field: str,
    result: CorpusValidationResult,
    source_id: str,
    line_number: int,
) -> None:
    if not _row_text(row, field):
        _add_row_error(
            result,
            f"empty_{field}",
            f"{field} must not be empty.",
            source_id,
            field,
            line_number,
        )


def _add_manifest_error(
    result: CorpusValidationResult,
    code: str,
    message: str,
    field: str | None = None,
    line_number: int | None = None,
) -> None:
    result.issues.append(
        Issue(
            code=code,
            severity=IssueSeverity.ERROR,
            category="manifest",
            message=message,
            field=field,
            line_number=line_number,
            blocks_manifest=True,
        )
    )


def _add_row_error(
    result: CorpusValidationResult,
    code: str,
    message: str,
    source_id: str,
    field: str,
    line_number: int,
) -> None:
    result.issues.append(
        Issue(
            code=code,
            severity=IssueSeverity.ERROR,
            category="source",
            message=message,
            source_id=source_id or None,
            field=field,
            line_number=line_number,
            blocks_manifest=True,
        )
    )


def _add_import_blocker(
    result: CorpusValidationResult,
    code: str,
    message: str,
    source_id: str,
    field: str,
    line_number: int,
) -> None:
    result.issues.append(
        Issue(
            code=code,
            severity=IssueSeverity.ERROR,
            category="import-readiness",
            message=message,
            source_id=source_id or None,
            field=field,
            line_number=line_number,
            blocks_import=True,
        )
    )


def _add_row_warning(
    result: CorpusValidationResult,
    code: str,
    message: str,
    source_id: str,
    field: str,
    line_number: int,
) -> None:
    result.issues.append(
        Issue(
            code=code,
            severity=IssueSeverity.WARNING,
            category="source",
            message=message,
            source_id=source_id or None,
            field=field,
            line_number=line_number,
        )
    )


def _row_text(row: dict[str, str], field: str) -> str:
    return (row.get(field) or "").strip()


def _optional_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_iso_date_or_datetime(value: str) -> bool:
    candidate = value.replace("Z", "+00:00")
    if not DATE_PREFIX_RE.match(candidate):
        return False
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _has_traversal(path: Path) -> bool:
    return any(part == ".." for part in path.parts)


def _looks_absolute(path: Path) -> bool:
    raw = str(path)
    return path.is_absolute() or raw.startswith(("/", "\\")) or bool(re.match(r"^[A-Za-z]:", raw))


def _resolve_under(base: Path, path: Path) -> Path:
    candidate = base / path
    try:
        return candidate.resolve(strict=True)
    except FileNotFoundError:
        return candidate.resolve(strict=False)


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _display_path(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve(strict=False).relative_to(root).as_posix()
    except ValueError:
        return path.name


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)
