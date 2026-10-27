from knowledge_engine.corpus.validate_evidence_record import validate_evidence_record


def test_validate_evidence_record_example_1() -> None:
    assert (
        validate_evidence_record(
            {"title": "Study Title", "author": "Author Name", "year": 2020, "source": "Source Name"}
        )
        == True
    )


def test_validate_evidence_record_example_2() -> None:
    assert (
        validate_evidence_record(
            {"title": "Study Title", "author": "Author Name", "source": "Source Name"}
        )
        == False
    )


def test_validate_evidence_record_example_3() -> None:
    assert (
        validate_evidence_record(
            {
                "title": "Study Title",
                "author": "Author Name",
                "year": "2020",
                "source": "Source Name",
            }
        )
        == False
    )


def test_validate_evidence_record_example_4() -> None:
    assert (
        validate_evidence_record(
            {"title": "Study Title", "author": "Author Name", "year": 2020, "source": None}
        )
        == False
    )


def test_validate_evidence_record_example_5() -> None:
    assert (
        validate_evidence_record(
            {
                "title": "Study Title",
                "author": "Author Name",
                "year": 2020,
                "source": "Source Name",
                "additional_field": "Extra Info",
            }
        )
        == True
    )
