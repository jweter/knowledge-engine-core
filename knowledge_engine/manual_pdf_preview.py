"""Preview-first evidence for a single human-supplied PDF.

`ke import`/`ke corpus-import` have always accepted any local PDF -- no
door was ever closed there. What was missing was a way to avoid hand-typing
a manifest row's worth of metadata (title, authors, DOI, license) for each
one. `PyMuPDFParser` (the same parser `ke import` itself uses) already
extracts title/authors/abstract/DOI/page-count/word-count deterministically
from the PDF's own bytes; this module wires that into a review-first
preview, optionally cross-checked against Unpaywall (M36) for OA/license
evidence when a DOI is found, so whoever is adding this one PDF (a human
or an AI agent) reviews one small JSON file instead of typing a CSV row
by hand.

Mirrors the discovery-then-adjudication shape used everywhere else in this
project, scaled down to one PDF at a time: `prepare_manual_pdf_preview`
never writes to the corpus manifest or database, and
`export_manual_pdf_manifest_draft` refuses to produce a manifest-ready row
unless the preview's `license_rule_result` is `"passed"` -- exactly the
same bar every automated pipeline's adjudication engine already enforces.
Running the second command is itself the explicit approval act (by a
human or an AI agent), the same way an automated batch's `--approvals`
file is.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from knowledge_engine.license_rules import evaluate_license, license_deed_url
from knowledge_engine.manifest_curation import MANIFEST_FIELDS, ManifestCurationDraft
from knowledge_engine.parser import DocumentParseError, DocumentParser, PyMuPDFParser
from knowledge_engine.unpaywall_lookup import UnpaywallLookupResult, normalize_unpaywall_license


class ManualPdfPreviewError(RuntimeError):
    """Sanitized manual-PDF preview or manifest-draft failure."""


class UnpaywallLookup(Protocol):
    """Structural interface for the one Unpaywall operation this module needs."""

    def lookup(self, doi: str) -> UnpaywallLookupResult:
        """Return one DOI's OA-location/license evidence."""


@dataclass(frozen=True)
class ManualPdfPreview:
    """Reviewable evidence for one human-supplied PDF, before any promotion."""

    source_path: str
    content_hash: str
    title: str
    authors: tuple[str, ...]
    abstract: str | None
    doi: str | None
    page_count: int
    word_count: int
    doi_lookup_performed: bool
    unpaywall_title: str | None
    unpaywall_is_oa: bool | None
    unpaywall_best_license: str | None
    license_rule_result: str
    previewed_at: str

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def prepare_manual_pdf_preview(
    pdf_path: Path,
    *,
    parser: DocumentParser | None = None,
    unpaywall_service: UnpaywallLookup | None = None,
) -> ManualPdfPreview:
    """Parse one local PDF and report reviewable evidence -- never imports it.

    Local parsing (title/authors/abstract/DOI/page-count/word-count) always
    runs. Passing `unpaywall_service` additionally looks up a found DOI for
    OA/license evidence over the network; omit it to stay fully offline,
    at the cost of `license_rule_result` always being
    `"incomplete_missing_license"` (no CORE-style silent guessing either).
    """

    if pdf_path.is_symlink():
        raise ManualPdfPreviewError("PDF input must not be a symbolic link.")

    active_parser = parser or PyMuPDFParser()
    try:
        parsed = active_parser.parse(pdf_path)
    except DocumentParseError as exc:
        raise ManualPdfPreviewError(str(exc)) from exc

    doi_lookup_performed = False
    unpaywall_title: str | None = None
    unpaywall_is_oa: bool | None = None
    unpaywall_best_license: str | None = None
    license_rule_result = evaluate_license(None)

    if unpaywall_service is not None and parsed.doi is not None:
        doi_lookup_performed = True
        result = unpaywall_service.lookup(parsed.doi)
        if result.found and result.record is not None:
            unpaywall_title = result.record.title
            unpaywall_is_oa = result.record.is_oa
            unpaywall_best_license = normalize_unpaywall_license(
                result.record.best_oa_location_license
            )
            license_rule_result = result.record.license_rule_result

    return ManualPdfPreview(
        source_path=str(pdf_path),
        content_hash=parsed.content_hash,
        title=parsed.title,
        authors=tuple(parsed.authors),
        abstract=parsed.abstract,
        doi=parsed.doi,
        page_count=parsed.page_count,
        word_count=parsed.word_count,
        doi_lookup_performed=doi_lookup_performed,
        unpaywall_title=unpaywall_title,
        unpaywall_is_oa=unpaywall_is_oa,
        unpaywall_best_license=unpaywall_best_license,
        license_rule_result=license_rule_result,
        previewed_at=datetime.now(UTC).isoformat(),
    )


