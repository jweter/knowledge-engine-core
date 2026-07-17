from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.metadata_enrichment import (
    MetadataCandidate,
    MetadataProviderResult,
    MetadataQuery,
    ProviderDiagnostic,
)


class FakeProvider:
    name = "crossref"

    def __init__(self, result: MetadataProviderResult) -> None:
        self.result = result
        self.queries: list[MetadataQuery] = []

    def lookup(self, query: MetadataQuery) -> MetadataProviderResult:
        self.queries.append(query)
        return self.result


def test_metadata_preview_displays_network_notice_before_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = MetadataCandidate(
        provider="crossref",
        provider_record_id="10.1000/example",
        queried_identifier="10.1000/example",
        field="title",
        value="Example Paper",
        normalized_value="example paper",
        retrieved_at=datetime(2026, 7, 18, tzinfo=UTC),
    )
    provider = FakeProvider(MetadataProviderResult(candidates=(candidate,)))
    monkeypatch.setattr(entrypoint, "_crossref_provider", lambda: provider)

    result = CliRunner().invoke(
        entrypoint.app,
        ["metadata-preview", "--doi", "https://doi.org/10.1000/example"],
    )

    assert result.exit_code == 0
    assert result.output.index("Network access:") < result.output.index(
        "External metadata candidates"
    )
    assert "Example Paper" in result.output
    assert "no metadata was persisted or promoted" in result.output
    assert provider.queries[0].normalized_doi == "10.1000/example"


def test_metadata_preview_distinguishes_no_match(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = FakeProvider(
        MetadataProviderResult(
            diagnostics=(
                ProviderDiagnostic(
                    provider="crossref",
                    code="no_match",
                    message="Crossref did not return a record for this DOI.",
                ),
            )
        )
    )
    monkeypatch.setattr(entrypoint, "_crossref_provider", lambda: provider)

    result = CliRunner().invoke(
        entrypoint.app,
        ["metadata-preview", "--doi", "10.1000/missing"],
    )

    assert result.exit_code == 0
    assert "No match:" in result.output
    assert "Provider failure" not in result.output


def test_metadata_preview_distinguishes_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeProvider(
        MetadataProviderResult(
            diagnostics=(
                ProviderDiagnostic(
                    provider="crossref",
                    code="rate_limited",
                    message="Crossref rate limit was reached.",
                    retryable=True,
                ),
            )
        )
    )
    monkeypatch.setattr(entrypoint, "_crossref_provider", lambda: provider)

    result = CliRunner().invoke(
        entrypoint.app,
        ["metadata-preview", "--doi", "10.1000/example"],
    )

    assert result.exit_code == 1
    assert "Provider failure (rate_limited)" in result.output
    assert "Retry may" in result.output
    assert "succeed later." in result.output


def test_metadata_preview_rejects_unknown_provider_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fail_if_called() -> FakeProvider:
        nonlocal called
        called = True
        raise AssertionError("provider factory must not be called")

    monkeypatch.setattr(entrypoint, "_crossref_provider", fail_if_called)

    result = CliRunner().invoke(
        entrypoint.app,
        ["metadata-preview", "--doi", "10.1000/example", "--provider", "other"],
    )

    assert result.exit_code != 0
    assert "Unsupported metadata provider" in result.output
    assert "Network access:" not in result.output
    assert called is False


def test_default_corpus_import_does_not_build_metadata_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus_path = _write_blocked_corpus(tmp_path)
    monkeypatch.chdir(tmp_path)
    called = False

    def fail_if_called() -> FakeProvider:
        nonlocal called
        called = True
        raise AssertionError("offline corpus import must not build a metadata provider")

    monkeypatch.setattr(entrypoint, "_crossref_provider", fail_if_called)

    result = CliRunner().invoke(entrypoint.app, ["corpus-import", str(corpus_path)])

    assert result.exit_code == 1
    assert "Network access:" not in result.output
    assert called is False


def _write_blocked_corpus(tmp_path: Path) -> Path:
    (tmp_path / "knowledge_engine").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname='test'\n", encoding="utf-8")
    corpus_dir = tmp_path / "data" / "corpora" / "metadata_preview"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "license_policy.md").write_text("# License\n", encoding="utf-8")
    (tmp_path / "papers" / "corpora" / "metadata_preview").mkdir(parents=True)
    corpus = {
        "manifest_version": 1,
        "corpus_id": "metadata_preview",
        "name": "Metadata Preview Corpus",
        "description": "Proves normal import remains offline.",
        "scientific_domain": "test science",
        "research_question": {"question_id": "q_preview", "text": "Does import stay offline?"},
        "created_at": "2026-07-18",
        "updated_at": "2026-07-18",
        "license_policy": "license_policy.md",
        "source_manifest": "sources.csv",
        "default_local_papers_directory": "papers/corpora/metadata_preview",
    }
    corpus_path = corpus_dir / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    (corpus_dir / "sources.csv").write_text(
        "source_id,title,usage_status,inclusion_status,source_url,access_date,"
        "inclusion_reason,license_type,license_url,local_path\n"
        "source-1,Paper,needs_legal_review,included,https://example.test/paper,2026-07-18,"
        "Relevant,unknown,,paper.pdf\n",
        encoding="utf-8",
    )
    return corpus_path
