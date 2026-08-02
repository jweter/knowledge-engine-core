"""Download the latest corpus-library snapshot from Drive and import it locally.

`ke-corpus-library-drive-backup` only pushes: it exports this database's
corpus-library content and uploads it to Drive, skipping the upload when an
identical snapshot is already there. Nothing on the laptop side pulls that
snapshot back down. This is the other half -- it lists the allowlisted
`corpus_library.snapshot` Drive folder, picks the most recently created file,
skips the download entirely if its SHA-256 matches the last snapshot this
machine already imported (a local marker file records that), and otherwise
downloads and imports it via `import_corpus_library_compressed`, which is
itself idempotent per paper (a content hash already present locally is
skipped, not reprocessed).
"""

from __future__ import annotations

import argparse
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from knowledge_engine.config import Settings
from knowledge_engine.corpus_library import ImportSummary, import_corpus_library_compressed
from knowledge_engine.database import Database
from knowledge_engine.drive_adapter import (
    ConstrainedDriveAdapter,
    DriveFileMetadata,
    DriveTransport,
)
from knowledge_engine.drive_boundary import resolve_drive_destination
from knowledge_engine.google_drive_http import GoogleDriveHttpTransport
from knowledge_engine.google_drive_oauth_refresh import (
    load_refresh_token_credentials,
    mint_access_token,
)

_DESTINATION_NAME = "corpus_library.snapshot"
_DOWNLOADED_SNAPSHOT_NAME = "corpus_library_snapshot.sqlite3.gz"
_MARKER_NAME = "last_imported.sha256"

RestoreStatus = Literal["no_snapshot", "already_up_to_date", "imported"]


class CorpusLibraryDriveRestoreError(RuntimeError):
    """Sanitized corpus-library Drive restore failure."""


class RestoringDriveTransport(DriveTransport, Protocol):
    """Transport operations required beyond plain uploads: listing and download."""

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]: ...

    def download_bytes(self, file_id: str) -> bytes: ...


@dataclass(frozen=True)
class DriveRestoreResult:
    """Outcome of one restore attempt, distinguishing all three real cases."""

    status: RestoreStatus
    file_id: str | None = None
    sha256: str = ""
    import_summary: ImportSummary | None = None


def _parse_created_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read_marker(marker_path: Path) -> str:
    if not marker_path.is_file():
        return ""
    return marker_path.read_text(encoding="utf-8").strip()


def run_corpus_library_drive_restore(
    *,
    target_database: Path,
    output_directory: Path,
    transport: RestoringDriveTransport,
) -> DriveRestoreResult:
    """Download and import the newest Drive snapshot if this machine lacks it.

    Returns a `DriveRestoreResult` whose `status` is `"no_snapshot"` (the
    Drive folder is empty), `"already_up_to_date"` (the newest snapshot's
    SHA-256 matches this machine's last-imported marker -- nothing
    downloaded), or `"imported"` (a snapshot was downloaded and run through
    `import_corpus_library_compressed`; its own per-paper dedup means
    `import_summary.imported_paper_count` can still be zero if every paper in
    it already exists locally).
    """

    destination = resolve_drive_destination(_DESTINATION_NAME)
    adapter = ConstrainedDriveAdapter(transport)
    adapter.verify_destination(destination)

    files = transport.list_files(destination.folder_id)
    if not files:
        return DriveRestoreResult(status="no_snapshot")
    latest = max(files, key=lambda entry: _parse_created_time(entry.created_time))
    if not latest.sha256:
        raise CorpusLibraryDriveRestoreError(
            "Drive snapshot metadata is missing its recorded hash."
        )

    output_directory.mkdir(parents=True, exist_ok=True)
    marker_path = output_directory / _MARKER_NAME
    last_imported_hash = _read_marker(marker_path)
    if last_imported_hash and last_imported_hash.casefold() == latest.sha256.casefold():
        return DriveRestoreResult(
            status="already_up_to_date", file_id=latest.file_id, sha256=latest.sha256
        )

    payload = transport.download_bytes(latest.file_id)
    if hashlib.sha256(payload).hexdigest().casefold() != latest.sha256.casefold():
        raise CorpusLibraryDriveRestoreError(
            "Downloaded corpus library snapshot did not match its recorded hash."
        )

    snapshot_path = output_directory / _DOWNLOADED_SNAPSHOT_NAME
    if snapshot_path.exists():
        snapshot_path.unlink()
    snapshot_path.write_bytes(payload)

    database = Database(
        Settings(database_url=f"sqlite:///{target_database}", data_dir=target_database.parent)
    )
    database.initialize()
    try:
        with database.session() as session:
            summary = import_corpus_library_compressed(session, snapshot_path)
    except Exception as exc:
        raise CorpusLibraryDriveRestoreError(
            "Corpus library import did not complete due to an internal error."
        ) from exc
    finally:
        database.engine.dispose()

    marker_path.write_text(latest.sha256, encoding="utf-8")
    return DriveRestoreResult(
        status="imported", file_id=latest.file_id, sha256=latest.sha256, import_summary=summary
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Download the most recently uploaded corpus-library snapshot from Drive and "
            "import it into the local database, skipping entirely if it was already imported."
        )
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--credentials",
        type=Path,
        default=None,
        help=(
            "Path to a stored OAuth refresh-token credentials file. Defaults to "
            "KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS if not given."
        ),
    )
    arguments = parser.parse_args()

    credentials_path = arguments.credentials
    if credentials_path is None:
        env_value = os.environ.get("KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS", "")
        credentials_path = Path(env_value) if env_value else None
    if credentials_path is None:
        raise SystemExit(
            "OAuth refresh-token credentials are required "
            "(--credentials or KNOWLEDGE_ENGINE_GOOGLE_OAUTH_REFRESH_CREDENTIALS)."
        )

    refresh_credentials = load_refresh_token_credentials(credentials_path)
    access_token = mint_access_token(refresh_credentials)
    transport = GoogleDriveHttpTransport(access_token=access_token)

    result = run_corpus_library_drive_restore(
        target_database=arguments.database,
        output_directory=arguments.output_dir,
        transport=transport,
    )
    if result.status == "no_snapshot":
        print("No corpus library snapshot found in Drive yet -- nothing to restore.")
    elif result.status == "already_up_to_date":
        print("Corpus library already up to date -- nothing downloaded.")
    else:
        assert result.import_summary is not None
        print(
            f"Restored corpus library snapshot: file_id={result.file_id} "
            f"{result.import_summary.imported_paper_count} paper(s) imported, "
            f"{result.import_summary.skipped_existing_paper_count} already present and skipped."
        )


if __name__ == "__main__":
    main()
