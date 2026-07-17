"""Update legacy tests to the independent execution/review status contract."""

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"expected test block not found in {path}:\n{old}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "tests/test_cli_m10_reporting.py",
    '        run.run_status = "needs_review"\n',
    '        run.run_status = "succeeded"\n        run.review_status = "needs_review"\n',
)
replace_once(
    "tests/test_duplicate_ingestion.py",
    '    assert result.run_status == "needs_review"\n',
    '    assert result.run_status == "succeeded"\n'
    '    assert result.review_status == "needs_review"\n'
    '    assert run.review_status == "needs_review"\n',
)
replace_once(
    "tests/test_title_year_duplicate_ingestion.py",
    '    assert result.run_status == "needs_review"\n',
    '    assert result.run_status == "succeeded"\n'
    '    assert result.review_status == "needs_review"\n'
    '    assert run.review_status == "needs_review"\n',
)
