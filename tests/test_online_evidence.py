from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import knowledge_engine.entrypoint as entrypoint
from knowledge_engine.federated_discovery import ProviderObservation
from knowledge_engine.online_evidence import (
    Citation,
    ClaimStatus,
    EvidenceClaim,
    EvidenceExcerpt,
    EvidenceStance,
    OnlineEvidenceBundle,
    OnlineEvidenceError,
    OnlineSource,
    RetrievalStatus,
    content_sha256,
    source_id_for,
    verify_against_retrieved_content,
)

RETRIEVED_AT = "2026-10-31T15:00:00+00:00"
TRIAL_TEXT = (
    "Results. Mean change in body weight from baseline to week 104 was -15.2% with "
    "semaglutide and -2.6% with placebo."
)
NULL_TEXT = "Results. No difference in body weight was observed between groups at week 52."


def _observation(**overrides: object) -> ProviderObservation:
    fields: dict[str, object] = {
        "provider": "Europe PMC",
        "provider_id": "PMC9999999",
        "title": "Two-year effects of semaglutide",
        "doi": "https://doi.org/10.1038/S41591-022-02026-4",
        "pmcid": "PMC9999999",
        "license": "cc-by",
    }
    fields.update(overrides)
    return ProviderObservation(**fields)  # type: ignore[arg-type]


def _retrieved(content: str = TRIAL_TEXT, **overrides: object) -> OnlineSource:
    return OnlineSource.from_observation(
        _observation(**overrides),
        url="https://europepmc.org/article/PMC/PMC9999999",
        retrieved_at=RETRIEVED_AT,
        status=RetrievalStatus.RETRIEVED,
        content=content,
    )


def _bundle() -> tuple[OnlineEvidenceBundle, dict[str, str]]:
    trial = _retrieved()
    null = _retrieved(
        NULL_TEXT, doi="10.1000/null-trial", pmcid=None, provider_id="null", title="A null trial"
    )
    gone = OnlineSource(
        source_id=source_id_for(pmid="12345"),
        url="https://pubmed.ncbi.nlm.nih.gov/12345/",
        retrieved_at=RETRIEVED_AT,
        status=RetrievalStatus.NOT_PERMITTED,
        provider="pubmed",
        pmid="12345",
        failure_reason="Full text is behind a paywall.",
    )
    supports = EvidenceExcerpt.quote(
        trial.source_id, TRIAL_TEXT[9:], char_start=9, locator="Results"
    )
    contradicts = EvidenceExcerpt.quote(null.source_id, NULL_TEXT[9:])
    bundle = OnlineEvidenceBundle(
        question="Does semaglutide reduce body weight in adults with obesity?",
        sources=(trial, null, gone),
        excerpts=(supports, contradicts),
        claims=(
            EvidenceClaim(
                "c1",
                "Semaglutide reduces body weight versus placebo.",
                (Citation(supports.excerpt_id, EvidenceStance.SUPPORTS),),
            ),
            EvidenceClaim(
                "c2",
                "The weight effect is consistent across trials.",
                (
                    Citation(supports.excerpt_id, EvidenceStance.SUPPORTS),
                    Citation(contradicts.excerpt_id, EvidenceStance.CONTRADICTS),
                ),
            ),
            EvidenceClaim("c3", "The effect persists beyond five years."),
        ),
    )
    return bundle, {trial.source_id: TRIAL_TEXT, null.source_id: NULL_TEXT}


def test_source_ids_are_stable_and_prefer_the_strongest_identifier() -> None:
    assert source_id_for(doi="https://doi.org/10.1/ABC", pmid="1") == "doi:10.1/abc"
    assert source_id_for(pmcid="PMC12", pmid="1") == "pmcid:pmc12"
    assert source_id_for(url="HTTPS://Example.org/a") == source_id_for(url="https://example.org/a")
    with pytest.raises(OnlineEvidenceError, match="needs a DOI"):
        source_id_for()


