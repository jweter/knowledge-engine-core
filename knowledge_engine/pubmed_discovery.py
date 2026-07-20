"""Review-first PubMed and PMC Open Access candidate discovery."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.parse import urlencode

from knowledge_engine.ncbi_http import TransportResponse

EUTILS_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
PMC_OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
DEFAULT_HEADERS = {
    "Accept": "application/json, application/xml",
    "User-Agent": "knowledge-engine-core/0.2",
}


class NcbiDiscoveryError(RuntimeError):
    """Sanitized provider or response failure."""


class GetTransport(Protocol):
    """Structural transport interface used by the discovery service."""

    def get(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> TransportResponse:
        """Fetch one bounded HTTPS response."""


@dataclass(frozen=True)
class PubmedCandidate:
    """One reviewable bibliographic candidate."""

    pmid: str
    title: str
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    doi: str | None
    pmcid: str | None
    open_access: bool
    license: str | None
    pdf_url: str | None
    xml_url: str | None
    status: str
    metadata_source: str
    pmcid_source: str | None
    oa_source: str | None


@dataclass(frozen=True)
class DiscoveryResult:
    """Deterministic discovery output."""

    query: str
    retstart: int
    limit: int
    candidates: tuple[PubmedCandidate, ...]

    def to_json(self) -> str:
        """Render stable, reviewable JSON."""

        payload = {
            "query": self.query,
            "retstart": self.retstart,
            "limit": self.limit,
            "candidate_count": len(self.candidates),
            "candidates": [asdict(candidate) for candidate in self.candidates],
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"


@dataclass(frozen=True)
class _PubmedMetadata:
    title: str
    authors: tuple[str, ...]
    publication_year: int | None
    venue: str | None
    doi: str | None


class PubmedPmcDiscoveryService:
    """Discover PubMed records and verify PMC OA evidence without downloading papers."""

    def __init__(
        self,
        transport: GetTransport,
        *,
        timeout_seconds: float = 20.0,
        max_response_bytes: int = 5_000_000,
    ) -> None:
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes

    def discover(self, query: str, *, limit: int, retstart: int = 0) -> DiscoveryResult:
        """Return a bounded, deterministic page of candidates."""

        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("PubMed query must not be empty.")
        if not 1 <= limit <= 100:
            raise ValueError("Discovery limit must be between 1 and 100.")
        if retstart < 0:
            raise ValueError("Discovery retstart must be non-negative.")

        pmids = self._search(normalized_query, limit=limit, retstart=retstart)
        metadata = self._fetch_metadata(pmids)
        pmc_links = self._link_pmc(pmids)

        candidates: list[PubmedCandidate] = []
        for pmid in pmids:
            record = metadata.get(pmid, _PubmedMetadata("", (), None, None, None))
            pmcid = pmc_links.get(pmid)
            oa = self._fetch_oa_record(pmcid) if pmcid else None
            candidates.append(
                PubmedCandidate(
                    pmid=pmid,
                    title=record.title,
                    authors=record.authors,
                    publication_year=record.publication_year,
                    venue=record.venue,
                    doi=record.doi,
                    pmcid=pmcid,
                    open_access=oa is not None,
                    license=oa.license if oa else None,
                    pdf_url=oa.pdf_url if oa else None,
                    xml_url=oa.xml_url if oa else None,
                    status="oa_verified" if oa else "metadata_only",
                    metadata_source="pubmed_efetch",
                    pmcid_source="pubmed_elink" if pmcid else None,
                    oa_source="pmc_oa_service" if oa else None,
                )
            )
        return DiscoveryResult(
            query=normalized_query,
            retstart=retstart,
            limit=limit,
            candidates=tuple(candidates),
        )

    def _search(self, query: str, *, limit: int, retstart: int) -> list[str]:
        body = self._get_json(
            f"{EUTILS_BASE_URL}/esearch.fcgi?"
            + urlencode(
                {
                    "db": "pubmed",
                    "term": query,
                    "retmode": "json",
                    "retmax": limit,
                    "retstart": retstart,
                    "sort": "pub_date",
                }
            )
        )
        try:
            values = body["esearchresult"]["idlist"]
        except (KeyError, TypeError) as exc:
            raise NcbiDiscoveryError("PubMed search response was malformed.") from exc
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise NcbiDiscoveryError("PubMed search response was malformed.")
        return values

    def _fetch_metadata(self, pmids: list[str]) -> dict[str, _PubmedMetadata]:
        if not pmids:
            return {}
        xml_root = self._get_xml(
            f"{EUTILS_BASE_URL}/efetch.fcgi?"
            + urlencode({"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
        )
        records: dict[str, _PubmedMetadata] = {}
        for article in xml_root.findall(".//PubmedArticle"):
            pmid = _element_text(article.find(".//PMID"))
            title = _flatten_text(article.find(".//ArticleTitle"))
            authors = tuple(
                name
                for author in article.findall(".//Article/AuthorList/Author")
                if (name := _author_name(author))
            )
            venue = _element_text(article.find(".//Article/Journal/Title")) or None
            publication_year = _publication_year(article)
            doi = None
            for article_id in article.findall(".//ArticleId"):
                if article_id.attrib.get("IdType") == "doi":
                    doi = _element_text(article_id) or None
                    break
            if pmid:
                records[pmid] = _PubmedMetadata(
                    title=title,
                    authors=authors,
                    publication_year=publication_year,
                    venue=venue,
                    doi=doi,
                )
        return records

    def _link_pmc(self, pmids: list[str]) -> dict[str, str]:
        if not pmids:
            return {}
        parameters: list[tuple[str, str]] = [
            ("dbfrom", "pubmed"),
            ("db", "pmc"),
            ("retmode", "json"),
            ("linkname", "pubmed_pmc"),
        ]
        parameters.extend(("id", pmid) for pmid in pmids)
        body = self._get_json(f"{EUTILS_BASE_URL}/elink.fcgi?" + urlencode(parameters))

        result: dict[str, str] = {}
        requested_pmids = set(pmids)
        linksets = body.get("linksets")
        if not isinstance(linksets, list):
            raise NcbiDiscoveryError("PubMed linkage response was malformed.")
        for linkset in linksets:
            if not isinstance(linkset, dict):
                raise NcbiDiscoveryError("PubMed linkage response was malformed.")
            ids = linkset.get("ids")
            databases = linkset.get("linksetdbs")
            if not isinstance(ids, list) or len(ids) != 1 or not isinstance(databases, list):
                raise NcbiDiscoveryError("PubMed linkage response was malformed.")
            pmid = str(ids[0])
            if pmid not in requested_pmids or pmid in result:
                raise NcbiDiscoveryError("PubMed linkage response did not reconcile.")
            for database in databases:
                if not isinstance(database, dict) or database.get("linkname") != "pubmed_pmc":
                    continue
                links = database.get("links")
                if not isinstance(links, list) or len(links) != 1:
                    raise NcbiDiscoveryError("PubMed linkage response was ambiguous.")
                result[pmid] = f"PMC{links[0]}"
                break
        return result

    def _fetch_oa_record(self, pmcid: str) -> _OaRecord | None:
        root = self._get_xml(f"{PMC_OA_URL}?" + urlencode({"id": pmcid}))
        matching_records = [
            record for record in root.findall(".//record") if record.attrib.get("id") == pmcid
        ]
        if not matching_records:
            return None
        if len(matching_records) != 1:
            raise NcbiDiscoveryError("PMC OA response did not reconcile.")
        record = matching_records[0]
        license_name = record.attrib.get("license") or None
        pdf_url = None
        xml_url = None
        for link in record.findall("link"):
            href = link.attrib.get("href")
            if not href:
                continue
            normalized_href = href.replace("ftp://", "https://")
            if link.attrib.get("format") == "pdf":
                pdf_url = normalized_href
            elif link.attrib.get("format") in {"tgz", "xml"}:
                xml_url = normalized_href
        return _OaRecord(license=license_name, pdf_url=pdf_url, xml_url=xml_url)

    def _get_json(self, url: str) -> dict[str, object]:
        response = self._get(url)
        try:
            value = json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise NcbiDiscoveryError("NCBI returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise NcbiDiscoveryError("NCBI returned malformed JSON.")
        return value

    def _get_xml(self, url: str) -> ET.Element:
        response = self._get(url)
        try:
            return ET.fromstring(response.body)
        except ET.ParseError as exc:
            raise NcbiDiscoveryError("NCBI returned malformed XML.") from exc

    def _get(self, url: str) -> TransportResponse:
        try:
            response = self.transport.get(
                url=url,
                headers=DEFAULT_HEADERS,
                timeout_seconds=self.timeout_seconds,
                max_response_bytes=self.max_response_bytes,
            )
        except (OSError, TimeoutError) as exc:
            raise NcbiDiscoveryError("NCBI request failed.") from exc
        if response.status_code != 200:
            raise NcbiDiscoveryError("NCBI request returned a non-success status.")
        return response


@dataclass(frozen=True)
class _OaRecord:
    license: str | None
    pdf_url: str | None
    xml_url: str | None


def _author_name(author: ET.Element) -> str:
    collective = _element_text(author.find("CollectiveName"))
    if collective:
        return collective
    fore = _element_text(author.find("ForeName"))
    last = _element_text(author.find("LastName"))
    return " ".join(part for part in (fore, last) if part)


def _publication_year(article: ET.Element) -> int | None:
    for path in (
        ".//Article/Journal/JournalIssue/PubDate/Year",
        ".//ArticleDate/Year",
        ".//PubMedPubDate[@PubStatus='pubmed']/Year",
    ):
        value = _element_text(article.find(path))
        if value.isdigit() and len(value) == 4:
            return int(value)
    medline_date = _element_text(
        article.find(".//Article/Journal/JournalIssue/PubDate/MedlineDate")
    )
    if len(medline_date) >= 4 and medline_date[:4].isdigit():
        return int(medline_date[:4])
    return None


def _element_text(element: ET.Element | None) -> str:
    return "" if element is None or element.text is None else element.text.strip()


def _flatten_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())
