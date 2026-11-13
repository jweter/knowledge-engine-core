"""Export the ``ke-online-evidence/v1`` contract artifacts for consumer repos.

``knowledge-engine-ai`` and ``knowledge-engine-web`` each need Core's exact current golden
bundle fixture (``tests/fixtures/online_evidence/``) and formal JSON Schema
(``docs/schemas/online_evidence_v1.schema.json``) in their own contract-test suites. Until now
that meant an undocumented hand copy of files out of this repository, which can silently drift
from Core's own committed copies the next time either changes here. This module -- and the
``ke online-evidence-export-contract`` command built on it -- writes the exact same bytes
``knowledge_engine.online_golden.write_golden_fixture`` and
``knowledge_engine.online_evidence_schema.render_schema`` already produce for Core's own
committed fixture and schema, so a consumer repo can refresh its fixtures from a single
deterministic call and detect drift instead of hand-copying them.
"""

from __future__ import annotations

from pathlib import Path

from knowledge_engine.online_evidence_schema import render_schema
from knowledge_engine.online_golden import write_golden_fixture

SCHEMA_FILE_NAME = "online_evidence_v1.schema.json"


class OnlineEvidenceExportError(Exception):
    """Raised when the online-evidence contract cannot be exported as requested."""


def export_online_evidence_contract(directory: Path, *, force: bool = False) -> None:
    """Write the golden bundle, its ``contents/`` texts and the JSON Schema into ``directory``.

    Creates ``directory`` (and any missing parents) if it does not already exist. Refuses to
    write into an existing, non-empty directory unless ``force`` is True, so a caller never
    silently loses whatever it already had there.
    """

    if directory.is_symlink():
        raise OnlineEvidenceExportError("Export directory must not be a symbolic link.")
    if directory.exists():
        if not directory.is_dir():
            raise OnlineEvidenceExportError("Export path exists and is not a directory.")
        if not force and any(directory.iterdir()):
            raise OnlineEvidenceExportError(
                "Export directory already exists and is not empty. Use --force to overwrite."
            )
    else:
        directory.mkdir(parents=True)

    write_golden_fixture(directory)
    (directory / SCHEMA_FILE_NAME).write_text(render_schema(), encoding="utf-8")


__all__ = [
    "SCHEMA_FILE_NAME",
    "OnlineEvidenceExportError",
    "export_online_evidence_contract",
]
