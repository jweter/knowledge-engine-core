"""Deterministic cross-study reporting for a validated evidence map.

This module renders already-reviewed Evidence and Relationship Records. It
does not validate scientific meaning, infer relationships, parse statistical
values from prose, compute consensus, or access a database.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from knowledge_engine.utils import normalize_doi


@dataclass(frozen=True)
class CitationMetadata:
    """Curated citation fields for one normalized DOI."""

    title: str
    authors: str
    year: str
    venue: str
    doi: str
    source_url: str
    license_type: str


@dataclass(frozen=True)
class ComparisonRelationship:
    """One selected reviewed relationship touching a comparison row."""

    relationship_id: str
    relationship_type: str
    other_evidence_record_id: str
    direction: str
    rationale: str


@dataclass(frozen=True)
class ComparisonRow:
    """Source-linked fields displayed for one selected Evidence Record."""

    evidence_record_id: str
    role: str
    inclusion_rationale: str
    source_title: str
    doi: str
    authors: str
    year: str
    venue: str
    source_url: str
    license_type: str
    study_type: str
    review_status: str
    population: str
    intervention: str
    comparator: str
    outcome: str
    evidence_direction: str
    result_summary: str
    limitations: tuple[str, ...]
    relationships: tuple[ComparisonRelationship, ...]


def build_comparison_rows(
    map_payload: Mapping[str, Any],
    *,
    evidence_records: Sequence[Mapping[str, Any]],
    relationship_records: Sequence[Mapping[str, Any]],
    citations_by_doi: Mapping[str, CitationMetadata],
) -> tuple[ComparisonRow, ...]:
    """Build rows in the evidence-node and relationship order declared by the map.

    Inputs must already have passed the evidence, relationship, source, and map
    validators. Missing optional display fields remain visibly unrecorded.
    """

    evidence_by_id = {str(record["evidence_record_id"]): record for record in evidence_records}
    relationships_by_id = {
        str(record["relationship_id"]): record for record in relationship_records
    }
    selected_relationships = [
        relationships_by_id[str(relationship_id)]
        for relationship_id in map_payload["relationship_ids"]
    ]

    rows: list[ComparisonRow] = []
    for node in map_payload["evidence_nodes"]:
        evidence_id = str(node["evidence_record_id"])
        record = evidence_by_id[evidence_id]
        doi = _text(record.get("source_doi"))
        citation = citations_by_doi.get(normalize_doi(doi))
        relationships = tuple(
            relationship
            for selected in selected_relationships
            if (relationship := _comparison_relationship(selected, evidence_id)) is not None
        )
        raw_limitations = record.get("limitations")
        limitations = (
            tuple(_text(value) for value in raw_limitations if _text(value))
            if isinstance(raw_limitations, list)
            else ()
        )
        rows.append(
            ComparisonRow(
                evidence_record_id=evidence_id,
                role=_text(node.get("role")),
                inclusion_rationale=_text(node.get("inclusion_rationale")),
                source_title=(citation.title if citation else _text(record.get("source_title"))),
                doi=(citation.doi if citation else doi),
                authors=(citation.authors if citation else ""),
                year=(citation.year if citation else ""),
                venue=(citation.venue if citation else ""),
                source_url=(citation.source_url if citation else ""),
                license_type=(citation.license_type if citation else ""),
                study_type=_text(record.get("study_type")),
                review_status=_text(record.get("review_status")),
                population=_text(record.get("population")),
                intervention=_text(record.get("intervention")),
                comparator=_text(record.get("comparator")),
                outcome=_text(record.get("outcome")),
                evidence_direction=_text(record.get("evidence_direction")),
                result_summary=_text(record.get("result_summary")),
                limitations=limitations,
                relationships=relationships,
            )
        )
    return tuple(rows)


def render_evidence_map_report(
    map_payload: Mapping[str, Any],
    *,
    rows: Sequence[ComparisonRow],
) -> str:
    """Render one deterministic Markdown comparison report."""

    relationship_count = sum(
        1 for relationship_id in map_payload.get("relationship_ids", []) if relationship_id
    )
    lines = [
        f"# {_md_text(map_payload.get('title'))}",
        "",
        "## Map",
        "",
        f"- **Map ID:** `{_md_code(map_payload.get('map_id'))}`",
        f"- **Status:** {_display(map_payload.get('map_status'))}",
        f"- **Research question:** {_display(map_payload.get('research_question'))}",
        f"- **Selected evidence records:** {len(rows)}",
        f"- **Selected reviewed relationships:** {relationship_count}",
        "",
        "This is a deterministic comparison of stored, reviewed records. It does not "
        "infer evidence or relationships and does not perform scientific synthesis.",
        "",
        "## Scope",
        "",
    ]
    scope = map_payload["scope"]
    for field in ("population", "intervention", "outcome", "exclusions"):
        lines.append(f"- **{field.replace('_', ' ').title()}:** {_display(scope.get(field))}")

    lines.extend(
        [
            "",
            "## Study Index",
            "",
            "| # | Evidence Record | Role | Study design | Year | DOI |",
            "| ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"| {index} | `{_md_code(row.evidence_record_id)}` | {_table(row.role)} | "
            f"{_table(row.study_type)} | {_table(row.year)} | {_table(row.doi)} |"
        )

    lines.extend(["", "## Cross-Study Comparison", ""])
    for index, row in enumerate(rows, start=1):
        lines.extend(_row_lines(index, row))

    lines.extend(_group_lines("Population Groups", map_payload["population_groups"]))
    lines.extend(_group_lines("Comparator Groups", map_payload["comparator_groups"]))

    contradiction = map_payload["contradiction_assessment"]
    lines.extend(
        [
            "## Contradiction Assessment",
            "",
            f"- **Status:** {_display(contradiction.get('status'))}",
            f"- **Statement:** {_display(contradiction.get('statement'))}",
            "",
            "## Analytical Readiness",
            "",
            f"All {len(rows)} selected records expose their reported result summaries as "
            "reviewed prose. This report does not treat that prose as typed statistical input.",
            "",
            "Before deterministic effect verification begins, each supported statistical "
            "record needs explicit source-linked fields for estimate type, value, unit, "
            "confidence interval or other uncertainty measure, treatment time point, analysis "
            "population, group sizes, and the formula inputs required for recomputation.",
            "",
            "No effect was recalculated or pooled. No sensitivity analysis, meta-analysis, "
            "consensus score, confidence score, ranking, or LLM narration was produced.",
            "",
            "## Trust Boundary",
            "",
            "- No evidence or relationship was inferred.",
            "- No scientific synthesis was performed.",
            "- No consensus or confidence was calculated or changed.",
            "- No statistical value was parsed from prose or recomputed.",
            "- This report does not constitute legal approval, scientific review, clinical "
            "guidance, or truth determination.",
            "",
        ]
    )
    return "\n".join(lines)


def _comparison_relationship(
    record: Mapping[str, Any], evidence_id: str
) -> ComparisonRelationship | None:
    source_id = _text(record.get("source_evidence_record_id"))
    target_id = _text(record.get("target_evidence_record_id"))
    if source_id == evidence_id:
        other_id = target_id
        direction = "outgoing"
    elif target_id == evidence_id:
        other_id = source_id
        direction = "incoming"
    else:
        return None
    return ComparisonRelationship(
        relationship_id=_text(record.get("relationship_id")),
        relationship_type=_text(record.get("relationship_type")),
        other_evidence_record_id=other_id,
        direction=direction,
        rationale=_text(record.get("rationale")),
    )


def _row_lines(index: int, row: ComparisonRow) -> list[str]:
    lines = [
        f"### {index}. {_md_text(row.source_title)}",
        "",
        f"- **Evidence Record:** `{_md_code(row.evidence_record_id)}`",
        f"- **Map role:** {_display(row.role)}",
        f"- **Inclusion rationale:** {_display(row.inclusion_rationale)}",
        f"- **Study design:** {_display(row.study_type)}",
        f"- **Review status:** {_display(row.review_status)}",
        f"- **Authors:** {_display(row.authors)}",
        f"- **Venue / year:** {_display(row.venue)} / {_display(row.year)}",
        f"- **DOI:** `{_md_code(row.doi)}`",
        f"- **Source:** {_source_link(row.source_url)}",
        f"- **Declared license:** {_display(row.license_type)}",
        f"- **Population:** {_display(row.population)}",
        f"- **Intervention:** {_display(row.intervention)}",
        f"- **Comparator:** {_display(row.comparator)}",
        f"- **Outcome:** {_display(row.outcome)}",
        f"- **Evidence direction:** {_display(row.evidence_direction)}",
        f"- **Reported result:** {_display(row.result_summary)}",
        "- **Recorded limitations:**",
    ]
    lines.extend(f"  - {_md_text(limitation)}" for limitation in row.limitations)
    lines.append("- **Reviewed relationships:**")
    if row.relationships:
        for relationship in row.relationships:
            lines.append(
                f"  - `{_md_code(relationship.relationship_id)}`: "
                f"**{_md_text(relationship.relationship_type)}** "
                f"({relationship.direction}) with "
                f"`{_md_code(relationship.other_evidence_record_id)}`. "
                f"{_md_text(relationship.rationale)}"
            )
    else:
        lines.append("  - None selected in this map.")
    lines.append("")
    return lines


def _group_lines(title: str, groups: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = [f"## {title}", ""]
    for group in groups:
        evidence_ids = ", ".join(f"`{_md_code(value)}`" for value in group["evidence_record_ids"])
        lines.extend(
            [
                f"### {_md_text(group.get('label'))}",
                "",
                f"- **Evidence Records:** {evidence_ids}",
                f"- **Interpretation boundary:** {_display(group.get('interpretation_boundary'))}",
                "",
            ]
        )
    return lines


def _source_link(url: str) -> str:
    if not url:
        return "Not recorded"
    safe_url = quote(url, safe=":/?#@!$&'*+,;=%")
    return f"[Source]({safe_url})"


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _display(value: object) -> str:
    text = _text(value)
    return _md_text(text) if text else "Not recorded"


def _table(value: object) -> str:
    text = _text(value)
    return _md_text(text).replace("|", "\\|") if text else "Not recorded"


def _md_code(value: object) -> str:
    text = _text(value) or "Not recorded"
    return text.replace("`", "\\`").replace("\r", " ").replace("\n", " ")


def _md_text(value: object) -> str:
    text = _text(value) or "Not recorded"
    text = " ".join(text.split())
    for character in ("\\", "`", "*", "_", "{", "}", "[", "]", "<", ">"):
        text = text.replace(character, f"\\{character}")
    return text
