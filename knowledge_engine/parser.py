"""PDF parsing for Phase 0 ingestion."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz
from pydantic import BaseModel, Field

from knowledge_engine.utils import count_words, file_sha256, normalize_whitespace

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
REFERENCE_HEADING_PATTERN = re.compile(r"(?im)^\s*(?:references|bibliography|literature cited)\s*$")
PATENT_TITLE_PATTERN = re.compile(
    r"(?is)\(54\)\s*Title:\s*(.*?)(?:\n\s*\n\s*\(57\)|\n\s*\n\s*Abstract\b)"
)
GENERIC_TITLE_LINES = {
    "abstract",
    "article",
    "articles",
    "general relativity",
    "original article",
    "research article",
    "review",
    "reviews",
}


class DocumentParseError(Exception):
    """Expected, recoverable failure while parsing one declared document."""


class UnsupportedDocumentError(DocumentParseError):
    """The declared document type is not supported by the active parser."""


class MalformedDocumentError(DocumentParseError):
    """The declared document is unreadable as a structurally valid PDF."""


class ParsedPaper(BaseModel):
    """Structured result returned by a document parser."""

    source_path: Path
    content_hash: str
    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    doi: str | None = None
    page_count: int
    word_count: int
    raw_text: str
    body_text: str


class DocumentParser:
    """Interface for document parsers."""

    def parse(self, path: Path) -> ParsedPaper:
        """Parse a document into normalized metadata and text.

        Implementations raise ``DocumentParseError`` only for expected document-level
        failures. Programming defects and unexpected dependency failures must propagate.
        """

        raise NotImplementedError


class PyMuPDFParser(DocumentParser):
    """Extract text and best-effort metadata from PDFs using PyMuPDF."""

    def parse(self, path: Path) -> ParsedPaper:
        """Parse a PDF file."""

        pdf_path = path.expanduser().resolve()
        if not pdf_path.exists():
            msg = f"PDF not found: {pdf_path}"
            raise FileNotFoundError(msg)
        if pdf_path.suffix.lower() != ".pdf":
            msg = f"Only PDF files are supported in Phase 0: {pdf_path}"
            raise UnsupportedDocumentError(msg)

        try:
            with fitz.open(pdf_path) as document:
                if document.needs_pass:
                    msg = "The PDF is encrypted and requires a password."
                    raise MalformedDocumentError(msg)
                page_texts = [page.get_text("text") for page in document]
                metadata = document.metadata or {}
                page_count = document.page_count
        except fitz.FileDataError as exc:
            raise MalformedDocumentError("The PDF structure could not be parsed.") from exc

        raw_text = normalize_whitespace("\n\n".join(page_texts))
        title = self._extract_title(metadata, raw_text, pdf_path)
        authors = self._extract_authors(metadata)
        abstract = self._extract_abstract(raw_text)
        doi = self._extract_doi(raw_text)
        body_text = self._extract_body_text(raw_text, abstract)

        return ParsedPaper(
            source_path=pdf_path,
            content_hash=file_sha256(pdf_path),
            title=title,
            authors=authors,
            abstract=abstract,
            doi=doi,
            page_count=page_count,
            word_count=count_words(raw_text),
            raw_text=raw_text,
            body_text=body_text,
        )

    def _extract_title(self, metadata: dict[str, str], raw_text: str, path: Path) -> str:
        metadata_title = (metadata.get("title") or "").strip()
        if metadata_title.lower() not in {"untitled", "none"} and self._is_title_candidate(
            metadata_title
        ):
            return metadata_title

        patent_match = PATENT_TITLE_PATTERN.search(raw_text)
        if patent_match:
            patent_title = normalize_whitespace(patent_match.group(1))
            if patent_title:
                return patent_title

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for index, candidate in enumerate(lines):
            if not self._is_title_candidate(candidate):
                continue
            if index + 1 < len(lines) and self._is_wrapped_title_continuation(
                candidate, lines[index + 1]
            ):
                return f"{candidate} {lines[index + 1]}"
            return candidate
        return path.stem.replace("_", " ").replace("-", " ").strip().title()

    def _is_title_candidate(self, candidate: str) -> bool:
        normalized = candidate.casefold().strip(" .:")
        if not 8 <= len(candidate) <= 300:
            return False
        if not re.search(r"[A-Za-z]", candidate):
            return False
        if DOI_PATTERN.search(candidate):
            return False
        if normalized in GENERIC_TITLE_LINES:
            return False
        if re.match(r"^\(\d{2}\)\s", candidate):
            return False
        if re.match(r"^(?:pii|issn|isbn)\s*:", candidate, re.IGNORECASE):
            return False
        if candidate.isupper() and len(candidate.split()) <= 6:
            return False
        return True

    def _is_wrapped_title_continuation(self, candidate: str, next_line: str) -> bool:
        if not self._is_title_candidate(next_line):
            return False
        first_character = next_line.lstrip()[0]
        if first_character.islower() or first_character in {"£", "β", "γ"}:
            return True
        final_word = candidate.rstrip(" .:;-").split()[-1].casefold()
        return final_word in {"a", "an", "and", "for", "in", "of", "on", "or", "the", "to", "with"}

    def _extract_authors(self, metadata: dict[str, str]) -> list[str]:
        author_text = (metadata.get("author") or "").strip()
        if not author_text:
            return []
        pieces = re.split(r";|,|\band\b", author_text)
        return [piece.strip() for piece in pieces if piece.strip()]

    def _extract_abstract(self, raw_text: str) -> str | None:
        match = re.search(
            r"(?is)\babstract\b[:\s]*(.*?)(?:\n\s*(?:keywords?|introduction|1\.?\s+introduction)\b)",
            raw_text,
        )
        if not match:
            return None
        abstract = normalize_whitespace(match.group(1))
        return abstract[:5000] if abstract else None

    def _extract_doi(self, raw_text: str) -> str | None:
        reference_heading = REFERENCE_HEADING_PATTERN.search(raw_text)
        identity_text = raw_text[: reference_heading.start()] if reference_heading else raw_text
        identity_match = DOI_PATTERN.search(identity_text)
        if identity_match:
            return identity_match.group(0).rstrip(".")

        matches = [match.group(0).rstrip(".") for match in DOI_PATTERN.finditer(raw_text)]
        normalized_counts = Counter(match.casefold() for match in matches)
        repeated = [match for match, count in normalized_counts.items() if count >= 2]
        if len(repeated) == 1:
            repeated_doi = repeated[0]
            return next(match for match in matches if match.casefold() == repeated_doi)
        return None

    def _extract_body_text(self, raw_text: str, abstract: str | None) -> str:
        if abstract:
            return raw_text.replace(abstract, "", 1).strip()
        return raw_text
