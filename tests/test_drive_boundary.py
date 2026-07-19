from __future__ import annotations

import pytest

from knowledge_engine.drive_boundary import (
    DRIVE_FOLDER_IDS,
    KNOWLEDGE_ENGINE_DRIVE_ROOT_ID,
    DriveBoundaryError,
    logical_name_for_folder_id,
    resolve_drive_destination,
)


def test_resolves_allowlisted_destination() -> None:
    destination = resolve_drive_destination("database_backups.sqlite")

    assert destination.folder_id == "1xwjJkIOn3ytt34hIvQGyXyJHwsPlGb3Z"
    assert destination.root_folder_id == KNOWLEDGE_ENGINE_DRIVE_ROOT_ID


def test_rejects_unknown_destination() -> None:
    with pytest.raises(DriveBoundaryError, match="not allowlisted"):
        resolve_drive_destination("personal_documents")


def test_rejects_folder_id_as_destination() -> None:
    with pytest.raises(DriveBoundaryError, match="not allowlisted"):
        resolve_drive_destination(KNOWLEDGE_ENGINE_DRIVE_ROOT_ID)


def test_rejects_normalization_ambiguity() -> None:
    with pytest.raises(DriveBoundaryError, match="exact logical name"):
        resolve_drive_destination(" exports.public ")


def test_folder_ids_are_unique() -> None:
    assert len(set(DRIVE_FOLDER_IDS.values())) == len(DRIVE_FOLDER_IDS)


def test_reverse_lookup_requires_allowlisted_folder() -> None:
    assert logical_name_for_folder_id("14tA8lAsqBGXdx89e3UBSDPXskkX6BNHZ") == "exports.public"
    with pytest.raises(DriveBoundaryError, match="not uniquely allowlisted"):
        logical_name_for_folder_id("outside-project-folder")
