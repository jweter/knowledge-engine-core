"""Deterministically pre-score discovery-cycle candidates against a corpus's
scope criteria, to speed up (never replace) the AI (or human) title/abstract
scope screen this project has always required before `ke pmc-oa-acquire`.

Context: every discovery cycle across the GLP-1, oncology, and mental-health
corpora ends with `ke discovery-cycle-run` handing back a
`ready_for_scope_review` worksheet of 50-100 raw candidate titles, which an
AI agent (or a human) then reads one by one and classifies against that
corpus's `inclusion_criteria.md`/`exclusion_criteria.md`. That per-title
judgment call is real and this tool does not remove it -- see
`docs/ai_layer_architecture.md`'s "one rule that does not change": nothing
in this project auto-authors a scope decision without an AI (or human)
review step -- no human review is required. What this tool does is exactly
what that review already does mechanically before applying judgment: recognize
title-level signals ("this says 'case report'", "this names sertraline",
"this is about mice") that make many candidates fast, low-judgment calls, so
review time concentrates on the genuinely ambiguous ones.

Each candidate is scored `likely_include`, `likely_exclude`, or
`needs_manual_review`, with the matched rule names and a short rationale
attached -- never a bare verdict. A `likely_exclude`/`likely_include` verdict
is still a proposal for the reviewer to confirm or override, not an
autonomous accept/reject; nothing in this tool acquires, imports, or writes
to `sources.csv`.

Rule sets are corpus-specific and hand-authored from that corpus's own
criteria documents plus this project's actual, already-applied screening
practice (documented across the mental-health corpus's README status
entries) -- not a generic NLP classifier. Adding a new corpus means adding a
new `ScopeRuleSet` below, not writing new matching logic.

Example:
    poetry run python tools/discovery_scope_prescreen.py \\
        --worksheet work/mental_health/cycle-v2r7-worksheet.json \\
        --corpus mental_health_mdd_antidepressants \\
        --output work/mental_health/cycle-v2r7-prescreen.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

Verdict = Literal["likely_include", "likely_exclude", "needs_manual_review"]


@dataclass(frozen=True)
class ScopeRule:
    """One named, regex-based signal a title can match."""

    name: str
    pattern: re.Pattern[str]
    reason: str


@dataclass(frozen=True)
class ScopeRuleSet:
    """A corpus's hand-authored screening rules.

    `topic_terms` gate whether the title is about this corpus's condition at
    all. `named_agent_terms` gate whether a specific in-scope intervention is
    named (bare mentions of the drug class without a named agent are treated
    as `needs_manual_review`, matching this project's own repeated finding
    that generic terms collapse yield -- see the mental-health corpus's
    README "yield collapsed" entries). `hard_exclude_rules` are checked only
    after both topic and agent gates pass, since an exclude signal on an
    already off-topic title is redundant, not additional evidence.
    """

    corpus_id: str
    topic_terms: tuple[re.Pattern[str], ...]
    named_agent_terms: tuple[re.Pattern[str], ...]
    hard_exclude_rules: tuple[ScopeRule, ...]


def _ci(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


MENTAL_HEALTH_MDD_ANTIDEPRESSANTS = ScopeRuleSet(
    corpus_id="mental_health_mdd_antidepressants",
    topic_terms=(
        _ci(r"\bdepress\w*\b"),  # depression, depressive, depressant, depressed
        _ci(r"\bmajor depressive disorder\b"),
        _ci(r"\bmdd\b"),
        _ci(r"\bantidepressant\w*\b"),
    ),
    named_agent_terms=(
        _ci(r"\bssri\b"),
        _ci(r"\bsnri\b"),
        _ci(r"\bfluoxetine\b"),
        _ci(r"\bsertraline\b"),
        _ci(r"\bescitalopram\b"),
        _ci(r"\bparoxetine\b"),
        _ci(r"\bcitalopram\b"),
        _ci(r"\bvenlafaxine\b"),
        _ci(r"\bduloxetine\b"),
        _ci(r"\bdesvenlafaxine\b"),
        _ci(r"\bvilazodone\b"),
        _ci(r"selective serotonin reuptake inhibitor"),
        _ci(r"serotonin.norepinephrine reuptake inhibitor"),
    ),
    hard_exclude_rules=(
        ScopeRule(
            "case_report",
            _ci(r"\bcase report(s)?\b|\bcase series\b"),
            "case report/series (any size)",
        ),
        ScopeRule(
            "preclinical_animal",
            _ci(r"\b(mice|mouse|rat|rats|murine|rodent|zebrafish)\b"),
            "preclinical/animal study",
        ),
        ScopeRule(
            "protocol_only",
            _ci(r"\bstudy protocol\b|\bprotocol for a\b|\btrial protocol\b"),
            "protocol-only paper, no results yet",
        ),
        ScopeRule(
            "expert_consensus",
            _ci(r"\bdelphi\b|\bexpert consensus\b|\bconsensus statement\b"),
            "expert consensus/Delphi statement",
        ),
        ScopeRule(
            "bipolar",
            _ci(r"\bbipolar\b"),
            "bipolar population, explicitly excluded in scientific_question.md",
        ),
        ScopeRule(
            "psychotic_population",
            _ci(r"\bpsychotic depression\b|\bschizophrenia\b"),
            "psychotic-disorder population, explicitly excluded",
        ),
        ScopeRule(
            "perinatal_population",
            _ci(r"\bperinatal\b|\bpostpartum\b|\bpregnan(t|cy)\b"),
            "perinatal/postpartum population, explicitly excluded",
        ),
        ScopeRule(
            "off_topic_comorbid_primary",
            _ci(
                r"\bpanic disorder\b|\bobsessive.compulsive\b|\bocd\b|"
                r"\bgeneralized anxiety\b|\birritable bowel\b|\bfibromyalgia\b"
            ),
            "off-topic comorbid primary condition (not MDD itself)",
        ),
        ScopeRule(
            "herbal_supplement",
            _ci(r"\bherbal\b|\bsupplement\b"),
            "herbal/supplement compound (unless a named SSRI/SNRI is also "
            "present -- review manually)",
        ),
        ScopeRule(
            "imaging_biomarker_signal",
            _ci(
                r"\bneuroimaging\b|\bneuroanatomical\b|\bbiomarker(s)?\b|\bfmri\b|\bpet scan\b|"
                r"\bmedication.free individuals\b"
            ),
            "title-level imaging/biomarker signal -- this project's exclusion "
            "criteria exclude mechanism/imaging/biomarker studies whose focus "
            "is not treatment-outcome efficacy, but a title-only regex cannot "
            "reliably tell an imaging *study* from an imaging *outcome measured "
            "within* a genuine treatment-outcome trial; always confirm from the "
            "abstract, this rule alone should not decide.",
        ),
    ),
)

ONCOLOGY_NSCLC_CHECKPOINT_INHIBITORS = ScopeRuleSet(
    corpus_id="oncology_nsclc_checkpoint_inhibitors",
    topic_terms=(
        _ci(r"\bnon.small.cell lung cancer\b"),  # non-small-cell / non-small cell
        _ci(r"\bnsclc\b"),
        _ci(r"\blung cancer\b"),
        _ci(r"\blung carcinoma\b"),
        _ci(r"\blung adenocarcinoma\b"),
    ),
    named_agent_terms=(
        _ci(r"\bpembrolizumab\b"),
        _ci(r"\bnivolumab\b"),
        _ci(r"\batezolizumab\b"),
        _ci(r"\bdurvalumab\b"),
        _ci(r"\bcemiplimab\b"),
        _ci(r"\bpd.?1\b"),  # PD-1 / PD 1 / PD1
        _ci(r"\bpd.?l1\b"),  # PD-L1 / PD L1 / PDL1
        _ci(r"programmed death.1"),
        _ci(r"programmed death.ligand 1"),
        _ci(r"\bimmune checkpoint inhibitor"),
        _ci(r"\bcheckpoint inhibitor"),
    ),
    hard_exclude_rules=(
        ScopeRule(
            "case_report",
            _ci(r"\bcase report(s)?\b|\bcase series\b"),
            "case report/series (any size)",
        ),
        ScopeRule(
            "preclinical_animal",
            _ci(r"\b(mice|mouse|rat|rats|murine|rodent|xenograft|zebrafish)\b"),
            "preclinical/animal study",
        ),
        ScopeRule(
            "protocol_only",
            _ci(r"\bstudy protocol\b|\bprotocol for a\b|\btrial protocol\b"),
            "protocol-only paper, no results yet",
        ),
        ScopeRule(
            "pediatric_population",
            _ci(r"\bpediatric\b|\bpaediatric\b|\bchildhood\b|\binfant(s)?\b"),
            "pediatric-only population, explicitly excluded in "
            "exclusion_criteria.md -- note the shared adjudication layer "
            "(knowledge_engine.scientific_scope) also checks this "
            "separately pre-acquisition; this rule is a second, "
            "belt-and-suspenders check at the scope-prescreen stage.",
        ),
        ScopeRule(
            "mechanism_only",
            _ci(
                r"\bmechanism of action\b|\bmolecular mechanism(s)?\b|\bin vitro\b|"
                r"\bcell line(s)?\b"
            ),
            "mechanism-only paper without a named clinical intervention/trial, "
            "explicitly excluded in exclusion_criteria.md",
        ),
        ScopeRule(
            "non_primary_content",
            _ci(
                r"\bcommentary\b|\beditorial\b|\bletter to the editor\b|"
                r"\bcorrespondence\b|\bnews\b|\bperspective\b|\bviewpoint\b"
            ),
            "editorial/commentary/letter/news, explicitly excluded in "
            "exclusion_criteria.md as 'rather than primary or synthesized "
            "evidence' -- note this only catches titles that carry an "
            "explicit marker; a commentary whose title reads like a "
            "primary trial report (e.g. 'PACIFIC-5 Trial: Refining "
            "Patient Selection...', a real near-miss this session caught "
            "only by reading the PDF body's own 'COMMENTARY' section-type "
            "label) will not match here -- see the post-acquisition "
            "article-type check for that class of case.",
        ),
    ),
)

CORPUS_RULE_SETS: dict[str, ScopeRuleSet] = {
    MENTAL_HEALTH_MDD_ANTIDEPRESSANTS.corpus_id: MENTAL_HEALTH_MDD_ANTIDEPRESSANTS,
    ONCOLOGY_NSCLC_CHECKPOINT_INHIBITORS.corpus_id: ONCOLOGY_NSCLC_CHECKPOINT_INHIBITORS,
}


@dataclass(frozen=True)
class PrescreenResult:
    pmid: str | int | None
    title: str
    verdict: Verdict
    matched_rules: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_json(self) -> dict[str, object]:
        return {
            "pmid": self.pmid,
            "title": self.title,
            "verdict": self.verdict,
            "matched_rules": self.matched_rules,
            "rationale": self.rationale,
        }


def prescreen_candidate(title: str, rules: ScopeRuleSet) -> tuple[Verdict, list[str], str]:
    has_topic_term = any(term.search(title) for term in rules.topic_terms)
    has_named_agent = any(term.search(title) for term in rules.named_agent_terms)

    if not has_topic_term and not has_named_agent:
        return (
            "likely_exclude",
            ["off_topic"],
            "Title names neither this corpus's condition nor a specific in-scope agent.",
        )

    if not has_named_agent:
        return (
            "needs_manual_review",
            ["no_named_agent"],
            "On-topic but names no specific in-scope agent -- generic class "
            "terms alone have repeatedly produced low yield in this "
            "project's own discovery cycles; needs an AI (or human) read of the "
            "abstract.",
        )

    if not has_topic_term:
        return (
            "needs_manual_review",
            ["agent_named_topic_unstated"],
            "Names a specific in-scope agent but the title does not restate "
            "the corpus's condition -- the discovery query already requires "
            "co-occurrence at the PubMed abstract/MeSH level, so this can be "
            "a genuinely on-topic paper (e.g. an agent-specific case report "
            "or pharmacovigilance finding) whose title just doesn't repeat "
            "'depression'; needs an AI (or human) read rather than a title-only "
            "guess either way.",
        )

    exclude_hits = [rule for rule in rules.hard_exclude_rules if rule.pattern.search(title)]
    if exclude_hits:
        names = [rule.name for rule in exclude_hits]
        reasons = "; ".join(rule.reason for rule in exclude_hits)
        return "likely_exclude", names, reasons

    return (
        "likely_include",
        ["on_topic", "named_agent_present"],
        "Mentions the corpus condition and a named in-scope agent, with no "
        "matched hard-exclude signal in the title alone.",
    )


def prescreen_worksheet(worksheet: dict[str, object], rules: ScopeRuleSet) -> list[PrescreenResult]:
    candidates_raw = worksheet.get("ready_for_scope_review") or worksheet.get("candidates") or []
    candidates = cast("list[dict[str, object]]", candidates_raw)
    results: list[PrescreenResult] = []
    for candidate in candidates:
        title = str(candidate.get("title", ""))
        verdict, matched_rules, rationale = prescreen_candidate(title, rules)
        pmid_raw = candidate.get("pmid")
        pmid = pmid_raw if isinstance(pmid_raw, (str, int)) or pmid_raw is None else str(pmid_raw)
        results.append(
            PrescreenResult(
                pmid=pmid,
                title=title,
                verdict=verdict,
                matched_rules=matched_rules,
                rationale=rationale,
            )
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--worksheet", type=Path, required=True, help="ke discovery-cycle-run output JSON"
    )
    parser.add_argument(
        "--corpus",
        required=True,
        choices=sorted(CORPUS_RULE_SETS),
        help="Which corpus's hand-authored rule set to apply",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Path for the prescreened worksheet JSON"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    args = parser.parse_args()

    if args.output.exists() and not args.force:
        raise SystemExit(f"{args.output} already exists; pass --force to overwrite.")

    worksheet = json.loads(args.worksheet.read_text())
    rules = CORPUS_RULE_SETS[args.corpus]
    results = prescreen_worksheet(worksheet, rules)

    counts: dict[str, int] = {"likely_include": 0, "likely_exclude": 0, "needs_manual_review": 0}
    for result in results:
        counts[result.verdict] += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "corpus": args.corpus,
                "source_worksheet": str(args.worksheet),
                "counts": counts,
                "candidates": [result.to_json() for result in results],
            },
            indent=2,
        )
    )

    print(
        f"Prescreened {len(results)} candidate(s): "
        f"{counts['likely_include']} likely_include, "
        f"{counts['likely_exclude']} likely_exclude, "
        f"{counts['needs_manual_review']} needs_manual_review."
    )
    print(
        "These are deterministic proposals, not decisions -- the same "
        "AI (or human) title-and-abstract scope screen this project has always "
        "required before ke pmc-oa-acquire still applies to every row, "
        "especially needs_manual_review and likely_include rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
