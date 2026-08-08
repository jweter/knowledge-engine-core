"""Reacquire missing corpus PDFs from official open-access providers.

This recovery utility treats an existing Knowledge Engine SQLite corpus as the
inventory of papers that were previously ingested. It never inserts papers into
the database and never treats a successful download as scientific review.

For each paper it:

1. derives the historical PDF filename from ``papers.source_path``;
2. skips an already-present file whose SHA-256 matches the historical hash;
3. resolves the stored DOI against Europe PMC;
4. prefers PMC's official Article Datasets Cloud Service when the record is in PMC;
5. otherwise accepts only a Europe PMC-hosted PDF explicitly marked open access;
6. validates the payload is a PDF, hashes it, and commits it atomically; and
7. appends a JSONL recovery receipt so interrupted runs can be audited/resumed.

The historical SHA-256 is evidence about the old bytes, not a requirement that a
fresh official provider must return byte-identical content. A changed provider
copy is therefore recorded as ``reacquired_hash_changed`` rather than silently
rejected. Existing local hash mismatches are never overwritten unless
``--replace-mismatch`` is explicitly supplied; the old file is quarantined first.

No paywall circumvention, publisher scraping, browser automation, OCR, SQLite
mutation, or Evidence Record mutation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PDF_SIGNATURE = b"%PDF-"
MAX_PDF_BYTES = 100_000_000
MAX_METADATA_BYTES = 8_000_000
USER_AGENT = "knowledge-engine-core-corpus-recovery/1.0"
EUROPEPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EUROPEPMC_PDF_HOST = "europepmc.org"
PMC_CLOUD_HOST = "pmc-oa-opendata.s3.amazonaws.com"
PMC_CLOUD_BASE_URL = f"https://{PMC_CLOUD_HOST}"
PMC_CLOUD_BUCKET = "pmc-oa-opendata"
S3_NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._() -]*\.pdf$", re.IGNORECASE)
HISTORICAL_PMC_FILENAME = re.compile(r"^(PMC\d+)\.pdf$", re.IGNORECASE)


class RecoveryError(RuntimeError):
    """One sanitized corpus-recovery failure."""


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        raise RecoveryError("Provider attempted an unexpected redirect.")


@dataclass(frozen=True)
class PaperRow:
    paper_id: int
    title: str
    doi: str | None
    source_path: str
    historical_sha256: str
    historical_page_count: int
    historical_word_count: int


@dataclass(frozen=True)
class Resolution:
    provider: str
    doi: str
    pmcid: str | None
    license: str | None
    pdf_url: str


@dataclass(frozen=True)
class RecoveryReceipt:
    paper_id: int
    title: str
    doi: str | None
    filename: str
    status: str
    provider: str | None
    pmcid: str | None
    license: str | None
    historical_sha256: str
    current_sha256: str | None
    historical_hash_match: bool | None
    byte_count: int | None
    note: str | None


class HttpClient:
    """Small bounded HTTPS client with explicit provider allowlists."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.opener = build_opener(_NoRedirectHandler())

    def get(self, url: str, *, max_bytes: int, accept: str) -> bytes:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None:
            raise RecoveryError("Provider URL failed HTTPS validation.")
        if parsed.port not in (None, 443):
            raise RecoveryError("Provider URL used an unsupported port.")
        allowed_hosts = {
            "www.ebi.ac.uk",
            EUROPEPMC_PDF_HOST,
            PMC_CLOUD_HOST,
        }
        if parsed.hostname not in allowed_hosts:
            raise RecoveryError(f"Provider host is not allowlisted: {parsed.hostname!r}.")
        request = Request(
            url,
            headers={"Accept": accept, "User-Agent": USER_AGENT},
            method="GET",
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                declared = response.headers.get("Content-Length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise RecoveryError("Provider response exceeded the configured size limit.")
                payload = response.read(max_bytes + 1)
        except HTTPError as exc:
            raise RecoveryError(f"Provider returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise RecoveryError("Provider request failed.") from exc
        if len(payload) > max_bytes:
            raise RecoveryError("Provider response exceeded the configured size limit.")
        return payload


def normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
    return normalized.rstrip(". ") or None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_filename(source_path: str, paper_id: int) -> str:
    candidate = Path(source_path.replace("\\", "/")).name
    if candidate and SAFE_FILENAME.fullmatch(candidate):
        return candidate
    return f"paper-{paper_id}.pdf"


def load_papers(database: Path) -> list[PaperRow]:
    if not database.is_file():
        raise RecoveryError(f"Database not found: {database}")
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        columns = {row[1] for row in con.execute("PRAGMA table_info(papers)")}
        required = {
            "id",
            "title",
            "doi",
            "source_path",
            "content_hash",
            "page_count",
            "word_count",
        }
        missing = required - columns
        if missing:
            raise RecoveryError(f"Database papers table is missing columns: {sorted(missing)}")
        rows = con.execute(
            """
            SELECT id, title, doi, source_path, content_hash, page_count, word_count
            FROM papers
            ORDER BY id
            """
        ).fetchall()
    finally:
        con.close()
    return [
        PaperRow(
            paper_id=int(row[0]),
            title=str(row[1]),
            doi=normalize_doi(row[2]),
            source_path=str(row[3]),
            historical_sha256=str(row[4]).lower(),
            historical_page_count=int(row[5]),
            historical_word_count=int(row[6]),
        )
        for row in rows
    ]


def _json_get(client: HttpClient, url: str) -> dict[str, Any]:
    payload = client.get(url, max_bytes=MAX_METADATA_BYTES, accept="application/json")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecoveryError("Provider returned malformed JSON.") from exc
    if not isinstance(value, dict):
        raise RecoveryError("Provider returned malformed JSON.")
    return value


def _xml_get(client: HttpClient, url: str) -> ET.Element:
    payload = client.get(url, max_bytes=MAX_METADATA_BYTES, accept="application/xml")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RecoveryError("Provider returned malformed XML.") from exc


def _pmc_latest_version(client: HttpClient, pmcid: str) -> int | None:
    url = f"{PMC_CLOUD_BASE_URL}/?" + urlencode(
        {"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"}
    )
    root = _xml_get(client, url)
    versions: list[int] = []
    for element in root.findall(".//s3:CommonPrefixes/s3:Prefix", S3_NS):
        text = (element.text or "").strip()
        suffix = text.removeprefix(f"{pmcid}.").rstrip("/")
        if suffix.isdigit():
            versions.append(int(suffix))
    return max(versions) if versions else None


def _pmc_cloud_pdf_url(raw_pdf_url: str) -> str:
    """Convert the Article Datasets Cloud Service's ``s3://`` pdf_url into HTTPS.

    PMC's metadata JSON records ``pdf_url``/``text_url``/``xml_url`` as
    ``s3://pmc-oa-opendata/<key>`` URIs, not HTTPS URLs. Only the
    ``pmc-oa-opendata`` bucket is ever accepted; anything else is rejected
    rather than silently fetched.
    """
    parsed = urlsplit(raw_pdf_url)
    if parsed.scheme != "s3" or parsed.netloc != PMC_CLOUD_BUCKET:
        raise RecoveryError("PMC metadata returned a non-allowlisted PDF URL.")
    key = parsed.path.lstrip("/")
    if not key:
        raise RecoveryError("PMC metadata returned an empty PDF object key.")
    https_url = f"{PMC_CLOUD_BASE_URL}/{key}"
    if parsed.query:
        https_url = f"{https_url}?{parsed.query}"
    return https_url


def _pmc_resolution(
    client: HttpClient, *, doi: str, pmcid: str, expected_doi: str | None = None
) -> Resolution | None:
    version = _pmc_latest_version(client, pmcid)
    if version is None:
        return None
    metadata = _json_get(client, f"{PMC_CLOUD_BASE_URL}/metadata/{pmcid}.{version}.json")
    if metadata.get("pmcid") != pmcid or metadata.get("version") != version:
        raise RecoveryError("PMC metadata identity did not reconcile.")
    if expected_doi is not None:
        metadata_doi = metadata.get("doi")
        if (
            isinstance(metadata_doi, str)
            and normalize_doi(metadata_doi) is not None
            and normalize_doi(metadata_doi) != expected_doi
        ):
            raise RecoveryError("PMC metadata DOI did not match the expected paper identity.")
    if metadata.get("is_pmc_openaccess") is not True:
        return None
    raw_pdf_url = metadata.get("pdf_url")
    if not isinstance(raw_pdf_url, str) or not raw_pdf_url:
        return None
    pdf_url = _pmc_cloud_pdf_url(raw_pdf_url)
    license_value = metadata.get("license_code")
    license_name = license_value if isinstance(license_value, str) else None
    return Resolution(
        provider="pmc_article_datasets_cloud",
        doi=doi,
        pmcid=pmcid,
        license=license_name,
        pdf_url=pdf_url,
    )


def _europepmc_pdf(raw: dict[str, Any]) -> str | None:
    full_text = raw.get("fullTextUrlList")
    if not isinstance(full_text, dict):
        return None
    entries = full_text.get("fullTextUrl")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("availabilityCode") != "OA" or entry.get("documentStyle") != "pdf":
            continue
        url = entry.get("url")
        if isinstance(url, str) and urlsplit(url).hostname == EUROPEPMC_PDF_HOST:
            return url
    return None


def resolve_doi(client: HttpClient, doi: str) -> Resolution | None:
    query = f'DOI:"{doi}"'
    url = (
        EUROPEPMC_SEARCH_URL
        + "?"
        + urlencode(
            {
                "query": query,
                "format": "json",
                "resultType": "core",
                "pageSize": 10,
            }
        )
    )
    body = _json_get(client, url)
    result_list = body.get("resultList")
    if not isinstance(result_list, dict):
        raise RecoveryError("Europe PMC search response was malformed.")
    rows = result_list.get("result")
    if not isinstance(rows, list):
        raise RecoveryError("Europe PMC search response was malformed.")
    exact: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if normalize_doi(row.get("doi") if isinstance(row.get("doi"), str) else None) == doi:
            exact.append(row)
    if not exact:
        return None

    # Prefer an exact DOI record in PMC because NCBI's OA cloud is the repository's
    # established primary acquisition route.
    for row in exact:
        pmcid = row.get("pmcid")
        if row.get("inPMC") == "Y" and isinstance(pmcid, str) and pmcid.startswith("PMC"):
            resolved = _pmc_resolution(client, doi=doi, pmcid=pmcid, expected_doi=doi)
            if resolved is not None:
                return resolved

    for row in exact:
        if row.get("isOpenAccess") != "Y":
            continue
        pdf_url = _europepmc_pdf(row)
        if pdf_url is None:
            continue
        license_value = row.get("license")
        return Resolution(
            provider="europe_pmc_hosted_oa",
            doi=doi,
            pmcid=row.get("pmcid") if isinstance(row.get("pmcid"), str) else None,
            license=license_value if isinstance(license_value, str) else None,
            pdf_url=pdf_url,
        )
    return None


def resolve_historical_pmcid(
    client: HttpClient, *, doi: str | None, filename: str
) -> Resolution | None:
    """Try the PMCID already embedded in the historical filename directly.

    Europe PMC's DOI-search index does not reliably report ``inPMC``/
    ``isOpenAccess`` for every paper that PMC's own Article Datasets Cloud
    Service actually has -- confirmed live: papers whose historical filename
    already names a real PMCID sometimes come back with no exact-DOI PMC
    match in Europe PMC's search response, even though that exact PMCID
    exists in the Cloud Service bucket. Since the historical filename came
    from this project's own prior acquisition (not user input), checking it
    directly first is strictly more reliable than depending on Europe PMC's
    search index alone. Falls back silently (returns ``None``) for a
    filename that is not PMC-shaped, or a PMCID that turns out not to be
    open access -- ``resolve_doi`` still runs afterward either way.
    """

    match = HISTORICAL_PMC_FILENAME.match(filename)
    if match is None:
        return None
    pmcid = match.group(1).upper()
    return _pmc_resolution(client, doi=doi or "", pmcid=pmcid, expected_doi=doi)


def append_receipt(path: Path, receipt: RecoveryReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(asdict(receipt), sort_keys=True, ensure_ascii=False) + "\n")


def quarantine_existing(path: Path) -> Path:
    current_hash = sha256_file(path)
    quarantine = path.with_name(f"{path.stem}.historical-mismatch-{current_hash[:12]}{path.suffix}")
    if quarantine.exists():
        raise RecoveryError(f"Quarantine destination already exists: {quarantine.name}")
    os.replace(path, quarantine)
    return quarantine


def download_pdf(client: HttpClient, resolution: Resolution) -> bytes:
    payload = client.get(resolution.pdf_url, max_bytes=MAX_PDF_BYTES, accept="application/pdf")
    if not payload.startswith(PDF_SIGNATURE):
        raise RecoveryError("Resolved open-access resource was not a PDF payload.")
    return payload


def recover_one(
    paper: PaperRow,
    *,
    target_dir: Path,
    receipts_path: Path,
    client: HttpClient,
    dry_run: bool,
    replace_mismatch: bool,
) -> RecoveryReceipt:
    filename = safe_filename(paper.source_path, paper.paper_id)
    destination = target_dir / filename

    if destination.exists():
        if not destination.is_file() or destination.is_symlink():
            return RecoveryReceipt(
                paper.paper_id,
                paper.title,
                paper.doi,
                filename,
                "blocked_existing_path",
                None,
                None,
                None,
                paper.historical_sha256,
                None,
                None,
                None,
                "Existing destination is not a regular file.",
            )
        current_hash = sha256_file(destination)
        if current_hash == paper.historical_sha256:
            return RecoveryReceipt(
                paper.paper_id,
                paper.title,
                paper.doi,
                filename,
                "already_present_verified",
                None,
                None,
                None,
                paper.historical_sha256,
                current_hash,
                True,
                destination.stat().st_size,
                None,
            )
        if not replace_mismatch:
            return RecoveryReceipt(
                paper.paper_id,
                paper.title,
                paper.doi,
                filename,
                "existing_hash_mismatch",
                None,
                None,
                None,
                paper.historical_sha256,
                current_hash,
                False,
                destination.stat().st_size,
                "Re-run with --replace-mismatch only after reviewing the existing file.",
            )
        if not dry_run:
            quarantine_existing(destination)

    # The historical filename's own PMCID (when present) is tried first: it
    # came from this project's own prior acquisition, and is confirmed more
    # reliable than Europe PMC's DOI-search index alone (some PMC-hosted,
    # open-access papers never come back as an exact-DOI PMC match there). A
    # hiccup on this fast path (network error, identity mismatch) falls
    # through to the proven resolve_doi() path rather than failing outright.
    resolution: Resolution | None = None
    try:
        resolution = resolve_historical_pmcid(client, doi=paper.doi, filename=filename)
    except RecoveryError:
        resolution = None

    resolution_error: RecoveryError | None = None
    if resolution is None and paper.doi is not None:
        try:
            resolution = resolve_doi(client, paper.doi)
        except RecoveryError as exc:
            resolution_error = exc

    if resolution is None:
        if resolution_error is not None:
            return RecoveryReceipt(
                paper.paper_id,
                paper.title,
                paper.doi,
                filename,
                "resolution_failed",
                None,
                None,
                None,
                paper.historical_sha256,
                None,
                None,
                None,
                str(resolution_error),
            )
        if paper.doi is None:
            return RecoveryReceipt(
                paper.paper_id,
                paper.title,
                None,
                filename,
                "unresolved_no_doi",
                None,
                None,
                None,
                paper.historical_sha256,
                None,
                None,
                None,
                "Database row has no DOI and the historical filename did not "
                "resolve to an open-access PMC record; manual source resolution "
                "is required.",
            )
        return RecoveryReceipt(
            paper.paper_id,
            paper.title,
            paper.doi,
            filename,
            "open_access_source_unresolved",
            None,
            None,
            None,
            paper.historical_sha256,
            None,
            None,
            None,
            "No allowlisted open-access PDF was resolved for the stored DOI.",
        )

    if dry_run:
        return RecoveryReceipt(
            paper.paper_id,
            paper.title,
            paper.doi,
            filename,
            "dry_run_resolved",
            resolution.provider,
            resolution.pmcid,
            resolution.license,
            paper.historical_sha256,
            None,
            None,
            None,
            resolution.pdf_url,
        )

    try:
        payload = download_pdf(client, resolution)
    except RecoveryError as exc:
        return RecoveryReceipt(
            paper.paper_id,
            paper.title,
            paper.doi,
            filename,
            "download_failed",
            resolution.provider,
            resolution.pmcid,
            resolution.license,
            paper.historical_sha256,
            None,
            None,
            None,
            str(exc),
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    temporary = target_dir / f".{filename}.reacquire.tmp"
    try:
        temporary.write_bytes(payload)
        current_hash = hashlib.sha256(payload).hexdigest()
        os.replace(temporary, destination)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        return RecoveryReceipt(
            paper.paper_id,
            paper.title,
            paper.doi,
            filename,
            "commit_failed",
            resolution.provider,
            resolution.pmcid,
            resolution.license,
            paper.historical_sha256,
            None,
            None,
            None,
            f"Downloaded PDF could not be committed: {exc.__class__.__name__}",
        )

    matched = current_hash == paper.historical_sha256
    return RecoveryReceipt(
        paper.paper_id,
        paper.title,
        paper.doi,
        filename,
        "reacquired_verified" if matched else "reacquired_hash_changed",
        resolution.provider,
        resolution.pmcid,
        resolution.license,
        paper.historical_sha256,
        current_hash,
        matched,
        len(payload),
        None
        if matched
        else (
            "Official OA provider returned bytes different from the historical PDF;"
            " identity requires later parser/source review."
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument(
        "--receipts",
        type=Path,
        default=Path("work/corpus-recovery/reacquisition_receipts.jsonl"),
    )
    parser.add_argument("--limit", type=int, default=None, help="Process at most N database rows.")
    parser.add_argument("--start-id", type=int, default=0, help="Skip paper IDs below this value.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Resolve sources without downloading PDFs."
    )
    parser.add_argument(
        "--replace-mismatch",
        action="store_true",
        help="Quarantine an existing hash-mismatched PDF and reacquire it.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=0.4,
        help="Delay between papers to avoid aggressive provider traffic (default: 0.4 s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if args.start_id < 0:
        raise SystemExit("--start-id must be non-negative")
    if args.request_delay < 0:
        raise SystemExit("--request-delay must be non-negative")

    papers = [paper for paper in load_papers(args.database) if paper.paper_id >= args.start_id]
    if args.limit is not None:
        papers = papers[: args.limit]
    if not papers:
        print("No papers selected.")
        return 0

    client = HttpClient()
    counts: dict[str, int] = {}
    print(f"Selected {len(papers)} paper(s). Target: {args.target_dir}")
    for index, paper in enumerate(papers, start=1):
        receipt = recover_one(
            paper,
            target_dir=args.target_dir,
            receipts_path=args.receipts,
            client=client,
            dry_run=args.dry_run,
            replace_mismatch=args.replace_mismatch,
        )
        append_receipt(args.receipts, receipt)
        counts[receipt.status] = counts.get(receipt.status, 0) + 1
        print(
            f"[{index}/{len(papers)}] paper {paper.paper_id}: {receipt.status} - {receipt.filename}"
        )
        if index != len(papers) and args.request_delay:
            time.sleep(args.request_delay)

    print("\nSummary")
    print("-------")
    for status in sorted(counts):
        print(f"{status}: {counts[status]}")
    print(f"Receipts: {args.receipts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
