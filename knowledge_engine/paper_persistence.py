"""Classified atomic persistence for parsed papers."""

from __future__ import annotations

from sqlalchemy.exc import DatabaseError, IntegrityError, OperationalError

from knowledge_engine.database import PaperRepository
from knowledge_engine.models import Paper, PaperAuthor, PaperKeyword, PaperText
from knowledge_engine.parser import ParsedPaper
from knowledge_engine.persistence_errors import (
    DatabaseIOError,
    DatabaseUnavailableError,
    DuplicatePaperError,
    RelationalWriteError,
    SearchIndexWriteError,
)


class ClassifiedPaperRepository(PaperRepository):
    """Persist papers while exposing narrow expected operational failure types."""

    def add_parsed_paper(self, parsed: ParsedPaper, keywords: list[str] | None = None) -> Paper:
        """Store one paper and classify expected relational and FTS failures."""

        paper = Paper(
            title=parsed.title,
            doi=parsed.doi,
            abstract=parsed.abstract,
            source_path=str(parsed.source_path),
            content_hash=parsed.content_hash,
            page_count=parsed.page_count,
            word_count=parsed.word_count,
        )
        paper.text = PaperText(raw_text=parsed.raw_text, body_text=parsed.body_text)
        self.session.add(paper)

        with self.session.no_autoflush:
            for position, author_name in enumerate(parsed.authors):
                author = self._get_or_create_author(author_name)
                author_link = PaperAuthor(author=author, position=position)
                paper.author_links.append(author_link)
                self.session.add(author_link)

            for keyword_value in keywords or []:
                keyword = self._get_or_create_keyword(keyword_value)
                keyword_link = PaperKeyword(keyword=keyword)
                paper.keyword_links.append(keyword_link)
                self.session.add(keyword_link)

        try:
            self.session.flush()
        except IntegrityError as exc:
            raise DuplicatePaperError("A paper identity constraint was violated.") from exc
        except OperationalError as exc:
            raise _classify_operational_error(exc, stage="relational") from exc
        except DatabaseError as exc:
            raise RelationalWriteError("The relational paper write failed.") from exc

        try:
            self.upsert_search_index(paper)
        except OperationalError as exc:
            raise _classify_operational_error(exc, stage="search_index") from exc
        except DatabaseError as exc:
            raise SearchIndexWriteError("The search-index write failed.") from exc
        return paper


def _classify_operational_error(
    exc: OperationalError,
    *,
    stage: str,
) -> DatabaseUnavailableError | DatabaseIOError | RelationalWriteError | SearchIndexWriteError:
    """Map stable SQLite operational categories without exposing raw messages."""

    message = str(exc.orig).lower()
    if "locked" in message or "busy" in message or "unable to open database" in message:
        return DatabaseUnavailableError("The database is temporarily unavailable.")
    if "disk i/o" in message or "readonly" in message or "database or disk is full" in message:
        return DatabaseIOError("The database reported an I/O failure.")
    if stage == "search_index":
        return SearchIndexWriteError("The search-index write failed.")
    return RelationalWriteError("The relational paper write failed.")
