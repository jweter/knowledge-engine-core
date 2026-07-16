"""Pure CLI option resolution for fresh, resume, and retry corpus imports."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge_engine.import_runs.resume import RunMode


@dataclass(frozen=True)
class CorpusImportMode:
    """Resolved import mode selected from mutually exclusive CLI options."""

    mode: RunMode | None
    parent_import_run_id: str | None

    @property
    def is_linked(self) -> bool:
        """Return whether this request creates a run linked to a parent."""

        return self.mode is not None


def resolve_corpus_import_mode(
    *,
    resume_from: str | None,
    retry_failed_from: str | None,
) -> CorpusImportMode:
    """Resolve mutually exclusive CLI parent-run options deterministically."""

    resume_id = _normalized_run_id(resume_from)
    retry_id = _normalized_run_id(retry_failed_from)
    if resume_id is not None and retry_id is not None:
        raise ValueError("--resume-from and --retry-failed-from are mutually exclusive.")
    if resume_id is not None:
        return CorpusImportMode(mode="resume", parent_import_run_id=resume_id)
    if retry_id is not None:
        return CorpusImportMode(mode="retry_failed", parent_import_run_id=retry_id)
    return CorpusImportMode(mode=None, parent_import_run_id=None)


def _normalized_run_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("Import run identifiers must not be empty.")
    return normalized
