import pytest

from knowledge_engine.import_runs.cli_modes import resolve_corpus_import_mode


def test_fresh_mode_has_no_parent() -> None:
    resolved = resolve_corpus_import_mode(resume_from=None, retry_failed_from=None)
    assert resolved.mode is None
    assert resolved.parent_import_run_id is None
    assert resolved.is_linked is False


def test_resume_mode_selects_parent() -> None:
    resolved = resolve_corpus_import_mode(resume_from=" run-a ", retry_failed_from=None)
    assert resolved.mode == "resume"
    assert resolved.parent_import_run_id == "run-a"
    assert resolved.is_linked is True


def test_retry_mode_selects_parent() -> None:
    resolved = resolve_corpus_import_mode(resume_from=None, retry_failed_from=" run-b ")
    assert resolved.mode == "retry_failed"
    assert resolved.parent_import_run_id == "run-b"
    assert resolved.is_linked is True


def test_parent_options_cannot_be_combined() -> None:
    with pytest.raises(ValueError):
        resolve_corpus_import_mode(resume_from="run-a", retry_failed_from="run-b")


@pytest.mark.parametrize("value", ["", "   "])
def test_blank_parent_identifier_is_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        resolve_corpus_import_mode(resume_from=value, retry_failed_from=None)
