import json
from pathlib import Path

import pytest
from click import unstyle
from typer.testing import CliRunner

from knowledge_engine.cli import app
from knowledge_engine.evidence_map_report import (
    CitationMetadata,
    build_comparison_rows,
    render_evidence_map_report,
)


def _payload() -> dict[str, object]:
    return {
        "title": "Comparison [Map]",
        "map_id": "comparison-map-v1",
        "map_status": "reviewed",
        "research_question": "Does treatment affect weight?",
        "scope": {
            "population": "Adults",
            "intervention": "Treatment",
            "outcome": "Body weight",
            "exclusions": "Other outcomes",
        },
        "evidence_nodes": [
            {
                "evidence_record_id": "ev-b",
                "role": "population_extension",
                "inclusion_rationale": "Second source in declared map order.",
            },
            {
                "evidence_record_id": "ev-a",
                "role": "landmark_trial",
                "inclusion_rationale": "Direct source.",
            },
        ],
        "relationship_ids": ["rel-second", "rel-first"],
        "population_groups": [
            {
                "label": "Adults",
                "evidence_record_ids": ["ev-b", "ev-a"],
                "interpretation_boundary": "Populations remain distinct.",
            }
        ],
        "comparator_groups": [
            {
                "label": "Placebo",
                "evidence_record_ids": ["ev-b", "ev-a"],
                "interpretation_boundary": "Comparators remain distinct.",
            }
        ],
        "contradiction_assessment": {
            "status": "none_identified_in_bounded_map",
            "statement": "No aligned contradiction was identified.",
            "evidence_record_ids": [],
        },
    }


def _records() -> list[dict[str, object]]:
    return [
        {
            "evidence_record_id": "ev-a",
            "source_doi": "https://doi.org/10.1000/A",
            "source_title": "Parser title A",
            "study_type": "randomized_controlled_trial",
            "review_status": "reviewed",
            "population": "Adults without diabetes",
            "intervention": "Treatment A",
            "comparator": "Placebo",
            "outcome": "Body weight",
            "evidence_direction": "supports",
            "result_summary": "Treatment reduced weight.",
            "limitations": ["One limitation."],
        },
        {
            "evidence_record_id": "ev-b",
            "source_doi": "10.1000/b",
            "source_title": "Source *B*",
            "study_type": "cohort_study",
            "review_status": "reviewed",
            "population": "Adults with diabetes",
            "intervention": "Treatment B",
            "comparator": "Usual care",
            "outcome": "Body weight",
            "evidence_direction": "qualifies",
            "result_summary": "A [bounded] result.",
            "limitations": ["Selection | bias."],
        },
    ]


def _relationships() -> list[dict[str, str]]:
    return [
        {
            "relationship_id": "rel-first",
            "source_evidence_record_id": "ev-a",
            "target_evidence_record_id": "ev-b",
            "relationship_type": "supports",
            "rationale": "First rationale.",
        },
        {
            "relationship_id": "rel-second",
            "source_evidence_record_id": "ev-b",
            "target_evidence_record_id": "ev-a",
            "relationship_type": "qualifies",
            "rationale": "Second [bounded] rationale.",
        },
    ]


def _citations() -> dict[str, CitationMetadata]:
    return {
        "10.1000/a": CitationMetadata(
            title="Curated title A",
            authors="A. Author",
            year="2024",
            venue="Journal A",
            doi="10.1000/A",
            source_url="https://example.test/a",
            license_type="CC BY",
        ),
        "10.1000/b": CitationMetadata(
            title="Curated title B",
            authors="B. Author",
            year="2023",
            venue="Journal B",
            doi="10.1000/b",
            source_url="https://example.test/b",
            license_type="CC0",
        ),
    }


def test_comparison_rows_follow_map_and_relationship_order() -> None:
    rows = build_comparison_rows(
        _payload(),
        evidence_records=_records(),
        relationship_records=_relationships(),
        citations_by_doi=_citations(),
    )

    assert [row.evidence_record_id for row in rows] == ["ev-b", "ev-a"]
    assert rows[1].source_title == "Curated title A"
    assert rows[1].doi == "10.1000/A"
    assert [relationship.relationship_id for relationship in rows[0].relationships] == [
        "rel-second",
        "rel-first",
    ]
    assert rows[0].relationships[0].direction == "outgoing"
    assert rows[0].relationships[1].direction == "incoming"


