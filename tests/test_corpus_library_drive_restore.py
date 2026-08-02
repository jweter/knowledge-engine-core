from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import export_corpus_library_compressed
from knowledge_engine.corpus_library_drive_restore import (
    CorpusLibraryDriveRestoreError,
    run_corpus_library_drive_restore,
)
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.drive_adapter import DriveAdapterError, DriveFileMetadata, DriveFolderMetadata
from knowledge_engine.drive_boundary import DRIVE_FOLDER_IDS, KNOWLEDGE_ENGINE_DRIVE_ROOT_ID
from knowledge_engine.models import Paper
from knowledge_engine.parser import ParsedPage, ParsedPaper

_DESTINATION_FOLDER_ID = DRIVE_FOLDER_IDS["corpus_library.snapshot"]


class FakeCorpusLibraryRestoreTransport:
    def __init__(self, *, files: list[DriveFileMetadata] | None = None) -> None:
        self.files = list(files or [])
        self.downloads: dict[str, bytes] = {}
        self.downloaded_file_ids: list[str] = []

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return DriveFolderMetadata(folder_id, (KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,), True)

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]:
        assert folder_id == _DESTINATION_FOLDER_ID
        return self.files

    def download_bytes(self, file_id: str) -> bytes:
        self.downloaded_file_ids.append(file_id)
        return self.downloads[file_id]

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        raise AssertionError("restore never uploads")

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        raise AssertionError("restore never re-fetches upload metadata")


def _empty_database(tmp_path: Path, name: str) -> Path:
    db_path = tmp_path / name
    database = Database(Settings(project_root=tmp_path, database_url=f"sqlite:///{db_path}"))
    database.initialize()
    return db_path


def _snapshot_with_one_paper(tmp_path: Path) -> bytes:
    source_db = tmp_path / "source.sqlite3"
    database = Database(Settings(project_root=tmp_path, database_url=f"sqlite:///{source_db}"))
    database.initialize()
    text = "Results\n\nBody weight decreased by 10%."
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(
            ParsedPaper(
                source_path=tmp_path / "a.pdf",
                content_hash="a" * 64,
                title="A Trial",
                authors=["Ada Scientist"],
                abstract="An abstract.",
                doi="10.1/a",
                page_count=1,
                word_count=10,
                raw_text=text,
                body_text=text,
                pages=[ParsedPage(page_number=1, text=text)],
            ),
            keywords=["obesity"],
        )
    database.engine.dispose()

    snapshot_path = tmp_path / "snapshot.sqlite3.gz"
    export_corpus_library_compressed(database.engine, snapshot_path)
    return snapshot_path.read_bytes()


def _file_metadata(*, file_id: str, payload: bytes, created_time: str) -> DriveFileMetadata:
    return DriveFileMetadata(
        file_id=file_id,
        name="corpus_library_snapshot.sqlite3.gz",
        parent_ids=(_DESTINATION_FOLDER_ID,),
        byte_count=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        created_time=created_time,
    )


def test_no_snapshot_when_folder_is_empty(tmp_path: Path) -> None:
    target_db = _empty_database(tmp_path, "target.sqlite3")
    transport = FakeCorpusLibraryRestoreTransport()

    result = run_corpus_library_drive_restore(
        target_database=target_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )

    assert result.status == "no_snapshot"
    assert transport.downloaded_file_ids == []


def test_downloads_and_imports_newest_snapshot(tmp_path: Path) -> None:
    target_db = _empty_database(tmp_path, "target.sqlite3")
    payload = _snapshot_with_one_paper(tmp_path)
    older_payload = b"stale gzip bytes"
    transport = FakeCorpusLibraryRestoreTransport(
        files=[
            _file_metadata(
                file_id="old-1", payload=older_payload, created_time="2026-01-01T00:00:00.000Z"
            ),
            _file_metadata(
                file_id="new-1", payload=payload, created_time="2026-08-02T21:15:23.864Z"
            ),
        ]
    )
    transport.downloads = {"old-1": older_payload, "new-1": payload}

    result = run_corpus_library_drive_restore(
        target_database=target_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )

    assert result.status == "imported"
    assert result.file_id == "new-1"
    assert transport.downloaded_file_ids == ["new-1"]
    assert result.import_summary is not None
    assert result.import_summary.imported_paper_count == 1
    assert result.import_summary.skipped_existing_paper_count == 0

    check_database = Database(
        Settings(project_root=tmp_path, database_url=f"sqlite:///{target_db}")
    )
    with check_database.session() as session:
        titles = session.scalars(select(Paper.title)).all()
    check_database.engine.dispose()
    assert titles == ["A Trial"]

    marker_path = tmp_path / "output" / "last_imported.sha256"
    assert marker_path.read_text(encoding="utf-8").strip() == result.sha256


def test_second_run_skips_when_marker_matches(tmp_path: Path) -> None:
    target_db = _empty_database(tmp_path, "target.sqlite3")
    payload = _snapshot_with_one_paper(tmp_path)
    transport = FakeCorpusLibraryRestoreTransport(
        files=[
            _file_metadata(
                file_id="new-1", payload=payload, created_time="2026-08-02T21:15:23.864Z"
            )
        ]
    )
    transport.downloads = {"new-1": payload}

    first = run_corpus_library_drive_restore(
        target_database=target_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )
    assert first.status == "imported"

    second = run_corpus_library_drive_restore(
        target_database=target_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )

    assert second.status == "already_up_to_date"
    assert second.file_id == "new-1"
    assert transport.downloaded_file_ids == ["new-1"]


def test_raises_when_destination_ancestry_is_invalid(tmp_path: Path) -> None:
    target_db = _empty_database(tmp_path, "target.sqlite3")

    class UnrelatedFolderTransport(FakeCorpusLibraryRestoreTransport):
        def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
            return DriveFolderMetadata(folder_id, ("some-unrelated-root",), True)

    with pytest.raises(DriveAdapterError):
        run_corpus_library_drive_restore(
            target_database=target_db,
            output_directory=tmp_path / "output",
            transport=UnrelatedFolderTransport(),
        )


def test_raises_when_downloaded_bytes_do_not_match_recorded_hash(tmp_path: Path) -> None:
    target_db = _empty_database(tmp_path, "target.sqlite3")
    payload = _snapshot_with_one_paper(tmp_path)
    transport = FakeCorpusLibraryRestoreTransport(
        files=[
            _file_metadata(
                file_id="new-1", payload=payload, created_time="2026-08-02T21:15:23.864Z"
            )
        ]
    )
    transport.downloads = {"new-1": b"corrupted bytes, does not match recorded sha256"}

    with pytest.raises(CorpusLibraryDriveRestoreError):
        run_corpus_library_drive_restore(
            target_database=target_db,
            output_directory=tmp_path / "output",
            transport=transport,
        )
