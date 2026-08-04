from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library_drive_backup import (
    CorpusLibraryDriveBackupError,
    run_corpus_library_drive_backup,
)
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.drive_adapter import DriveAdapterError, DriveFileMetadata, DriveFolderMetadata
from knowledge_engine.drive_boundary import DRIVE_FOLDER_IDS, KNOWLEDGE_ENGINE_DRIVE_ROOT_ID
from knowledge_engine.parser import ParsedPage, ParsedPaper

_DESTINATION_FOLDER_ID = DRIVE_FOLDER_IDS["corpus_library.snapshot"]


class FakeCorpusLibraryTransport:
    def __init__(self, *, existing_files: list[DriveFileMetadata] | None = None) -> None:
        self.existing_files = list(existing_files or [])
        self.uploaded: dict[str, bytes] = {}
        self._next_id = 1
        self._last_upload: tuple[str, str, str, bytes] | None = None

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return DriveFolderMetadata(folder_id, (KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,), True)

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]:
        assert folder_id == _DESTINATION_FOLDER_ID
        return self.existing_files

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        file_id = f"file-{self._next_id}"
        self._next_id += 1
        self.uploaded[file_id] = payload
        self._last_upload = (file_id, name, parent_folder_id, payload)
        return file_id

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        assert self._last_upload is not None
        stored_id, name, parent_folder_id, payload = self._last_upload
        assert stored_id == file_id
        return DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )


def _source_database_with_one_paper(tmp_path: Path) -> Path:
    db_path = tmp_path / "source.sqlite3"
    database = Database(Settings(project_root=tmp_path, database_url=f"sqlite:///{db_path}"))
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
    return db_path


def test_uploads_new_snapshot(tmp_path: Path) -> None:
    source_db = _source_database_with_one_paper(tmp_path)
    transport = FakeCorpusLibraryTransport()

    file_id = run_corpus_library_drive_backup(
        source_database=source_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )

    assert file_id is not None
    assert file_id in transport.uploaded


def test_skips_upload_when_snapshot_hash_matches_existing(tmp_path: Path) -> None:
    source_db = _source_database_with_one_paper(tmp_path)

    # First run establishes the real snapshot bytes/hash to reuse below,
    # rather than hardcoding a brittle expected gzip byte sequence.
    probe_transport = FakeCorpusLibraryTransport()
    run_corpus_library_drive_backup(
        source_database=source_db,
        output_directory=tmp_path / "probe",
        transport=probe_transport,
    )
    uploaded_payload = next(iter(probe_transport.uploaded.values()))
    existing_hash = hashlib.sha256(uploaded_payload).hexdigest()

    # Cross SQLite's one-second CURRENT_TIMESTAMP resolution. The second
    # export must remain byte-identical rather than regenerating row timestamps.
    time.sleep(1.1)

    transport = FakeCorpusLibraryTransport(
        existing_files=[
            DriveFileMetadata(
                file_id="existing-1",
                name="corpus_library_snapshot.sqlite3.gz",
                parent_ids=(_DESTINATION_FOLDER_ID,),
                byte_count=len(uploaded_payload),
                sha256=existing_hash,
            )
        ]
    )

    file_id = run_corpus_library_drive_backup(
        source_database=source_db,
        output_directory=tmp_path / "output",
        transport=transport,
    )

    assert file_id is None
    assert transport.uploaded == {}


def test_raises_when_destination_ancestry_is_invalid(tmp_path: Path) -> None:
    source_db = _source_database_with_one_paper(tmp_path)

    class UnrelatedFolderTransport(FakeCorpusLibraryTransport):
        def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
            return DriveFolderMetadata(folder_id, ("some-unrelated-root",), True)

    with pytest.raises(DriveAdapterError):
        run_corpus_library_drive_backup(
            source_database=source_db,
            output_directory=tmp_path / "output",
            transport=UnrelatedFolderTransport(),
        )


def test_raises_when_source_database_missing(tmp_path: Path) -> None:
    transport = FakeCorpusLibraryTransport()

    with pytest.raises(CorpusLibraryDriveBackupError):
        run_corpus_library_drive_backup(
            source_database=tmp_path / "does-not-exist.sqlite3",
            output_directory=tmp_path / "output",
            transport=transport,
        )
