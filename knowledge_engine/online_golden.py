"""Deterministic golden ``ke-online-evidence/v1`` bundle for consumer contract tests.

AI and Web readers can validate against the committed fixture under
``tests/fixtures/online_evidence/`` without network access or a pre-ingested
corpus. The fixture is regenerated from this builder; a test pins byte-identity.
"""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_engine.online_evidence import (
    Citation,
    EvidenceClaim,
    EvidenceExcerpt,
    EvidenceStance,
    OnlineEvidenceBundle,
    OnlineSource,
    RetrievalStatus,
    content_sha256,
    source_id_for,
)

GOLDEN_RETRIEVED_AT = "2026-10-31T15:00:00+00:00"
GOLDEN_BUNDLE_NAME = "bundle.json"
GOLDEN_CONTENTS_DIR = "contents"
_TRIAL_TEXT = (
    "Results. Mean change in body weight from baseline to week 104 was -15.2% with "
    "semaglutide and -2.6% with placebo."
)


def build_golden_bundle() -> tuple[OnlineEvidenceBundle, dict[str, str]]:
    """The golden bundle and the retrieved text of each retrieved source (by source_id)."""

    trial = OnlineSource(
        source_id=source_id_for(doi="10.1000/golden-trial"),
        url="https://example.org/articles/golden-trial",
        retrieved_at=GOLDEN_RETRIEVED_AT,
        status=RetrievalStatus.RETRIEVED,
        provider="europe_pmc",
        title="A golden trial",
        doi="10.1000/golden-trial",
        content_sha256=content_sha256(_TRIAL_TEXT),
        license="cc-by",
    )
    failed = OnlineSource(
        source_id=source_id_for(pmid="424242"),
        url="https://example.org/articles/424242",
        retrieved_at=GOLDEN_RETRIEVED_AT,
        status=RetrievalStatus.FAILED,
        provider="pubmed",
        pmid="424242",
        failure_reason="HTTP 503 from provider.",
    )
    unavailable = OnlineSource(
        source_id=source_id_for(arxiv_id="2501.00001"),
        url="https://example.org/abs/2501.00001",
        retrieved_at=GOLDEN_RETRIEVED_AT,
        status=RetrievalStatus.UNAVAILABLE,
        provider="arxiv",
        arxiv_id="2501.00001",
        failure_reason="No accessible full text.",
    )
    excerpt = EvidenceExcerpt.quote(
        trial.source_id, _TRIAL_TEXT[9:], char_start=9, locator="Results"
    )
    bundle = OnlineEvidenceBundle(
        question="Does semaglutide reduce body weight in adults with obesity?",
        sources=(trial, failed, unavailable),
        excerpts=(excerpt,),
        claims=(
            EvidenceClaim(
                "c1",
                "Semaglutide reduces body weight versus placebo.",
                (Citation(excerpt.excerpt_id, EvidenceStance.SUPPORTS),),
            ),
            EvidenceClaim("c2", "The effect persists beyond five years."),
        ),
    )
    return bundle, {trial.source_id: _TRIAL_TEXT}


def render_golden_bundle(bundle: OnlineEvidenceBundle) -> str:
    return json.dumps(bundle.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_golden_fixture(directory: Path) -> None:
    """(Re)generate the golden fixture: ``bundle.json`` plus ``contents/<sha256>.txt``."""

    bundle, contents = build_golden_bundle()
    (directory / GOLDEN_CONTENTS_DIR).mkdir(parents=True, exist_ok=True)
    (directory / GOLDEN_BUNDLE_NAME).write_bytes(render_golden_bundle(bundle).encode("utf-8"))
    for text in contents.values():
        target = directory / GOLDEN_CONTENTS_DIR / f"{content_sha256(text)}.txt"
        target.write_bytes(text.encode("utf-8"))


__all__ = [
    "GOLDEN_BUNDLE_NAME",
    "GOLDEN_CONTENTS_DIR",
    "build_golden_bundle",
    "render_golden_bundle",
    "write_golden_fixture",
]
