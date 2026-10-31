"""The local vector index is an optional capability (owner decision 2026-10-30).

Importing the CLI and the research runtime must not load the vector stack, and a
vector command run without it must fail with a clear message instead of an
ImportError at startup.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.parser import ParsedPage, ParsedPaper
from knowledge_engine.research_runtime_packaging import VECTOR_ONLY_DEPENDENCIES
from knowledge_engine.vector_search import FaissVectorIndex
from knowledge_engine.vector_search.index import VectorCapabilityUnavailable
from knowledge_engine.vector_search.qdrant_index import QdrantVectorIndex

REPO_ROOT = Path(__file__).resolve().parents[1]
VECTOR_STACK = ("faiss", "qdrant_client", "sentence_transformers", "torch")


def test_importing_the_cli_and_research_runtime_loads_no_vector_package() -> None:
    probe = (
        "import json, sys\n"
        "import knowledge_engine.entrypoint, knowledge_engine.command_surface\n"
        "import knowledge_engine.research_runtime\n"
        f"print(json.dumps(sorted(m for m in {VECTOR_STACK!r} if m in sys.modules)))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(completed.stdout.strip().splitlines()[-1]) == []


def test_faiss_index_without_faiss_reports_the_optional_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "faiss", None)

    with pytest.raises(VectorCapabilityUnavailable, match="poetry install --extras vector"):
        FaissVectorIndex(2)


def test_qdrant_index_without_qdrant_client_reports_the_optional_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "qdrant_client", None)

    with pytest.raises(VectorCapabilityUnavailable, match="qdrant-client is missing"):
        QdrantVectorIndex(
            dimension=2,
            collection_name="papers",
            embedding_model="external:test-v1",
            url="http://localhost:6333",
        )


def test_embedding_index_build_without_faiss_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "source",
            database_url=f"sqlite:///{tmp_path / 'source'}.sqlite3",
        )
    )
    database.initialize()
    text = "Results\n\nBody weight decreased by 10%."
    with database.session() as session:
        paper = PaperRepository(session).add_parsed_paper(
            ParsedPaper(
                source_path=tmp_path / "a.pdf",
                content_hash="a" * 64,
                title="A Trial",
                authors=["Ada Scientist"],
                abstract="An abstract.",
                doi="10.1/aaaaaaaa",
                page_count=1,
                word_count=10,
                raw_text=text,
                body_text=text,
                pages=[ParsedPage(page_number=1, text=text)],
            )
        )
        paper_id = paper.id
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setitem(sys.modules, "faiss", None)
    vectors = tmp_path / "vectors.jsonl"
    vectors.write_text(
        json.dumps({"paper_id": paper_id, "vector": [1.0, 0.0], "embedding_model": "external:t"})
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        ["embedding-index-build", "--vectors", str(vectors), "--index-path", str(tmp_path / "i")],
    )

    assert result.exit_code == 1, result.output
    assert "optional vector capability is not installed" in " ".join(result.output.split())
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_the_vector_stack_is_exactly_the_optional_vector_extra() -> None:
    poetry = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "poetry"
    ]
    dependencies = poetry["dependencies"]

    assert set(poetry["extras"]["vector"]) == VECTOR_ONLY_DEPENDENCIES
    for name in VECTOR_ONLY_DEPENDENCIES:
        declaration = dependencies[name]
        assert isinstance(declaration, dict) and declaration.get("optional") is True, name


def test_the_locked_vector_extra_installs_only_cpu_torch() -> None:
    # A multi-constraint optional torch once locked a second, CUDA-enabled PyPI torch for
    # Linux/Windows next to the pytorch-cpu build; the lock must hold only the CPU build.
    packages = tomllib.loads((REPO_ROOT / "poetry.lock").read_text(encoding="utf-8"))["package"]
    torches = [package for package in packages if package["name"] == "torch"]

    assert torches and all(package["version"].endswith("+cpu") for package in torches)
    assert all(package.get("optional") is True for package in torches)
    assert not [p["name"] for p in packages if p["name"].startswith(("nvidia-", "triton"))]