def test_a_retrieved_observation_records_provenance_and_content_hash() -> None:
    source = _retrieved()

    assert source.source_id == "doi:10.1038/s41591-022-02026-4"
    assert source.provider == "europe_pmc"
    assert source.content_sha256 == content_sha256(TRIAL_TEXT)
    assert source.url.startswith("https://") and source.retrieved_at == RETRIEVED_AT
    assert source.license == "cc-by" and source.failure_reason is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"status": RetrievalStatus.FAILED}, "cannot carry a content hash"),
        ({"content_sha256": None}, "needs the SHA-256"),
        ({"retrieved_at": "2026-10-31T15:00:00"}, "UTC timestamp"),
        ({"retrieved_at": "yesterday"}, "ISO-8601"),
        ({"url": "file:///C:/papers/a.pdf"}, "http"),
        ({"source_id": "doi:10.9/other"}, "does not match"),
        ({"provider": " "}, "provider"),
    ],
)
def test_source_records_that_break_the_contract_are_rejected(
    change: dict[str, object], message: str
) -> None:
    fields = {**_retrieved().__dict__, **change}

    with pytest.raises(OnlineEvidenceError, match=message):
        OnlineSource(**fields)


def test_an_unavailable_source_must_say_why() -> None:
    with pytest.raises(OnlineEvidenceError, match="must state why"):
        OnlineSource.from_observation(
            _observation(),
            url="https://example.org/a",
            retrieved_at=RETRIEVED_AT,
            status=RetrievalStatus.UNAVAILABLE,
        )


def test_excerpt_ids_are_derived_and_offsets_must_span_the_text() -> None:
    excerpt = EvidenceExcerpt.quote("doi:10.1/x", "abc", char_start=4)

    assert excerpt.char_end == 7
    assert excerpt == EvidenceExcerpt.quote("doi:10.1/x", "abc", char_start=4)
    with pytest.raises(OnlineEvidenceError, match="does not match its content"):
        EvidenceExcerpt("doi:10.1/x#000000000000", "doi:10.1/x", "abc")
    with pytest.raises(OnlineEvidenceError, match="offsets"):
        EvidenceExcerpt(excerpt.excerpt_id, "doi:10.1/x", "abc", char_start=4, char_end=9)
    with pytest.raises(OnlineEvidenceError, match="exceeds"):
        EvidenceExcerpt.quote("doi:10.1/x", "a" * 1201)


def test_claim_status_makes_contradiction_and_missing_evidence_explicit() -> None:
    bundle, _contents = _bundle()

    assert [c.status for c in bundle.claims] == [
        ClaimStatus.SUPPORTED,
        ClaimStatus.CONTESTED,
        ClaimStatus.INSUFFICIENT_EVIDENCE,
    ]
    assert [s.source_id for s in bundle.unavailable_sources] == ["pmid:12345"]
    assert [c.claim_id for c in bundle.claims_with_status(ClaimStatus.CONTESTED)] == ["c2"]


def test_a_bundle_never_cites_unretrieved_sources_or_unknown_excerpts() -> None:
    bundle, _contents = _bundle()
    gone = bundle.unavailable_sources[0]
    quote_of_gone = EvidenceExcerpt.quote(gone.source_id, "anything")

    with pytest.raises(OnlineEvidenceError, match="not retrieved"):
        OnlineEvidenceBundle(bundle.question, bundle.sources, (*bundle.excerpts, quote_of_gone))
    with pytest.raises(OnlineEvidenceError, match="unknown excerpt"):
        OnlineEvidenceBundle(
            bundle.question,
            bundle.sources,
            bundle.excerpts,
            (EvidenceClaim("c9", "x", (Citation("doi:10.1/x#nope", EvidenceStance.SUPPORTS),)),),
        )
    with pytest.raises(OnlineEvidenceError, match="Duplicate source_id"):
        OnlineEvidenceBundle(bundle.question, (*bundle.sources, bundle.sources[0]))


def test_verification_finds_every_excerpt_in_the_retrieved_content() -> None:
    bundle, contents = _bundle()

    assert verify_against_retrieved_content(bundle, contents) == []


