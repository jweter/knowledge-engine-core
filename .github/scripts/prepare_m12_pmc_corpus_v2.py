from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
USER_AGENT = "KnowledgeEngineM12/1.0 (https://github.com/jweter/knowledge-engine-core)"
ALLOWED_LICENSES = {"CC0", "CC BY", "CC BY-SA", "CC BY-ND"}
LICENSE_URLS = {
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC BY": "https://creativecommons.org/licenses/by/4.0/",
    "CC BY-SA": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC BY-ND": "https://creativecommons.org/licenses/by-nd/4.0/",
}
MAX_PACKAGE_BYTES = 50 * 1024 * 1024
MAX_PDF_BYTES = 25 * 1024 * 1024
CSV_FIELDS = [
    "source_id",
    "title",
    "authors",
    "publication_year",
    "venue",
    "doi",
    "pmid",
    "arxiv_id",
    "other_identifier",
    "source_url",
    "pdf_url",
    "local_path",
    "access_date",
    "license_type",
    "license_url",
    "usage_status",
    "inclusion_status",
    "inclusion_reason",
    "exclusion_reason",
    "expected_content_hash",
    "source_type",
    "study_type",
    "population",
    "intervention",
    "comparator",
    "outcome_notes",
    "notes",
]


@dataclass(frozen=True)
class Candidate:
    pmcid: str
    citation: str
    license_type: str
    package_url: str


