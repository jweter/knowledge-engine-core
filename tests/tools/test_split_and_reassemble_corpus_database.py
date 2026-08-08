from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

import pytest

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"


def _load_module(name: str, filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, _TOOLS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


split_mod = _load_module("split_corpus_database", "split_corpus_database.py")
reassemble_mod = _load_module("reassemble_corpus_database", "reassemble_corpus_database.py")


def _make_database(path: Path, *, paper_count: int = 3) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)")
        connection.executemany(
            "INSERT INTO papers (id, title) VALUES (?, ?)",
            [(i, f"Paper {i}") for i in range(paper_count)],
        )
        connection.commit()
    finally:
        connection.close()


def test_split_then_reassemble_round_trips_exactly(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)

    output_dir = tmp_path / "db_parts"
    split_manifest = split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )
    assert split_manifest.part_count >= 1
    assert (output_dir / "manifest.json").is_file()

    restored = tmp_path / "restored.sqlite3"
    reassemble_manifest = reassemble_mod.reassemble_database(parts_dir=output_dir, output=restored)

    assert reassemble_manifest.total_sha256 == split_manifest.total_sha256
    assert hashlib.sha256(restored.read_bytes()).hexdigest() == split_manifest.total_sha256

    connection = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
    try:
        rows = connection.execute("SELECT COUNT(*) FROM papers").fetchone()
    finally:
        connection.close()
    assert rows[0] == 3


def test_split_produces_parts_no_larger_than_requested(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database, paper_count=50)

    output_dir = tmp_path / "db_parts"
    manifest = split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=512,
    )

    assert manifest.part_count > 1
    for part in manifest.parts:
        assert part.byte_count <= 512
        assert (output_dir / part.filename).stat().st_size == part.byte_count


def test_split_rejects_missing_database(tmp_path: Path) -> None:
    with pytest.raises(split_mod.SplitError, match="not found"):
        split_mod.split_database(
            database=tmp_path / "missing.sqlite3",
            output_dir=tmp_path / "out",
            production_commit="test-commit",
        )


def test_reassemble_rejects_tampered_part(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)
    output_dir = tmp_path / "db_parts"
    split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )

    first_part = next(iter(sorted(output_dir.glob("*.part*"))))
    tampered = bytearray(first_part.read_bytes())
    tampered[0] ^= 0xFF
    first_part.write_bytes(bytes(tampered))

    with pytest.raises(reassemble_mod.ReassembleError, match="SHA-256"):
        reassemble_mod.reassemble_database(
            parts_dir=output_dir, output=tmp_path / "restored.sqlite3"
        )


def test_reassemble_rejects_missing_part(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)
    output_dir = tmp_path / "db_parts"
    split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )

    first_part = next(iter(sorted(output_dir.glob("*.part*"))))
    first_part.unlink()

    with pytest.raises(reassemble_mod.ReassembleError, match="Missing part file"):
        reassemble_mod.reassemble_database(
            parts_dir=output_dir, output=tmp_path / "restored.sqlite3"
        )


def test_reassemble_refuses_to_clobber_mismatched_existing_output(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)
    output_dir = tmp_path / "db_parts"
    split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )

    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(b"unrelated existing content")

    with pytest.raises(reassemble_mod.ReassembleError, match="already exists"):
        reassemble_mod.reassemble_database(parts_dir=output_dir, output=restored)


def test_reassemble_is_a_no_op_when_output_already_matches(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)
    output_dir = tmp_path / "db_parts"
    split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )

    restored = tmp_path / "restored.sqlite3"
    reassemble_mod.reassemble_database(parts_dir=output_dir, output=restored)

    with pytest.raises(reassemble_mod.ReassembleError, match="already matches"):
        reassemble_mod.reassemble_database(parts_dir=output_dir, output=restored)


def test_reassemble_overwrite_flag_forces_rewrite(tmp_path: Path) -> None:
    database = tmp_path / "source.sqlite3"
    _make_database(database)
    output_dir = tmp_path / "db_parts"
    split_mod.split_database(
        database=database,
        output_dir=output_dir,
        production_commit="test-commit",
        part_size_bytes=64,
    )

    restored = tmp_path / "restored.sqlite3"
    restored.write_bytes(b"stale content")
    manifest = reassemble_mod.reassemble_database(
        parts_dir=output_dir, output=restored, overwrite=True
    )
    assert hashlib.sha256(restored.read_bytes()).hexdigest() == manifest.total_sha256
