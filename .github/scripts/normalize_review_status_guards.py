"""Normalize temporary truth-table guard syntax before applying the patch."""

from pathlib import Path

path = Path(".github/scripts/apply_review_status.py")
text = path.read_text(encoding="utf-8")
text = text.replace("pytest.param(", "(")
text = text.replace(', id="review-only")', ")")
text = text.replace(', id="imported-and-review")', ")")
text = text.replace(', id="counts-do-not-change-review-precedence")', ")")
text = text.replace(', id="review-does-not-change-execution")', ")")
text = text.replace("5, 0, 3", "3, 0, 2")
path.write_text(text, encoding="utf-8")
