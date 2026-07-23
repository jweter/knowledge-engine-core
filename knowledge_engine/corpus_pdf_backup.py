"""Skip-existing bulk backup of local corpus PDFs to the allowlisted Drive folder.

Uploads only local PDFs whose (filename, SHA-256) pair is not already present
in the `source_documents.pdf` Drive destination, so re-running after a
partial or interrupted prior run -- or after a fresh corpus-growth batch --
only transfers what is actually new. Reuses the existing
`ConstrainedDriveAdapter` for destination-ancestry verification and
upload-readback verification; never accepts an arbitrary destination folder
ID.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from knowledge_engine.drive_adapter import (
    ConstrainedDriveAdapter,
    DriveFileMetadata,
    DriveTransport,
)
from knowledge_engine.drive_boundary import resolve_drive_destination
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport
from knowledge_engine.google_drive_service_account import (
    load_service_account_key,
    mint_access_token,
)

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
_DESTINATION_NAME = "source_documents.pdf"


class CorpusPdfBackupError(RuntimeError):
    """Sanitized corpus PDF backup failure."""


class ListingDriveTransport(DriveTransport, Protocol):
    """Transport operations required by the corpus PDF backup, beyond plain uploads."""

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]: ...


@dataclass(frozen=True)
class CorpusPdfBackupSummary:
    """Outcome of one backup run, by local filename."""

    uploaded: tuple[str, ...]
    skipped_unchanged: tuple[str, ...]
    failed: tuple[tuple[str, str], ...]


def run_corpus_pdf_backup(
    *,
    papers_dir: Path,
    transport: ListingDriveTransport,
) -> CorpusPdfBackupSummary:
    """Upload every local PDF not already present in Drive with a matching hash."""

    if not papers_dir.is_dir():
        raise CorpusPdfBackupError("Local papers directory is unavailable.")

    destination = resolve_drive_destination(_DESTINATION_NAME)
    adapter = ConstrainedDriveAdapter(transport)
    adapter.verify_destination(destination)

    existing_by_name_hash = {
        (entry.name, entry.sha256.casefold())
        for entry in transport.list_files(destination.folder_id)
        if entry.sha256
    }

    local_pdfs = sorted(
        path for path in papers_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"
    )
    if not local_pdfs:
        raise CorpusPdfBackupError("No local PDF files were found to back up.")

    uploaded: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    for pdf_path in local_pdfs:
        try:
            payload = pdf_path.read_bytes()
        except OSError:
            failed.append((pdf_path.name, "local file could not be read"))
            continue
        local_hash = hashlib.sha256(payload).hexdigest()
        if (pdf_path.name, local_hash) in existing_by_name_hash:
            skipped.append(pdf_path.name)
            continue
        try:
            adapter.upload(destination=destination, name=pdf_path.name, payload=payload)
        except Exception as exc:  # noqa: BLE001 - reported per file, run continues
            failed.append((pdf_path.name, str(exc)))
            continue
        uploaded.append(pdf_path.name)

    return CorpusPdfBackupSummary(
        uploaded=tuple(uploaded), skipped_unchanged=tuple(skipped), failed=tuple(failed)
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Back up local corpus PDFs to the allowlisted Drive source-documents "
            "folder, skipping files already present with a matching SHA-256."
        )
    )
    parser.add_argument("--papers-dir", type=Path, required=True)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=None,
        help=(
            "Path to a Google service-account JSON key. Defaults to "
            "KNOWLEDGE_ENGINE_GOOGLE_SERVICE_ACCOUNT if not given."
        ),
    )
    arguments = parser.parse_args()

    credentials_path = arguments.credentials
    if credentials_path is None:
        env_value = os.environ.get("KNOWLEDGE_ENGINE_GOOGLE_SERVICE_ACCOUNT", "")
        credentials_path = Path(env_value) if env_value else None
    if credentials_path is None:
        raise SystemExit(
            "A service-account credentials path is required "
            "(--credentials or KNOWLEDGE_ENGINE_GOOGLE_SERVICE_ACCOUNT)."
        )

    key = load_service_account_key(credentials_path)
    access_token = mint_access_token(key, scopes=(_DRIVE_SCOPE,))
    transport = GoogleDriveHttpTransport(access_token=access_token)
    summary = run_corpus_pdf_backup(papers_dir=arguments.papers_dir, transport=transport)

    print(
        f"Uploaded {len(summary.uploaded)} file(s); "
        f"skipped {len(summary.skipped_unchanged)} already present; "
        f"{len(summary.failed)} failed."
    )
    for name, reason in summary.failed:
        print(f"  FAILED {name}: {reason}")
    if summary.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
