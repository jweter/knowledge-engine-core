"""Fail-closed Google Drive project-folder boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

KNOWLEDGE_ENGINE_DRIVE_ROOT_ID = "1ygxvhp7eEmU55LkmyrE0G3XjUMkagUjX"

_FOLDER_IDS = {
    "source_manifests": "1rWlSmnsuGyO4LZIaVpP1hIWcqWzFO8rQ",
    "source_manifests.approved": "1Af1fZzg1l2R7ROQ_94IOljq_7ihL19IK",
    "source_manifests.drafts": "16-vz19Wt-V_sa0rNbhpdixXbSLYh0tA2",
    "acquisition_evidence": "1kpbeZ6spMqt8CafSQAa5oT6f2iy6J4cm",
    "acquisition_evidence.approvals": "1a__5z8jgt6nt8ES2DpW1wSQkexZuNF6C",
    "acquisition_evidence.receipts": "1HFK3NMcKeW8w290euZZFAMLNZl4O6Nrx",
    "acquisition_evidence.license_evidence": "1XI9e356PpThMdpQJDaiSLba5BLRl45Wc",
    "acquisition_evidence.calibration_reports": "1Fr7RTq0QtPvF8WglMYNBw7NNWgrEyTpB",
    "source_documents": "1p_-8Rc_g-D_-VHt0D_s4CQnfH2upL5Xh",
    "source_documents.pdf": "1Q2fS-D1oHokldwZzcf7UFyMS2-Nqgo50",
    "source_documents.xml": "1JVDFzQlRfq8vFadufN5CJZMhbqT715SK",
    "source_documents.supplements": "1N_TF_Jppc5cwZePTqJc1g3gVT2Gq5be_",
    "source_documents.quarantined": "1SLmhHzwvQvDAH2jSRpq6CC2s7SsXCcM1",
    "database_backups": "1_49wxrW6bQXeWRXeRcQ7_SzkpAzQ2Qcs",
    "database_backups.sqlite": "1xwjJkIOn3ytt34hIvQGyXyJHwsPlGb3Z",
    "database_backups.postgres": "1cAFlDghrBi8RGsB8PjRFN0ooK7lre7OI",
    "database_backups.integrity_reports": "1DH13oQ72dyDw2TwzJd4TL68qD4nNnEpL",
    "extracted_data": "1S-OocrFBEsmW4OoZcoJ_mQXu-TMm2TJ0",
    "extracted_data.text": "1hcykYrce0BXuzaXCbVad6xP4QMgMr0Qn",
    "extracted_data.metadata": "1Q6mXH1hTaSE6EoTzISJR5QU85xMdzZvw",
    "extracted_data.tables": "1JImrfL18Dm82ZGUlSLyDCzv8ayUumLsa",
    "extracted_data.figures": "11ZVn1y_7x1A_lt4ivv66eTwOV3DpjuOA",
    "ingestion_runs": "1wnbGXCMTo3WKGDM_qQGrlSo6VyF3smep",
    "ingestion_runs.reports": "1SFQt-ZVDditEF220zArjAkUScUFgrc5A",
    "ingestion_runs.failures": "1Yc4GF84vWvhiDy3MEjJhjvFYAd39FsiX",
    "ingestion_runs.reconciliation": "1XmAtaUuPVFehh8bbD0KIwR8h_juqK_kr",
    "exports": "1jxDJAV_rtleZXgOcC9RFgixLKB4HJ-eO",
    "exports.public": "14tA8lAsqBGXdx89e3UBSDPXskkX6BNHZ",
    "exports.internal": "1Nrc79_PUlWPIHtwwYeS3LdtK7p_yZZvj",
    "exports.research_packages": "1WDt38HQDYZfKexsrQe0F1_ms3hHpm731",
    "archive": "1GMd3AChqDzHIBrM95aJcGa3cjHV36YLy",
}

DRIVE_FOLDER_IDS: Mapping[str, str] = MappingProxyType(_FOLDER_IDS)


class DriveBoundaryError(ValueError):
    """Requested Drive destination is outside the approved project map."""


@dataclass(frozen=True)
class DriveDestination:
    """One validated logical destination under the Knowledge Engine root."""

    logical_name: str
    folder_id: str
    root_folder_id: str = KNOWLEDGE_ENGINE_DRIVE_ROOT_ID


def resolve_drive_destination(logical_name: str) -> DriveDestination:
    """Resolve one exact allowlisted destination and reject arbitrary identifiers."""

    normalized = logical_name.strip()
    if not normalized or normalized != logical_name:
        raise DriveBoundaryError("Drive destination must be an exact logical name.")
    folder_id = DRIVE_FOLDER_IDS.get(normalized)
    if folder_id is None:
        raise DriveBoundaryError("Drive destination is not allowlisted for Knowledge Engine.")
    return DriveDestination(logical_name=normalized, folder_id=folder_id)


def logical_name_for_folder_id(folder_id: str) -> str:
    """Return the logical name for an allowlisted folder ID."""

    matches = [name for name, value in DRIVE_FOLDER_IDS.items() if value == folder_id]
    if len(matches) != 1:
        raise DriveBoundaryError("Drive folder ID is not uniquely allowlisted.")
    return matches[0]
