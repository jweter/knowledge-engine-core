import sqlite3

import pytest
from sqlalchemy.exc import OperationalError

from knowledge_engine.paper_persistence import _classify_operational_error
from knowledge_engine.persistence_errors import (
    DatabaseIOError,
    DatabaseUnavailableError,
    RelationalWriteError,
    SearchIndexWriteError,
)


def operational_error(message: str) -> OperationalError:
    return OperationalError("statement", {}, sqlite3.OperationalError(message))


@pytest.mark.parametrize(
    "message",
    [
        "database is locked",
        "database is busy",
        "unable to open database file",
    ],
)
def test_operational_unavailable_failures_are_classified_without_raw_details(
    message: str,
) -> None:
    error = _classify_operational_error(operational_error(message), stage="relational")

    assert isinstance(error, DatabaseUnavailableError)
    assert message not in str(error)


@pytest.mark.parametrize(
    "message",
    [
        "disk I/O error",
        "attempt to write a readonly database",
        "database or disk is full",
    ],
)
def test_operational_io_failures_are_classified_without_raw_details(message: str) -> None:
    error = _classify_operational_error(operational_error(message), stage="relational")

    assert isinstance(error, DatabaseIOError)
    assert message.lower() not in str(error).lower()


def test_unknown_relational_operational_failure_stays_relational() -> None:
    error = _classify_operational_error(
        operational_error("some stable but unclassified database condition"),
        stage="relational",
    )

    assert isinstance(error, RelationalWriteError)


def test_unknown_search_index_operational_failure_stays_search_index_specific() -> None:
    error = _classify_operational_error(
        operational_error("some stable but unclassified database condition"),
        stage="search_index",
    )

    assert isinstance(error, SearchIndexWriteError)
