"""Upload the local database's corpus-library content to Drive, skipping unchanged snapshots.

`corpus_library.py`'s own module docstring calls the exported snapshot
"git-committable" -- that was true when the corpus was small. Committing a
growing multi-hundred-MB snapshot to git repeatedly is exactly what bloated
this repo's history before (see the 2026-08-02 Drive-root-boundary and
service-account-quota fixes); GitHub's 100MB single-file cap makes it a hard
wall besides. This tool uploads the same snapshot to Drive instead, reusing
`ke-drive-backup-pilot`'s proven OAuth refresh-token auth (a bare service
account cannot write here -- confirmed live, no Drive storage quota on a
personal account) and `ke-corpus-pdf-backup`'s skip-if-hash-matches pattern,
so a week with zero new papers uploads nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Protocol

from sqlalchemy import create_engine

from knowledge_engine.corpus_library import export_corpus_library_compressed
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
_SNAPSHOT_NAME = "corpus_library_snapshot.sqlite3.gz"


class CorpusLibraryDriveBackupError(RuntimeError):
    """Sanitized corpus-library Drive backup failure."""


class ListingDriveTransport(DriveTransport, Protocol):
    """Transport operations required beyond plain uploads: listing for dedup."""

    def list_files(self, folder_id: str) -> list[DriveFileMetadata]: ...


def run_corpus_library_drive_backup(
    *,
    source_database: Path,
    output_directory: Path,
    transport: ListingDriveTransport,
) -> str | None:
    """Export the local corpus library and upload it if it differs from every Drive copy.

    Returns the uploaded file's id, or `None` if skipped because a snapshot
    with an identical SHA-256 is already present at the destination (a week
    with no new papers, or a re-run after a prior successful upload).
    """

    destination = resolve_drive_destination(_DESTINATION_NAME)
    adapter = ConstrainedDriveAdapter(transport)
    adapter.verify_destination(destination)

    output_directory.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_directory / _SNAPSHOT_NAME
    if snapshot_path.exists():
        snapshot_path.unlink()
    source_engine = create_engine(f"sqlite:///{source_database}", future=True)
    try:
        export_corpus_library_compressed(source_engine, snapshot_path)
    except Exception as exc:
        raise CorpusLibraryDriveBackupError(
            "Corpus library export did not complete due to an internal error."
        ) from exc

    payload = snapshot_path.read_bytes()
    if not payload:
        raise CorpusLibraryDriveBackupError("Corpus library export produced an empty file.")
    local_hash = hashlib.sha256(payload).hexdigest()

    existing_hashes = {
        entry.sha256.casefold()
        for entry in transport.list_files(destination.folder_id)
        if entry.sha256
    }
    if local_hash.casefold() in existing_hashes:
        return None

    upload = adapter.upload(destination=destination, name=_SNAPSHOT_NAME, payload=payload)
    return upload.file_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export the local database's corpus-library content and upload it to Drive, "
            "skipping the upload entirely if an identical snapshot is already there."
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

    file_id = run_corpus_library_drive_backup(
        source_database=arguments.database,
        output_directory=arguments.output_dir,
        transport=transport,
    )
    if file_id is None:
        print("Corpus library unchanged -- nothing uploaded.")
    else:
        print(f"Uploaded corpus library snapshot: file_id={file_id}")


if __name__ == "__main__":
    main()