def export_manual_pdf_manifest_draft(preview_path: Path) -> ManifestCurationDraft:
    """Turn one reviewed, license-verified preview into a manifest-ready row.

    Refuses -- rather than guessing -- unless `license_rule_result` is
    exactly `"passed"` and a DOI is present (this project's identity
    anchor for manually-supplied evidence, same as every automated
    pipeline). Running this command against a preview the human has looked
    at and accepted is itself the approval act; it never touches
    `sources.csv` directly, matching `manifest_curation_cli.py`'s existing
    "export a draft, do not modify the manifest" contract.
    """

    if preview_path.is_symlink():
        raise ManualPdfPreviewError("Preview input must not be a symbolic link.")
    try:
        payload = json.loads(preview_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManualPdfPreviewError("Preview input is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ManualPdfPreviewError("Preview input is not valid JSON.")

    if payload.get("license_rule_result") != "passed":
        raise ManualPdfPreviewError(
            "Preview license evidence is not verified as reusable; refusing to draft "
            "a manifest row. Only a preview with license_rule_result == 'passed' "
            "(an Unpaywall-verified reusable license) can be promoted this way."
        )
    doi = payload.get("doi")
    if not isinstance(doi, str) or not doi.strip():
        raise ManualPdfPreviewError("Preview is missing a DOI; refusing to draft a manifest row.")
    title = _required_string(payload, "title")
    content_hash = _required_string(payload, "content_hash")
    source_path = _required_string(payload, "source_path")
    license_name = _required_string(payload, "unpaywall_best_license")
    previewed_at = _required_string(payload, "previewed_at")

    row = {field: "" for field in MANIFEST_FIELDS}
    row.update(
        {
            "source_id": f"manual-{content_hash[:12]}",
            "title": title,
            "authors": _authors(payload),
            "doi": doi.strip(),
            "source_url": f"https://doi.org/{doi.strip()}",
            "local_path": Path(source_path).name,
            "access_date": _access_date(previewed_at),
            "license_type": license_name,
            "license_url": _license_url(license_name),
            "usage_status": "approved_open_access",
            "inclusion_status": "included",
            "inclusion_reason": "MANUAL_UPLOAD_LICENSE_VERIFIED_VIA_UNPAYWALL",
            "expected_content_hash": f"sha256:{content_hash}",
            "source_type": "paper",
            "notes": f"Manual PDF upload; license verified via Unpaywall lookup at {previewed_at}.",
        }
    )
    return ManifestCurationDraft(rows=(row,))


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManualPdfPreviewError("Preview is missing required evidence.")
    return value.strip()


def _authors(payload: dict[str, object]) -> str:
    value = payload.get("authors", [])
    if not isinstance(value, list) or not all(
        isinstance(author, str) and author.strip() for author in value
    ):
        raise ManualPdfPreviewError("Preview contains malformed author evidence.")
    return "; ".join(author.strip() for author in value)


def _access_date(previewed_at: str) -> str:
    try:
        return datetime.fromisoformat(previewed_at).date().isoformat()
    except ValueError as exc:
        raise ManualPdfPreviewError("Preview timestamp is malformed.") from exc


def _license_url(license_name: str) -> str:
    try:
        return license_deed_url(license_name)
    except ValueError as exc:
        raise ManualPdfPreviewError("License evidence has no canonical deed URL.") from exc
