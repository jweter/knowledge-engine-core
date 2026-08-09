from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "discovery_scope_prescreen.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("discovery_scope_prescreen", _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prescreen = _load_module()


@pytest.fixture()
def mh_rules() -> Any:
    return prescreen.CORPUS_RULE_SETS["mental_health_mdd_antidepressants"]


def test_off_topic_title_is_likely_exclude(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "FDG-PET/CT based small volume accelerated immuno chemoradiotherapy in NSCLC", mh_rules
    )
    assert verdict == "likely_exclude"
    assert matched_rules == ["off_topic"]


def test_generic_antidepressant_term_needs_manual_review(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Effects of Anxious Depression on Antidepressant Treatment Response.", mh_rules
    )
    assert verdict == "needs_manual_review"
    assert matched_rules == ["no_named_agent"]


def test_case_report_naming_an_agent_but_not_depression_needs_manual_review(mh_rules: Any) -> None:
    # Real title from mental-health cycle 8 (PMID 38347994): a genuine case
    # report about desvenlafaxine's own side effect, matched by the discovery
    # query via abstract-level co-occurrence with "depression" -- the title
    # itself never restates the condition, so the tool must not guess either
    # way from title text alone.
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Desvenlafaxine-Triggered Acneiform Eruptions on the Hand: A Compelling Case Report.",
        mh_rules,
    )
    assert verdict == "needs_manual_review"
    assert matched_rules == ["agent_named_topic_unstated"]


def test_case_report_naming_both_depression_and_agent_is_likely_exclude(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Sertraline-Induced Sleep Paralysis in Major Depressive Disorder: A Case Report.", mh_rules
    )
    assert verdict == "likely_exclude"
    assert "case_report" in matched_rules


def test_preclinical_animal_study_naming_depression_is_likely_exclude(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Developmental fluoxetine exposure affects depressive-like behavior in adult mice.",
        mh_rules,
    )
    assert verdict == "likely_exclude"
    assert "preclinical_animal" in matched_rules


def test_bipolar_population_is_likely_exclude(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Sertraline augmentation in bipolar depression: a randomized trial.", mh_rules
    )
    assert verdict == "likely_exclude"
    assert "bipolar" in matched_rules


def test_clean_named_agent_rct_is_likely_include(mh_rules: Any) -> None:
    verdict, matched_rules, _ = prescreen.prescreen_candidate(
        "Escitalopram versus other antidepressive agents for major depressive disorder: "
        "a systematic review and meta-analysis.",
        mh_rules,
    )
    assert verdict == "likely_include"
    assert matched_rules == ["on_topic", "named_agent_present"]


def test_prescreen_worksheet_counts_match_individual_verdicts(mh_rules: Any) -> None:
    worksheet = {
        "ready_for_scope_review": [
            {"pmid": 1, "title": "Escitalopram for major depressive disorder: an RCT."},
            {
                "pmid": 2,
                "title": (
                    "Sertraline-Induced Sleep Paralysis in Major Depressive "
                    "Disorder: A Case Report."
                ),
            },
            {
                "pmid": 3,
                "title": "Effects of Anxious Depression on Antidepressant Treatment Response.",
            },
        ]
    }

    results = prescreen.prescreen_worksheet(worksheet, mh_rules)

    verdicts = [result.verdict for result in results]
    assert verdicts == ["likely_include", "likely_exclude", "needs_manual_review"]
    assert [result.pmid for result in results] == [1, 2, 3]


def test_cli_writes_expected_summary_and_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    worksheet_path = tmp_path / "worksheet.json"
    worksheet_path.write_text(
        json.dumps(
            {
                "ready_for_scope_review": [
                    {"pmid": 1, "title": "Escitalopram for major depressive disorder: an RCT."},
                    {
                        "pmid": 2,
                        "title": (
                            "Sertraline-Induced Sleep Paralysis in Major "
                            "Depressive Disorder: A Case Report."
                        ),
                    },
                ]
            }
        )
    )
    output_path = tmp_path / "prescreen.json"

    sys.argv = [
        "discovery_scope_prescreen.py",
        "--worksheet",
        str(worksheet_path),
        "--corpus",
        "mental_health_mdd_antidepressants",
        "--output",
        str(output_path),
    ]
    result = prescreen.main()

    assert result == 0
    written = json.loads(output_path.read_text())
    assert written["counts"] == {"likely_include": 1, "likely_exclude": 1, "needs_manual_review": 0}
    assert len(written["candidates"]) == 2

    captured = capsys.readouterr()
    assert "1 likely_include" in captured.out
    assert "1 likely_exclude" in captured.out
    assert "not decisions" in captured.out


def test_cli_refuses_to_overwrite_without_force(tmp_path: Path) -> None:
    worksheet_path = tmp_path / "worksheet.json"
    worksheet_path.write_text(json.dumps({"ready_for_scope_review": []}))
    output_path = tmp_path / "prescreen.json"
    output_path.write_text("{}")

    sys.argv = [
        "discovery_scope_prescreen.py",
        "--worksheet",
        str(worksheet_path),
        "--corpus",
        "mental_health_mdd_antidepressants",
        "--output",
        str(output_path),
    ]

    with pytest.raises(SystemExit, match="already exists"):
        prescreen.main()
