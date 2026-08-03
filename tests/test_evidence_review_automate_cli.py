from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.config import Settings
from knowledge_engine.database import Database, PaperRepository
from knowledge_engine.extraction import LLM_GROUNDED_PICO_RULES_VERSION
from knowledge_engine.parser import ParsedPage, ParsedPaper

_PAGE_TEXT = (
    "A total of 318 participants were enrolled. Participants received "
    "SiPore21 or a matching placebo for 12 weeks. SiPore21 significantly "
    "reduced HbA1c from baseline (p=0.0036)."
)


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


def _database(tmp_path: Path) -> Database:
    database = Database(
        Settings(
            project_root=tmp_path,
            data_dir=tmp_path / "data",
            database_url=f"sqlite:///{tmp_path / 'source'}.sqlite3",
        )
    )
    database.initialize()
    parsed = ParsedPaper(
        source_path=tmp_path / "paper.pdf",
        content_hash="a" * 64,
        title="A SiPore21 trial",
        doi="10.1000/sipore21",
        page_count=1,
        word_count=len(_PAGE_TEXT.split()),
        raw_text=_PAGE_TEXT,
        body_text=_PAGE_TEXT,
        pages=[ParsedPage(page_number=1, text=_PAGE_TEXT)],
    )
    with database.session() as session:
        PaperRepository(session).add_parsed_paper(parsed)
    return database


class _FakeLLM:
    def __init__(self, *, model: str, host: str) -> None:
        self.model = model
        self.host = host

    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        return (
            '{"population": "A total of 318 participants were enrolled.", '
            '"intervention": "Participants received SiPore21 or a matching placebo '
            'for 12 weeks.", "comparator": "", "outcome": ""}'
        )


def _automated_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": "auto-cli-001",
        "extraction_method": "m52-evidence-classification-v1",
        "claim_text": "SiPore21 significantly reduced HbA1c from baseline (p=0.0036).",
        "population": "ARTICLE HISTORY boilerplate glued on by mistake.",
        "intervention": "ARTICLE HISTORY boilerplate glued on by mistake.",
        "comparator": None,
        "outcome": None,
        "source_span": {"paper_id": 1, "page_number": 1, "section": "results"},
        "review_checklist": {},
    }
    record.update(overrides)
    return record


def test_evidence_review_automate_grounds_fields_and_rewrites_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeLLM)

    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(json.dumps(_automated_record()) + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-automate",
            "--evidence",
            str(evidence_path),
            "--model",
            "fake-model",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _unwrapped(result.output)
    assert "grounded" in output
    assert "Updated 1 record" in output

    updated = json.loads(evidence_path.read_text(encoding="utf-8").strip())
    assert updated["extraction_method"] == LLM_GROUNDED_PICO_RULES_VERSION
    assert updated["population"] == "A total of 318 participants were enrolled."
    assert updated["intervention"] == (
        "Participants received SiPore21 or a matching placebo for 12 weeks."
    )
    assert updated["review_checklist"]["llm_grounded"] is True
    assert updated["review_checklist"]["human_reviewed"] is False


def test_evidence_review_automate_dry_run_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeLLM)

    evidence_path = tmp_path / "evidence_records.jsonl"
    original_content = json.dumps(_automated_record()) + "\n"
    evidence_path.write_text(original_content, encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-automate",
            "--evidence",
            str(evidence_path),
            "--model",
            "fake-model",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Dry run" in _unwrapped(result.output)
    assert evidence_path.read_text(encoding="utf-8") == original_content


def test_evidence_review_automate_skips_an_already_manually_reviewed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeLLM)

    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(
        json.dumps(_automated_record(extraction_method="manual_human_review")) + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-automate",
            "--evidence",
            str(evidence_path),
            "--model",
            "fake-model",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Automated records still eligible: 0" in _unwrapped(result.output)


def test_evidence_review_automate_skips_a_human_reviewed_checklist_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record can be human-reviewed while keeping an older automated
    `extraction_method` as provenance -- `review_checklist.human_reviewed`
    is what actually marks it reviewed. The CLI's eligibility filter must
    honor that, not just the literal `extraction_method` value."""

    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeLLM)

    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(
        json.dumps(
            _automated_record(
                extraction_method="m52-evidence-classification-v1",
                review_checklist={"human_reviewed": True},
            )
        )
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-automate",
            "--evidence",
            str(evidence_path),
            "--model",
            "fake-model",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Automated records still eligible: 0" in _unwrapped(result.output)


def test_evidence_review_automate_requires_a_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("KE_LLM_MODEL", raising=False)
    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(json.dumps(_automated_record()) + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["evidence-review-automate", "--evidence", str(evidence_path)],
    )

    assert result.exit_code != 0
    assert "No model given" in _unwrapped(result.output)


def test_evidence_review_automate_rejects_an_unknown_evidence_record_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = _database(tmp_path)
    monkeypatch.setattr(entrypoint, "_local_database", lambda: database)
    monkeypatch.setattr(entrypoint, "OllamaLLM", _FakeLLM)

    evidence_path = tmp_path / "evidence_records.jsonl"
    evidence_path.write_text(json.dumps(_automated_record()) + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "evidence-review-automate",
            "--evidence",
            str(evidence_path),
            "--model",
            "fake-model",
            "--evidence-record-id",
            "does-not-exist",
        ],
    )

    assert result.exit_code != 0
    assert "No eligible record found" in _unwrapped(result.output)