def test_report_is_deterministic_escaped_and_explicitly_non_analytical() -> None:
    rows = build_comparison_rows(
        _payload(),
        evidence_records=_records(),
        relationship_records=_relationships(),
        citations_by_doi=_citations(),
    )

    first = render_evidence_map_report(_payload(), rows=rows)
    second = render_evidence_map_report(_payload(), rows=rows)

    assert first == second
    assert "# Comparison \\[Map\\]" in first
    assert "A \\[bounded\\] result." in first
    assert "Selection | bias." in first
    assert first.index("`ev-b`") < first.index("`ev-a`")
    assert first.index("`rel-second`") < first.index("`rel-first`")
    assert "does not treat that prose as typed statistical input" in first
    assert "No effect was recalculated or pooled" in first
    assert "No consensus or confidence was calculated or changed" in first


def test_source_url_cannot_inject_markdown() -> None:
    citations = _citations()
    citations["10.1000/a"] = CitationMetadata(
        title="Curated title A",
        authors="A. Author",
        year="2024",
        venue="Journal A",
        doi="10.1000/A",
        source_url="https://example.test/a) [Injected](https://bad.test",
        license_type="CC BY",
    )
    rows = build_comparison_rows(
        _payload(),
        evidence_records=_records(),
        relationship_records=_relationships(),
        citations_by_doi=citations,
    )

    report = render_evidence_map_report(_payload(), rows=rows)

    assert "[Injected]" not in report
    assert "%29%20%5BInjected%5D%28" in report


def test_missing_optional_values_are_not_invented() -> None:
    records = _records()
    records[0]["population"] = None
    citations = _citations()
    del citations["10.1000/a"]

    rows = build_comparison_rows(
        _payload(),
        evidence_records=records,
        relationship_records=_relationships(),
        citations_by_doi=citations,
    )
    report = render_evidence_map_report(_payload(), rows=rows)

    assert rows[1].source_title == "Parser title A"
    assert rows[1].population == ""
    assert "- **Population:** Not recorded" in report
    assert "- **Authors:** Not recorded" in report


def test_committed_glp1_map_report_has_expected_counts_and_no_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    output = tmp_path / "glp1-report.md"
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-report",
            str(corpus / "golden_evidence_map.json"),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--relationships",
            str(corpus / "relationship_records.jsonl"),
            "--sources",
            str(corpus / "sources.csv"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Evidence records: 12" in result.output
    assert "Selected relationships: 17" in result.output
    report = output.read_text(encoding="utf-8")
    assert report.count("### ") >= 12
    assert "ev-glp1-glide-liraglutide-post-lagb-weight-001" in report
    assert "No effect was recalculated or pooled" in report
    assert not (tmp_path / "data" / "knowledge_engine.sqlite3").exists()


def test_cli_refuses_invalid_map_and_existing_output(tmp_path: Path) -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    invalid_map = tmp_path / "invalid-map.json"
    invalid_map.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    output = tmp_path / "report.md"
    output.write_text("keep", encoding="utf-8")
    common = [
        "--evidence",
        str(corpus / "evidence_records.jsonl"),
        "--relationships",
        str(corpus / "relationship_records.jsonl"),
        "--sources",
        str(corpus / "sources.csv"),
    ]

    invalid = CliRunner().invoke(app, ["evidence-map-report", str(invalid_map), *common])
    existing = CliRunner().invoke(
        app,
        [
            "evidence-map-report",
            str(corpus / "golden_evidence_map.json"),
            *common,
            "--output",
            str(output),
        ],
    )
    assert invalid.exit_code == 1
    assert "map validation failed" in invalid.output
    assert existing.exit_code == 2
    assert "Use --force to overwrite" in unstyle(existing.output)
    assert output.read_text(encoding="utf-8") == "keep"

    forced = CliRunner().invoke(
        app,
        [
            "evidence-map-report",
            str(corpus / "golden_evidence_map.json"),
            *common,
            "--output",
            str(output),
            "--force",
        ],
    )

    assert forced.exit_code == 0, forced.output
    assert output.read_text(encoding="utf-8").startswith(
        "# GLP-1 and Body-Weight Golden Evidence Map"
    )


def test_cli_never_overwrites_an_input_even_with_force() -> None:
    root = Path(__file__).parents[1]
    corpus = root / "data" / "corpora" / "glp1_weight_loss"
    map_path = corpus / "golden_evidence_map.json"
    original = map_path.read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "evidence-map-report",
            str(map_path),
            "--evidence",
            str(corpus / "evidence_records.jsonl"),
            "--relationships",
            str(corpus / "relationship_records.jsonl"),
            "--sources",
            str(corpus / "sources.csv"),
            "--output",
            str(map_path),
            "--force",
        ],
    )

    assert result.exit_code == 2
    assert "must not overwrite an input file" in result.output
    assert map_path.read_bytes() == original
