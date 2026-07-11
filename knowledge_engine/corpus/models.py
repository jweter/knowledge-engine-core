"""Typed result models for corpus manifest validation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum


class IssueSeverity(StrEnum):
    """Severity of a corpus validation issue."""

    ERROR = "error"
    WARNING = "warning"


class ValidityState(StrEnum):
    """Structural manifest validity."""

    VALID = "valid"
    INVALID = "invalid"


class ReadinessState(StrEnum):
    """Whether a structurally valid manifest is ready for a future import."""

    READY = "ready"
    BLOCKED = "blocked"
    NOT_EVALUATED = "not evaluated"


@dataclass(frozen=True)
class Issue:
    """A deterministic validation message with optional source-row context."""

    code: str
    severity: IssueSeverity
    category: str
    message: str
    source_id: str | None = None
    field: str | None = None
    line_number: int | None = None
    blocks_manifest: bool = False
    blocks_import: bool = False


@dataclass
class FileCounts:
    """Local file-readiness counts."""

    present: int = 0
    missing: int = 0
    invalid: int = 0
    not_checked: int = 0


@dataclass
class CorpusValidationResult:
    """Complete corpus validation result for CLI display and tests."""

    corpus_name: str | None = None
    corpus_id: str | None = None
    manifest_version: int | None = None
    source_manifest_path: str | None = None
    total_source_rows: int = 0
    valid_source_rows: int = 0
    usage_status_counts: Counter[str] = field(default_factory=Counter)
    inclusion_status_counts: Counter[str] = field(default_factory=Counter)
    file_counts: FileCounts = field(default_factory=FileCounts)
    issues: list[Issue] = field(default_factory=list)
    check_files: bool = False

    @property
    def structural_errors(self) -> list[Issue]:
        """Return issues that make the manifest structurally invalid."""

        return [issue for issue in self.issues if issue.blocks_manifest]

    @property
    def import_blockers(self) -> list[Issue]:
        """Return issues that block a future import."""

        return [issue for issue in self.issues if issue.blocks_import]

    @property
    def warnings(self) -> list[Issue]:
        """Return non-blocking warnings."""

        return [issue for issue in self.issues if issue.severity == IssueSeverity.WARNING]

    @property
    def manifest_validity(self) -> ValidityState:
        """Return structural validity."""

        if self.structural_errors:
            return ValidityState.INVALID
        return ValidityState.VALID

    @property
    def import_readiness(self) -> ReadinessState:
        """Return import readiness using the M7 validation-only contract."""

        if self.structural_errors or self.import_blockers:
            return ReadinessState.BLOCKED
        if not self.check_files:
            return ReadinessState.NOT_EVALUATED
        return ReadinessState.READY

    @property
    def warning_count(self) -> int:
        """Return warning count."""

        return len(self.warnings)

    @property
    def structural_error_count(self) -> int:
        """Return structural error count."""

        return len(self.structural_errors)

    @property
    def import_blocker_count(self) -> int:
        """Return import blocker count."""

        return len(self.import_blockers)