def test_verification_reports_fabricated_or_tampered_evidence() -> None:
    bundle, contents = _bundle()
    trial_id, null_id = bundle.sources[0].source_id, bundle.sources[1].source_id
    fabricated = EvidenceExcerpt.quote(trial_id, "Semaglutide cured obesity in every patient.")
    with_fabrication = OnlineEvidenceBundle(
        bundle.question, bundle.sources, (*bundle.excerpts, fabricated), bundle.claims
    )

    problems = verify_against_retrieved_content(
        with_fabrication, {trial_id: contents[trial_id], null_id: contents[null_id] + " edited"}
    )

    assert any(fabricated.excerpt_id in p and "not found" in p for p in problems)
    assert any(null_id in p and "SHA-256" in p for p in problems)
    assert verify_against_retrieved_content(bundle, {}) == [
        f"Source {trial_id}: retrieved content not supplied.",
        f"Source {null_id}: retrieved content not supplied.",
    ]


def test_an_excerpt_moved_away_from_its_offsets_is_reported() -> None:
    bundle, contents = _bundle()
    trial_id = bundle.sources[0].source_id
    shifted = {**contents, trial_id: "X" + contents[trial_id]}
    trial = OnlineSource(
        **{**bundle.sources[0].__dict__, "content_sha256": content_sha256(shifted[trial_id])}
    )
    moved = OnlineEvidenceBundle(bundle.question, (trial, *bundle.sources[1:]), bundle.excerpts)

    assert verify_against_retrieved_content(moved, shifted) == [
        f"Excerpt {bundle.excerpts[0].excerpt_id}: text is not at its offsets."
    ]


def test_a_bundle_round_trips_through_json() -> None:
    bundle, _contents = _bundle()

    payload = json.loads(json.dumps(bundle.to_dict()))

    assert payload["schema"] == "ke-online-evidence/v1"
    assert [c["status"] for c in payload["claims"]] == [
        "supported",
        "contested",
        "insufficient_evidence",
    ]
    assert OnlineEvidenceBundle.from_dict(payload) == bundle


def test_malformed_bundles_are_rejected_with_the_contract_error() -> None:
    bundle, _contents = _bundle()
    payload = bundle.to_dict()

    with pytest.raises(OnlineEvidenceError, match="schema"):
        OnlineEvidenceBundle.from_dict({**payload, "schema": "other"})
    with pytest.raises(OnlineEvidenceError, match="Malformed"):
        OnlineEvidenceBundle.from_dict({**payload, "sources": [{"url": "https://x.org"}]})
    with pytest.raises(OnlineEvidenceError, match="Malformed"):
        OnlineEvidenceBundle.from_dict(
            {**payload, "sources": [{**payload["sources"][0], "status": "cached"}]}
        )


def _write_bundle(tmp_path: Path, bundle: OnlineEvidenceBundle, contents: dict[str, str]) -> Path:
    texts = tmp_path / "contents"
    texts.mkdir()
    for text in contents.values():
        (texts / f"{content_sha256(text)}.txt").write_text(text, encoding="utf-8", newline="")
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    return path


def test_cli_verifies_a_bundle_against_its_retrieved_sources(tmp_path: Path) -> None:
    bundle, contents = _bundle()
    path = _write_bundle(tmp_path, bundle, contents)

    result = CliRunner().invoke(
        entrypoint.app,
        ["online-evidence-validate", str(path), "--contents-dir", str(tmp_path / "contents")],
    )

    output = " ".join(result.output.split())
    assert result.exit_code == 0, result.output
    assert "Sources: 2 retrieved, 1 unavailable; excerpts: 2; claims: 3" in output
    assert "unavailable pmid:12345 (not_permitted)" in output
    assert "contested claim c2" in output and "insufficient_evidence claim c3" in output
    assert "verified against retrieved content" in output


