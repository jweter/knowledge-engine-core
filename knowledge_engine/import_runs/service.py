"""Service layer for durable import-run validation attempts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from sqlalchemy.orm import Session

from knowledge_engine.corpus import CorpusValidationResult, Issue, validate_corpus_manifest
from knowledge_engine.corpus.validation import discover_project_root
from knowledge_engine.import_runs._helpers import new_uuid, utc_now
from knowledge_engine.import_runs.repository import ImportRunRepository
from knowledge_engine.models import ImportIssue, ImportItem, ImportRun, ManifestSnapshot

MAX_MANIFEST_INPUT_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class PersistedImportRun:
    """Service result for a persisted import-run attempt."""

    import_run_id: str
    run_status: str
    validation_result: CorpusValidationResult


class ImportRunService:
    """Create and inspect durable import-run validation attempts."""

    def __init__(self, session: Session, *, project_root: Path | None = None) -> None:
        self.session = session
        self.project_root = (project_root or discover_project_root()).resolve()
        self.repository = ImportRunRepository(session)

    def create_run(self, corpus_path: Path, *, check_files: bool = False) -> PersistedImportRun:
        """Validate a corpus manifest and persist the run, items, issues, and snapshot."""

        created_at = utc_now()
        validation_mode = "check_files" if check_files else "metadata_only"
        safe_corpus_path = _safe_relative_path(corpus_path, self.project_root)
        snapshot_inputs = _snapshot_inputs(corpus_path, self.project_root)
        validation_result = validate_corpus_manifest(
            corpus_path,
            check_files=check_files,
            project_root=self.project_root,
        )
        run_status = _run_status(validation_result)
        import_run_id = new_uuid()
        snapshot_id = new_uuid()
        snapshot = ManifestSnapshot(
            snapshot_id=snapshot_id,
            corpus_path=safe_corpus_path,
            source_manifest_path=snapshot_inputs.source_manifest_path,
            corpus_json_bytes=snapshot_inputs.corpus_json_bytes,
            source_csv_bytes=snapshot_inputs.source_csv_bytes,
            corpus_json_text=_decode_snapshot_text(snapshot_inputs.corpus_json_bytes),
            source_csv_text=(
                _decode_snapshot_text(snapshot_inputs.source_csv_bytes)
                if snapshot_inputs.source_csv_bytes is not None
                else None
            ),
            corpus_json_sha256=_digest(snapshot_inputs.corpus_json_bytes),
            source_csv_sha256=(
                _digest(snapshot_inputs.source_csv_bytes)
                if snapshot_inputs.source_csv_bytes is not None
                else None
            ),
            combined_sha256=_combined_snapshot_hash(
                snapshot_inputs.corpus_json_bytes,
                snapshot_inputs.source_csv_bytes,
                validation_result.manifest_version,
            ),
            captured_at=created_at,
        )
        run = ImportRun(
            import_run_id=import_run_id,
            corpus_id=validation_result.corpus_id,
            corpus_name=validation_result.corpus_name,
            manifest_version=validation_result.manifest_version,
            validation_mode=validation_mode,
            run_status=run_status,
            manifest_validity=validation_result.manifest_validity.value,
            import_readiness=validation_result.import_readiness.value,
            total_source_rows=validation_result.total_source_rows,
            valid_source_rows=validation_result.valid_source_rows,
            warning_count=validation_result.warning_count,
            structural_error_count=validation_result.structural_error_count,
            import_blocker_count=validation_result.import_blocker_count,
            created_at=created_at,
            completed_at=utc_now(),
            source_manifest_path=validation_result.source_manifest_path,
            license_policy_path=validation_result.license_policy_path,
            corpus_path=safe_corpus_path,
            parent_import_run_id=None,
            manifest_snapshot_id=snapshot_id,
        )
        items = _build_items(import_run_id, validation_result, created_at)
        issues = _build_issues(import_run_id, items, validation_result.issues, created_at)

        self.repository.add_snapshot(snapshot)
        self.repository.add_run(run)
        self.repository.add_items(items)
        self.repository.add_issues(issues)
        self.session.flush()
        self._verify_read_back(import_run_id, validation_result)
        return PersistedImportRun(
            import_run_id=import_run_id,
            run_status=run_status,
            validation_result=validation_result,
        )

    def get_run(self, import_run_id: str) -> ImportRun | None:
        """Return one persisted import run."""

        return self.repository.get_run(import_run_id)

    def list_runs(self) -> list[ImportRun]:
        """Return persisted import runs."""

        return self.repository.list_runs()

    def _verify_read_back(
        self,
        import_run_id: str,
        validation_result: CorpusValidationResult,
    ) -> None:
        run = self.repository.get_run(import_run_id)
        if run is None:
            msg = "Import run was not readable after persistence."
            raise RuntimeError(msg)
        if run.warning_count != sum(1 for issue in run.issues if issue.severity == "warning"):
            raise RuntimeError("Persisted warning count does not match persisted issues.")
        if run.structural_error_count != sum(1 for issue in run.issues if issue.blocks_manifest):
            raise RuntimeError("Persisted structural error count does not match persisted issues.")
        if run.import_blocker_count != sum(1 for issue in run.issues if issue.blocks_import):
            raise RuntimeError("Persisted import blocker count does not match persisted issues.")
        if len(run.items) != len(validation_result.source_rows):
            raise RuntimeError("Persisted import item count does not match source rows.")
        sequences = [issue.sequence for issue in run.issues]
        if sequences != sorted(sequences):
            raise RuntimeError("Persisted issue order is not deterministic.")
        if len({item.import_item_id for item in run.items}) != len(run.items):
            raise RuntimeError("Persisted import item IDs are not unique.")


@dataclass(frozen=True)
class _SnapshotInputs:
    corpus_json_bytes: bytes
    source_csv_bytes: bytes | None
    source_manifest_path: str | None


def _snapshot_inputs(corpus_path: Path, project_root: Path) -> _SnapshotInputs:
    corpus_bytes = _read_limited_manifest_input(corpus_path, "corpus JSON")
    source_manifest_path = _source_manifest_path(corpus_bytes)
    if source_manifest_path is None:
        return _SnapshotInputs(corpus_bytes, None, None)
    if Path(source_manifest_path).suffix.lower() != ".csv":
        return _SnapshotInputs(corpus_bytes, None, None)

    source_path = _safe_corpus_relative_path(corpus_path.parent, source_manifest_path)
    if source_path is None:
        return _SnapshotInputs(corpus_bytes, None, None)

    safe_source_path = _safe_relative_path(source_path, project_root)
    try:
        source_bytes = _read_limited_manifest_input(source_path, "source CSV")
    except OSError:
        source_bytes = None
    return _SnapshotInputs(corpus_bytes, source_bytes, safe_source_path)


def _read_limited_manifest_input(path: Path, label: str) -> bytes:
    size = path.stat().st_size
    if size > MAX_MANIFEST_INPUT_BYTES:
        msg = (
            f"{label} is too large to snapshot safely "
            f"({size} bytes; limit {MAX_MANIFEST_INPUT_BYTES} bytes)."
        )
        raise ValueError(msg)
    return path.read_bytes()


def _source_manifest_path(corpus_bytes: bytes) -> str | None:
    try:
        loaded = json.loads(corpus_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(loaded, dict):
        return None
    value = loaded.get("source_manifest")
    return value if isinstance(value, str) and value.strip() else None


def _safe_corpus_relative_path(corpus_dir: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    try:
        resolved_base = corpus_dir.resolve(strict=False)
        raw_combined = corpus_dir / candidate
        combined = raw_combined.resolve(strict=raw_combined.exists())
        combined.relative_to(resolved_base)
    except (OSError, ValueError):
        return None
    return combined


def _decode_snapshot_text(value: bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8-sig", errors="replace")


def _digest(value: bytes | None) -> str:
    return sha256(value or b"").hexdigest()


def _combined_snapshot_hash(
    corpus_bytes: bytes,
    source_csv_bytes: bytes | None,
    manifest_version: int | None,
) -> str:
    digest = sha256()
    version = str(manifest_version or "unknown").encode("utf-8")
    for label, value in [
        (b"manifest_version", version),
        (b"corpus_json", corpus_bytes),
        (
            b"source_csv:present" if source_csv_bytes is not None else b"source_csv:absent",
            source_csv_bytes or b"",
        ),
    ]:
        digest.update(label)
        digest.update(len(value).to_bytes(8, byteorder="big"))
        digest.update(value)
    return digest.hexdigest()


def _run_status(result: CorpusValidationResult) -> str:
    if result.structural_errors:
        return "validation_failed"
    if result.import_blockers:
        return "import_blocked"
    return "validated"


def _build_items(
    import_run_id: str,
    result: CorpusValidationResult,
    timestamp: str,
) -> list[ImportItem]:
    issues_by_line: dict[int, list[Issue]] = {}
    for issue in result.issues:
        if issue.line_number is not None:
            issues_by_line.setdefault(issue.line_number, []).append(issue)

    items: list[ImportItem] = []
    for row in result.source_rows:
        row_issues = issues_by_line.get(row.line_number, [])
        structural_count = sum(1 for issue in row_issues if issue.blocks_manifest)
        import_blocker_count = sum(1 for issue in row_issues if issue.blocks_import)
        warning_count = sum(1 for issue in row_issues if issue.severity.value == "warning")
        status = "valid"
        if structural_count:
            status = "invalid"
        elif import_blocker_count:
            status = "import_blocked"
        items.append(
            ImportItem(
                import_item_id=new_uuid(),
                import_run_id=import_run_id,
                source_id=row.source_id or None,
                csv_line_number=row.line_number,
                title=row.title or None,
                normalized_doi=row.normalized_doi or None,
                inclusion_status=row.inclusion_status or None,
                usage_status=row.usage_status or None,
                local_path=row.local_path or None,
                item_status=status,
                blocks_manifest=structural_count > 0,
                blocks_import=import_blocker_count > 0,
                warning_count=warning_count,
                structural_error_count=structural_count,
                import_blocker_count=import_blocker_count,
                created_at=timestamp,
                completed_at=timestamp,
            )
        )
    return items


def _build_issues(
    import_run_id: str,
    items: list[ImportItem],
    issues: list[Issue],
    timestamp: str,
) -> list[ImportIssue]:
    items_by_line = {item.csv_line_number: item.import_item_id for item in items}
    persisted: list[ImportIssue] = []
    for sequence, issue in enumerate(issues, start=1):
        item_id = items_by_line.get(issue.line_number)
        persisted.append(
            ImportIssue(
                issue_id=new_uuid(),
                import_run_id=import_run_id,
                import_item_id=item_id,
                code=issue.code,
                severity=issue.severity.value,
                category=issue.category,
                message=issue.message,
                source_id=issue.source_id,
                field=issue.field,
                csv_line_number=issue.line_number,
                blocks_manifest=issue.blocks_manifest,
                blocks_import=issue.blocks_import,
                sequence=sequence,
                created_at=timestamp,
            )
        )
    return persisted


def _safe_relative_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve(strict=False)
    try:
        return resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.name
