from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.mesh_lookup import MeshLookupResult
from knowledge_engine.rxnorm_lookup import RxNormLookupError, RxNormLookupResult


def _unwrapped(output: str) -> str:
    """Collapse Rich's line-wrapping so substring assertions survive it."""

    return " ".join(output.split())


class FakeRxNormService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def lookup(self, term: str) -> RxNormLookupResult:
        self.calls.append(term)
        if self.error is not None:
            raise self.error
        return RxNormLookupResult(
            term=term,
            found=True,
            rxcui="1991302",
            name="semaglutide",
            term_type="IN",
            synonym=None,
            ingredients=(),
            source_url="https://rxnav.nlm.nih.gov/REST/rxcui/1991302",
            license="Free, non-proprietary content (RxNorm, National Library of Medicine)",
            retrieved_at="2026-07-29T00:00:00+00:00",
        )


class FakeMeshService:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[str] = []

    def lookup(self, term: str) -> MeshLookupResult:
        self.calls.append(term)
        if self.error is not None:
            raise self.error
        return MeshLookupResult(
            term=term,
            found=True,
            mesh_id="D009765",
            heading="Obesity",
            scope_note="An excessive amount of adipose tissue in the body.",
            synonyms=("Obesities",),
            source_url="https://id.nlm.nih.gov/mesh/D009765",
            license="Free, non-proprietary content, National Library of Medicine (MeSH)",
            retrieved_at="2026-07-29T00:00:00+00:00",
        )


def _draft_item(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": None,
        "research_question": None,
        "evidence_direction": None,
        "population": "Adults with obesity",
        "intervention": "Semaglutide",
        "comparator": None,
        "outcome": None,
    }
    record.update(overrides)
    return record


def _write_input(tmp_path: Path, *items: dict[str, object]) -> Path:
    input_path = tmp_path / "draft.jsonl"
    input_path.write_text("\n".join(json.dumps(item) for item in items) + "\n", encoding="utf-8")
    return input_path


def test_annotate_writes_annotated_output_with_reference_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: rxnorm)
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: mesh)
    input_path = _write_input(tmp_path, _draft_item())
    output_path = tmp_path / "annotated.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    written = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(written) == 1
    context = written[0]["reference_context"]
    assert context["intervention"]["rxcui"] == "1991302"
    assert context["population"]["mesh_id"] == "D009765"
    assert context["comparator"] is None
    assert context["outcome"] is None
    unwrapped = _unwrapped(result.output)
    assert "Network access:" in unwrapped
    assert "Annotated 1 draft item" in unwrapped
    assert "not evidence" in unwrapped


def test_annotate_rejects_a_missing_input_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-annotate",
            "--input",
            str(tmp_path / "missing.jsonl"),
            "--output",
            str(tmp_path / "out.jsonl"),
        ],
    )

    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_annotate_rejects_an_existing_output_without_force(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())
    input_path = _write_input(tmp_path, _draft_item())
    output_path = tmp_path / "annotated.jsonl"
    output_path.write_text("existing", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_annotate_reports_no_items_for_an_empty_input_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())
    input_path = tmp_path / "draft.jsonl"
    input_path.write_text("", encoding="utf-8")
    output_path = tmp_path / "annotated.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert "No draft items found" in result.output
    assert output_path.read_text(encoding="utf-8") == ""


def test_annotate_clears_a_stale_output_when_a_rerun_finds_no_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prior run's annotated records must not linger and look current."""

    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())
    input_path = tmp_path / "draft.jsonl"
    input_path.write_text("", encoding="utf-8")
    output_path = tmp_path / "annotated.jsonl"
    output_path.write_text(json.dumps(_draft_item()) + "\n", encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "extraction-review-annotate",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    assert output_path.read_text(encoding="utf-8") == ""


def test_annotate_rejects_an_invalid_json_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: FakeRxNormService())
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())
    input_path = tmp_path / "draft.jsonl"
    input_path.write_text("not json\n", encoding="utf-8")
    output_path = tmp_path / "annotated.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "invalid JSON" in result.output


def test_annotate_exits_nonzero_on_lookup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        entrypoint,
        "RxNormLookupService",
        lambda transport: FakeRxNormService(error=RxNormLookupError("boom")),
    )
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: FakeMeshService())
    input_path = _write_input(tmp_path, _draft_item())
    output_path = tmp_path / "annotated.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "Reference-layer annotation failed" in result.output
    assert not output_path.exists()


def test_annotate_caches_terms_across_items_in_one_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rxnorm = FakeRxNormService()
    mesh = FakeMeshService()
    monkeypatch.setattr(entrypoint, "RxNormLookupService", lambda transport: rxnorm)
    monkeypatch.setattr(entrypoint, "MeshLookupService", lambda transport: mesh)
    input_path = _write_input(tmp_path, _draft_item(), _draft_item())
    output_path = tmp_path / "annotated.jsonl"

    result = CliRunner().invoke(
        entrypoint.app,
        ["extraction-review-annotate", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert rxnorm.calls.count("Semaglutide") == 1
    assert mesh.calls.count("obesity") == 1
    assert mesh.calls.count("Adults") == 1
