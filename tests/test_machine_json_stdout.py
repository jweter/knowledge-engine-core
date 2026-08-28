"""Regression tests for the production CLI's machine-readable stdout contract."""

from __future__ import annotations

import json
import subprocess
import sys


def test_production_command_surface_import_does_not_write_to_stdout() -> None:
    """Dependency deprecations must not corrupt JSON emitted by ``ke`` commands."""

    completed = subprocess.run(
        [sys.executable, "-c", "import knowledge_engine.command_surface"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == ""


def test_pymupdf_import_alias_does_not_write_to_stdout() -> None:
    """The supported PyMuPDF import path is silent and remains usable as ``fitz``."""

    code = (
        "import json; import pymupdf as fitz; print(json.dumps({'has_open': callable(fitz.open)}))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {"has_open": True}
