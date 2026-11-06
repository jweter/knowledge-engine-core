from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.online_evidence import (
    OnlineEvidenceBundle,
    RetrievalStatus,
    verify_against_retrieved_content,
)
from knowledge_engine.online_golden import (
    GOLDEN_BUNDLE_NAME,
    GOLDEN_CONTENTS_DIR,
    build_golden_bundle,
    render_golden_bundle,
    write_golden_fixture,
)

FIXTURE = Path(__file__).parent / "fixtures" / "online_evidence"

# The consumer contract: field name -> accepted JSON types. Additive fields are allowed.
TOP_LEVEL = {"schema": str, "question": str, "sources": list, "excerpts": list, "claims": list}
SOURCE = {
    "source_id": str,
    "url": str,
    "retrieved_at": str,
    "status": str,
    "provider": str,
    "title": (str, type(None)),
    "doi": (str, type(None)),
    "pmcid": (str, type(None)),
    "pmid": (str, type(None)),
    "arxiv_id": (str, type(None)),
    "content_sha256": (str, type(None)),
    "failure_reason": (str, type(None)),
    "license": (str, type(None)),
}
EXCERPT = {
    "excerpt_id": str,
    "source_id": str,
    "text": str,
    "char_start": (int, type(None)),
    "char_end": (int, type(None)),
    "locator": (str, type(None)),
}
CLAIM = {"claim_id": str, "text": str, "status": str, "citations": list}
CITATION = {"excerpt_id": str, "stance": str}


def _load() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURE / GOLDEN_BUNDLE_NAME).read_text("utf-8"))
    return payload


def _assert_fields(record: dict[str, Any], contract: dict[str, Any], where: str) -> None:
    for name, types in contract.items():
        assert name in record, f"{where}: required field {name!r} was removed or renamed"
        assert isinstance(record[name], types) and not (
            isinstance(record[name], bool) and types is not bool
        ), f"{where}.{name}: retyped to {type(record[name]).__name__}"


def test_the_golden_fixture_pins_the_consumer_field_contract() -> None:
    payload = _load()
    _assert_fields(payload, TOP_LEVEL, "bundle")
    assert payload["schema"] == "ke-online-evidence/v1"
    for source in payload["sources"]:
        _assert_fields(source, SOURCE, "source")
    for excerpt in payload["excerpts"]:
        _assert_fields(excerpt, EXCERPT, "excerpt")
    for claim in payload["claims"]:
        _assert_fields(claim, CLAIM, "claim")
        for citation in claim["citations"]:
            _assert_fields(citation, CITATION, "citation")
    assert {s["status"] for s in payload["sources"]} == {"retrieved", "failed", "unavailable"}


def test_the_builder_serialization_keeps_the_contract_fields() -> None:
    bundle, _ = build_golden_bundle()
    payload = bundle.to_dict()
    _assert_fields(payload, TOP_LEVEL, "bundle")
    for source in payload["sources"]:
        _assert_fields(source, SOURCE, "source")
    for excerpt in payload["excerpts"]:
        _assert_fields(excerpt, EXCERPT, "excerpt")


def test_additive_fields_do_not_break_a_consumer_reader() -> None:
    payload = _load()
    extended = {**payload, "future_field": 1}
    extended["sources"] = [{**s, "future_field": "x"} for s in payload["sources"]]
    extended["excerpts"] = [{**e, "future_field": "x"} for e in payload["excerpts"]]
    _assert_fields(extended, TOP_LEVEL, "bundle")
    for source in extended["sources"]:
        _assert_fields(source, SOURCE, "source")
    # Core's own reader tolerates additive top-level fields it does not know.
    assert OnlineEvidenceBundle.from_dict({**payload, "future_field": 1}) is not None


def test_the_fixture_is_regenerated_byte_identically(tmp_path: Path) -> None:
    write_golden_fixture(tmp_path)

    committed = sorted(p.relative_to(FIXTURE) for p in FIXTURE.rglob("*") if p.is_file())
    regenerated = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    assert committed == regenerated
    for relative in committed:
        assert (FIXTURE / relative).read_bytes() == (tmp_path / relative).read_bytes()
    bundle, _ = build_golden_bundle()
    assert (FIXTURE / GOLDEN_BUNDLE_NAME).read_text(encoding="utf-8") == render_golden_bundle(
        bundle
    )
    assert OnlineEvidenceBundle.from_dict(_load()) == bundle


def test_failed_and_unavailable_sources_are_never_quoted() -> None:
    bundle = OnlineEvidenceBundle.from_dict(_load())
    not_retrieved = {
        s.source_id for s in bundle.sources if s.status is not RetrievalStatus.RETRIEVED
    }

    assert len(not_retrieved) == 2
    assert not {e.source_id for e in bundle.excerpts} & not_retrieved
    for source in bundle.unavailable_sources:
        assert source.content_sha256 is None and (source.failure_reason or "").strip()


def test_the_golden_bundle_validates_offline_without_a_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the golden contract must not touch the network")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    bundle, contents = build_golden_bundle()
    assert verify_against_retrieved_content(bundle, contents) == []

    result = CliRunner().invoke(
        entrypoint.app,
        [
            "online-evidence-validate",
            str(FIXTURE / GOLDEN_BUNDLE_NAME),
            "--contents-dir",
            str(FIXTURE / GOLDEN_CONTENTS_DIR),
        ],
    )

    output = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert "Sources: 1 retrieved, 2 unavailable; excerpts: 1; claims: 2" in output
    assert "verified against retrieved content" in output