def test_cli_rejects_a_fabricated_excerpt(tmp_path: Path) -> None:
    bundle, contents = _bundle()
    fabricated = EvidenceExcerpt.quote(bundle.sources[0].source_id, "An invented finding.")
    tampered = OnlineEvidenceBundle(
        bundle.question, bundle.sources, (*bundle.excerpts, fabricated), bundle.claims
    )
    path = _write_bundle(tmp_path, tampered, contents)

    result = CliRunner().invoke(
        entrypoint.app,
        ["online-evidence-validate", str(path), "--contents-dir", str(tmp_path / "contents")],
    )

    assert result.exit_code == 1
    assert "text not found in its source" in " ".join(result.output.split())


def test_cli_rejects_a_bundle_that_breaks_the_contract(tmp_path: Path) -> None:
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps({"schema": "ke-online-evidence/v1", "question": "q"}), "utf-8")

    result = CliRunner().invoke(entrypoint.app, ["online-evidence-validate", str(path)])

    assert result.exit_code == 1
    assert "Invalid online evidence bundle" in result.output


@pytest.mark.parametrize("newline", ["\r\n", "\r", "\n"], ids=["crlf", "cr", "lf"])
def test_cli_preserves_each_newline_format_for_hashes_and_offsets(
    tmp_path: Path, newline: str
) -> None:
    text = f"Methods.{newline}Adults were randomised.{newline}Results.{newline}Weight fell by 15%."
    source = OnlineSource.from_observation(
        _observation(),
        url="https://europepmc.org/article/PMC/PMC9999999",
        retrieved_at=RETRIEVED_AT,
        status=RetrievalStatus.RETRIEVED,
        content=text,
    )
    start = text.index("Results.")
    quote = text[start:]  # spans a newline, so its offsets depend on exact line endings
    assert newline in quote
    excerpt = EvidenceExcerpt.quote(source.source_id, quote, char_start=start)
    bundle = OnlineEvidenceBundle("Does weight fall?", (source,), (excerpt,))
    texts = tmp_path / "contents"
    texts.mkdir()
    (texts / f"{content_sha256(text)}.txt").write_bytes(text.encode("utf-8"))
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")

    result = CliRunner().invoke(
        entrypoint.app, ["online-evidence-validate", str(path), "--contents-dir", str(texts)]
    )

    assert result.exit_code == 0, result.output
    assert "verified against retrieved content" in " ".join(result.output.split())
    assert excerpt.char_end == len(text)


@pytest.mark.parametrize("newline", ["\r\n", "\r"], ids=["crlf", "cr"])
def test_cli_still_rejects_modified_or_fabricated_text_with_other_newlines(
    tmp_path: Path, newline: str
) -> None:
    text = f"Results.{newline}Weight fell by 15%."
    source = OnlineSource.from_observation(
        _observation(),
        url="https://europepmc.org/article/PMC/PMC9999999",
        retrieved_at=RETRIEVED_AT,
        status=RetrievalStatus.RETRIEVED,
        content=text,
    )
    genuine = EvidenceExcerpt.quote(source.source_id, text, char_start=0)
    fabricated = EvidenceExcerpt.quote(source.source_id, f"Results.{newline}Weight fell by 50%.")
    bundle = OnlineEvidenceBundle("q", (source,), (genuine, fabricated))
    texts = tmp_path / "contents"
    texts.mkdir()
    stored = texts / f"{content_sha256(text)}.txt"
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(bundle.to_dict()), encoding="utf-8")
    args = ["online-evidence-validate", str(path), "--contents-dir", str(texts)]

    # Text normalised to LF no longer matches the recorded hash.
    stored.write_bytes(text.replace(newline, "\n").encode("utf-8"))
    modified = CliRunner().invoke(entrypoint.app, args)
    assert modified.exit_code == 1
    assert "does not match its SHA-256" in " ".join(modified.output.split())

    # The faithful text passes the hash, but the fabricated quote is still found missing.
    stored.write_bytes(text.encode("utf-8"))
    faithful = CliRunner().invoke(entrypoint.app, args)
    output = " ".join(faithful.output.split())
    assert faithful.exit_code == 1
    assert fabricated.excerpt_id in output and "text not found in its source" in output
    assert genuine.excerpt_id not in output
