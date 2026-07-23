from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from knowledge_engine.corpus_pdf_backup import CorpusPdfBackupError, run_corpus_pdf_backup
from knowledge_engine.drive_adapter import DriveAdapterError, DriveFileMetadata, DriveFolderMetadata
from knowledge_engine.drive_boundary import DRIVE_FOLDER_IDS, KNOWLEDGE_ENGINE_DRIVE_ROOT_ID

_DESTINATION_FOLDER_ID = DRIVE_FOLDER_IDS["source_documents.pdf"]


class FakeCorpusPdfTransport:
    def __init__(
        self,
        *,
        existing_files: list[DriveFileMetadata] | None = None,
        fail_names: set[str] | None = None,
    ) -> None:
        self.existing_files = list(existing_files or [])
        self.fail_names = fail_names or set()
        self.uploaded: dict[str, bytes] = {}
        self._next_id = 1

    def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
        return DriveFolderMetadata(folder_id, (KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,), True)

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]:
        assert folder_id == _DESTINATION_FOLDER_ID
        return self.existing_files

    def upload_bytes(self, *, parent_folder_id: str, name: str, payload: bytes) -> str:
        if name in self.fail_names:
            raise RuntimeError("simulated upload failure")
        file_id = f"file-{self._next_id}"
        self._next_id += 1
        self.uploaded[file_id] = payload
        self._last_upload = (file_id, name, parent_folder_id, payload)
        return file_id

    def get_file_metadata(self, file_id: str) -> DriveFileMetadata:
        stored_id, name, parent_folder_id, payload = self._last_upload
        assert stored_id == file_id
        return DriveFileMetadata(
            file_id=file_id,
            name=name,
            parent_ids=(parent_folder_id,),
            byte_count=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
        )


def _write_pdf(directory: Path, name: str, content: bytes) -> Path:
    path = directory / name
    path.write_bytes(content)
    return path


def test_uploads_new_files_and_skips_matching_hash(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    unchanged_payload = b"already backed up"
    _write_pdf(papers_dir, "unchanged.pdf", unchanged_payload)
    _write_pdf(papers_dir, "new.pdf", b"new content")

    transport = FakeCorpusPdfTransport(
        existing_files=[
            DriveFileMetadata(
                file_id="existing-1",
                name="unchanged.pdf",
                parent_ids=(_DESTINATION_FOLDER_ID,),
                byte_count=len(unchanged_payload),
                sha256=hashlib.sha256(unchanged_payload).hexdigest(),
            )
        ]
    )

    summary = run_corpus_pdf_backup(papers_dir=papers_dir, transport=transport)

    assert summary.uploaded == ("new.pdf",)
    assert summary.skipped_unchanged == ("unchanged.pdf",)
    assert summary.failed == ()


def test_matches_pdf_suffix_case_insensitively_and_ignores_other_files(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    _write_pdf(papers_dir, "uppercase.PDF", b"uppercase suffix")
    _write_pdf(papers_dir, "mixed.Pdf", b"mixed-case suffix")
    (papers_dir / "notes.txt").write_bytes(b"not a pdf")

    transport = FakeCorpusPdfTransport()

    summary = run_corpus_pdf_backup(papers_dir=papers_dir, transport=transport)

    assert set(summary.uploaded) == {"uppercase.PDF", "mixed.Pdf"}


def test_reuploads_when_local_content_changed(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    _write_pdf(papers_dir, "changed.pdf", b"new bytes on disk")

    transport = FakeCorpusPdfTransport(
        existing_files=[
            DriveFileMetadata(
                file_id="existing-1",
                name="changed.pdf",
                parent_ids=(_DESTINATION_FOLDER_ID,),
                byte_count=9,
                sha256=hashlib.sha256(b"old bytes").hexdigest(),
            )
        ]
    )

    summary = run_corpus_pdf_backup(papers_dir=papers_dir, transport=transport)

    assert summary.uploaded == ("changed.pdf",)
    assert summary.skipped_unchanged == ()


def test_records_failed_uploads_and_continues(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    _write_pdf(papers_dir, "a.pdf", b"a")
    _write_pdf(papers_dir, "b.pdf", b"b")

    transport = FakeCorpusPdfTransport(fail_names={"a.pdf"})

    summary = run_corpus_pdf_backup(papers_dir=papers_dir, transport=transport)

    assert summary.uploaded == ("b.pdf",)
    assert [name for name, _reason in summary.failed] == ["a.pdf"]


def test_raises_when_papers_dir_missing(tmp_path: Path) -> None:
    transport = FakeCorpusPdfTransport()

    with pytest.raises(CorpusPdfBackupError):
        run_corpus_pdf_backup(papers_dir=tmp_path / "missing", transport=transport)


def test_raises_when_no_local_pdfs(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    transport = FakeCorpusPdfTransport()

    with pytest.raises(CorpusPdfBackupError):
        run_corpus_pdf_backup(papers_dir=papers_dir, transport=transport)


def test_raises_when_destination_ancestry_is_invalid(tmp_path: Path) -> None:
    papers_dir = tmp_path / "papers"
    papers_dir.mkdir()
    _write_pdf(papers_dir, "a.pdf", b"a")

    class UnrelatedFolderTransport(FakeCorpusPdfTransport):
        def get_folder_metadata(self, folder_id: str) -> DriveFolderMetadata:
            return DriveFolderMetadata(folder_id, ("some-unrelated-root",), True)

    with pytest.raises(DriveAdapterError):
        run_corpus_pdf_backup(papers_dir=papers_dir, transport=UnrelatedFolderTransport())
