import json
from pathlib import Path

from knowledge_engine.config import Settings
from knowledge_engine.database import Database
from knowledge_engine.import_runs import ImportRunService
from knowledge_engine.models import ImportRun


def make_database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'knowledge.sqlite3'}",
        )
    )
    database.initialize()
    return database


def prepare_corpus_layout(
    tmp_path: Path,
    *,
    corpus_id: str = "test_corpus",
    create_license: bool = True,
) -> tuple[Path, Path]:
    (tmp_path / "knowledge_engine").mkdir(exist_ok=True)
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    corpus_dir = tmp_path / "data" / "corpora" / corpus_id
    corpus_dir.mkdir(parents=True, exist_ok=True)
    papers_dir = tmp_path / "papers" / "corpora" / corpus_id
    papers_dir.mkdir(parents=True, exist_ok=True)
    if create_license:
        (corpus_dir / "license_policy.md").write_text("# License\n", encoding="utf-8")
    return corpus_dir, papers_dir


def write_sources(
    path: Path,
    rows: list[dict[str, str]],
    *,
    header: list[str] | None = None,
) -> None:
    columns = header or [
        "source_id",
        "title",
        "publication_year",
        "doi",
        "usage_status",
        "inclusion_status",
        "source_url",
        "access_date",
        "inclusion_reason",
        "license_type",
        "license_url",
        "local_path",
    ]
    lines = [",".join(columns)]
    for row in rows:
        lines.append(",".join(row.get(name, "") for name in columns))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_corpus_manifest(path: Path, manifest: dict[str, object]) -> Path:
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def get_run(database: Database, run_id: str) -> ImportRun:
    with database.session() as session:
        run = ImportRunService(session, project_root=database.settings.project_root).get_run(run_id)
        assert run is not None
        return run