def _request_bytes(url: str, *, maximum: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        declared = response.headers.get("Content-Length")
        if declared and int(declared) > maximum:
            raise ValueError("declared response exceeds configured limit")
        payload = response.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError("streamed response exceeds configured limit")
    return payload


def _https_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.hostname != "ftp.ncbi.nlm.nih.gov" or parsed.scheme not in {"ftp", "https"}:
        raise ValueError("unsupported package URL")
    path = parsed.path
    legacy_prefix = "/pub/pmc/oa_package/"
    if path.startswith(legacy_prefix):
        path = path.replace(legacy_prefix, "/pub/pmc/deprecated/oa_package/", 1)
    return urllib.parse.urlunparse(("https", parsed.netloc, path, "", "", ""))


def _candidate_pages() -> list[Candidate]:
    candidates: list[Candidate] = []
    params = {"from": "2025-01-01", "until": "2025-12-31", "format": "pdf"}
    while len(candidates) < 5000:
        url = f"{OA_URL}?{urllib.parse.urlencode(params)}"
        root = ET.fromstring(_request_bytes(url, maximum=8 * 1024 * 1024))
        service_error = root.findtext(".//error")
        if service_error:
            raise RuntimeError(f"PMC OA service rejected the request: {service_error}")
        for record in root.findall(".//record"):
            if record.get("retracted") == "yes":
                continue
            license_type = (record.get("license") or "").strip()
            if license_type not in ALLOWED_LICENSES:
                continue
            package = next(
                (
                    link.get("href")
                    for link in record.findall("link")
                    if link.get("format") == "tgz"
                ),
                None,
            )
            pmcid = (record.get("id") or "").strip()
            if not package or not pmcid.startswith("PMC"):
                continue
            candidates.append(
                Candidate(
                    pmcid=pmcid,
                    citation=(record.get("citation") or pmcid).strip(),
                    license_type=license_type,
                    package_url=_https_url(package),
                )
            )
        token_node = root.find(".//resumption")
        token = token_node.get("token") if token_node is not None else None
        if not token:
            break
        params = {"resumptionToken": token}
    return sorted(
        {item.pmcid: item for item in candidates}.values(), key=lambda item: int(item.pmcid[3:])
    )


def _pdf_from_package(candidate: Candidate) -> bytes:
    archive = _request_bytes(candidate.package_url, maximum=MAX_PACKAGE_BYTES)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        members = sorted(
            (
                member
                for member in package.getmembers()
                if member.isfile() and member.name.casefold().endswith(".pdf")
            ),
            key=lambda member: (member.size, member.name),
        )
        for member in members:
            if member.size <= 0 or member.size > MAX_PDF_BYTES:
                continue
            extracted = package.extractfile(member)
            if extracted is None:
                continue
            payload = extracted.read(MAX_PDF_BYTES + 1)
            if len(payload) <= MAX_PDF_BYTES and payload.startswith(b"%PDF"):
                return payload
    raise ValueError("package did not contain a bounded PDF")


def _write_manifest(runtime: Path, selected: list[Candidate]) -> Path:
    corpus_dir = runtime / "corpus"
    papers_dir = runtime / "papers"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    papers_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "license_policy.md").write_text(
        "# M12 PMC OA License Policy\n\n"
        "Every included item was discovered through the official PMC OA Web Service, "
        "was not marked retracted, and carried a machine-readable CC0, CC BY, CC BY-SA, "
        "or CC BY-ND license. Packages were retrieved through the PMC OA dataset service.\n",
        encoding="utf-8",
    )
    with (corpus_dir / "sources.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in selected:
            writer.writerow(
                {
                    "source_id": candidate.pmcid.casefold(),
                    "title": candidate.citation,
                    "other_identifier": candidate.pmcid,
                    "source_url": f"https://pmc.ncbi.nlm.nih.gov/articles/{candidate.pmcid}/",
                    "pdf_url": candidate.package_url,
                    "local_path": f"{candidate.pmcid}.pdf",
                    "access_date": "2026-07-18",
                    "license_type": candidate.license_type,
                    "license_url": LICENSE_URLS[candidate.license_type],
                    "usage_status": "approved_open_access",
                    "inclusion_status": "included",
                    "inclusion_reason": (
                        "PMC OA dataset record with machine-readable reuse license."
                    ),
                    "source_type": "paper",
                    "notes": "Ephemeral M12 rehearsal input; PDF and database are not committed.",
                }
            )
    corpus = {
        "manifest_version": 1,
        "corpus_id": "m12_pmc_oa_rehearsal",
        "name": "M12 PMC Open Access 100-Paper Rehearsal",
        "description": (
            "Ephemeral controlled corpus selected from the official PMC OA dataset service."
        ),
        "scientific_domain": "biomedical science",
        "research_question": {
            "question_id": "q_m12_ingestion_rehearsal",
            "text": (
                "Can the current ingestion system process a controlled real 100-paper corpus "
                "reproducibly?"
            ),
        },
        "created_at": "2026-07-18",
        "updated_at": "2026-07-18",
        "license_policy": "license_policy.md",
        "source_manifest": "sources.csv",
        "default_local_papers_directory": ".m12-runtime/papers",
        "notes": "Runtime-only rehearsal manifest; source PDFs are discarded with the runner.",
    }
    corpus_path = corpus_dir / "corpus.json"
    corpus_path.write_text(json.dumps(corpus, indent=2) + "\n", encoding="utf-8")
    return corpus_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    runtime = workspace / ".m12-runtime"
    if runtime.exists():
        shutil.rmtree(runtime)
    (runtime / "papers").mkdir(parents=True)

    selected: list[Candidate] = []
    failures: Counter[str] = Counter()
    for candidate in _candidate_pages():
        if len(selected) == args.count:
            break
        try:
            payload = _pdf_from_package(candidate)
            (runtime / "papers" / f"{candidate.pmcid}.pdf").write_bytes(payload)
            selected.append(candidate)
            print(f"selected {len(selected):03d}/{args.count}: {candidate.pmcid}", flush=True)
        except urllib.error.HTTPError as exc:
            failures[f"http_{exc.code}"] += 1
        except (OSError, ValueError, tarfile.TarError) as exc:
            failures[type(exc).__name__] += 1
        time.sleep(0.05)
    if len(selected) != args.count:
        failure_summary = ", ".join(f"{key}={value}" for key, value in sorted(failures.items()))
        raise RuntimeError(
            f"selected {len(selected)} usable PDFs; required {args.count}; failures: "
            f"{failure_summary or 'none'}"
        )

    corpus_path = _write_manifest(runtime, selected)
    relative_corpus_path = corpus_path.relative_to(workspace)
    evidence = {
        "corpus_path": str(relative_corpus_path),
        "selected_count": len(selected),
        "licenses": sorted({candidate.license_type for candidate in selected}),
        "selection_failures": dict(sorted(failures.items())),
        "source_service": OA_URL,
    }
    (runtime / "preparation-evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(relative_corpus_path)


if __name__ == "__main__":
    main()
