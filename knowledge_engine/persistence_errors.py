"""Typed expected failures for atomic paper and search-index persistence."""

from __future__ import annotations


class PaperPersistenceError(Exception):
    """Expected operational failure while persisting one parsed paper."""


class DuplicatePaperError(PaperPersistenceError):
    """A paper conflicts with an existing path, DOI, or content hash."""


class RelationalWriteError(PaperPersistenceError):
    """The relational paper write failed for an expected database reason."""


class SearchIndexWriteError(PaperPersistenceError):
    """The FTS search-index write failed for an expected database reason."""


class DatabaseUnavailableError(PaperPersistenceError):
    """The database was locked, unavailable, or otherwise temporarily inaccessible."""


class DatabaseIOError(PaperPersistenceError):
    """The database reported an expected disk or I/O failure."""
