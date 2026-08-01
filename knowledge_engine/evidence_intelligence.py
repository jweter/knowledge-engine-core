"""Evidence Intelligence: deterministic, no-LLM confidence scoring.

See `docs/evidence_intelligence_design.md` for the full design and its
verification against `docs/ai_layer_architecture.md`. Every function here
is a pure computation over already-stored `EvidenceRecord`/
`RelationshipRecord` fields -- never an LLM call, never a guess, never a
number without a stored source. Scoped to exactly the
`clinical_medicine_v1` profile; not proposed as portable to another
field.

Evidence Quality, Evidence Consensus, and Claim Confidence are three
separate numbers that must never collapse into one -- callers must keep
them displayed separately, per the design doc's explicit requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CLINICAL_MEDICINE_V1 = "clinical_medicine_v1"

# GRADE-inspired study-design tiers -- study design is GRADE's own primary
# starting point for evidence certainty, the closest named, citable
# standard available (see docs/ai_interface_layer_scoping.md's Discovery
# Engine section). `clinical_medicine_v1`-scoped only.
_STUDY_DESIGN_WEIGHTS: dict[str, int] = {
    "systematic_review_meta_analysis": 40,
    "meta_analysis": 40,
    "systematic_review": 40,
    "randomized_controlled_trial": 35,
    "cross_over_trial": 35,
    "prospective_observational_cohort": 25,
    "cohort_study": 25,
    "retrospective_observational_cohort": 15,
    "retrospective_study": 15,
    "cross_sectional_study": 15,
    "observational_study": 15,
    "pilot_study": 5,
    "case_report": 5,
}

_MANUAL_EXTRACTION_METHODS = frozenset({"manual_human_review", "manual"})

# Relationship types whose count feeds the reliability label. `supersedes`
# is deliberately excluded -- it retires the older claim rather than
# stating current agreement/disagreement; see
# docs/stability_and_tracking_design.md.
_CONSENSUS_ELIGIBLE_TYPES = frozenset({"supports", "contradicts", "qualifies", "contextualizes"})
_AGREEMENT_TYPES = frozenset({"supports", "contradicts"})


@dataclass(frozen=True)
class EvidenceQuality:
    """How trustworthy is this one `EvidenceRecord`, on its own."""

    evidence_record_id: str
    score: int
    study_design_tier: str
    study_type_missing: bool
    manually_reviewed: bool


def compute_evidence_quality(record: dict[str, Any]) -> EvidenceQuality:
    """Compute Evidence Quality for one `EvidenceRecord` dict.

    Three deterministic, independently inspectable components: a
    study-design weight (0-40), extraction rigor (25 or 40), and a
    completeness penalty (0 to -10) for missing `limitations` or
    `uncertainty_notes`. Summed, clamped to the achievable [0, 80] raw
    range, then scaled to a 0-100 display score. No component reads or
    invents a field the record does not already have -- notably, no
    `sample_size` term, since that field does not exist in
    `EvidenceRecord` today (see the design doc's real-data audit).
    """

    evidence_record_id = str(record.get("evidence_record_id", ""))
    study_type = record.get("study_type")
    design_points = _STUDY_DESIGN_WEIGHTS.get(study_type, 0) if study_type else 0
    tier = (
        study_type
        if study_type in _STUDY_DESIGN_WEIGHTS
        else ("missing" if not study_type else "unrecognized")
    )

    extraction_method = record.get("extraction_method")
    review_checklist = record.get("review_checklist") or {}
    manually_reviewed = extraction_method in _MANUAL_EXTRACTION_METHODS and bool(review_checklist)
    rigor_points = 40 if manually_reviewed else 25

    penalty = 0
    if not record.get("limitations"):
        penalty -= 5
    if not record.get("uncertainty_notes"):
        penalty -= 5

    raw = max(0, min(80, design_points + rigor_points + penalty))
    score = round(raw * 1.25)

    return EvidenceQuality(
        evidence_record_id=evidence_record_id,
        score=score,
        study_design_tier=tier,
        study_type_missing=not study_type,
        manually_reviewed=manually_reviewed,
    )


@dataclass(frozen=True)
class EvidenceConsensus:
    """How consistently the literature agrees, for claims compared to each other at all."""

    relationship_edge_count: int
    supports_count: int
    contradicts_count: int
    score: int | None
    reliability: str


def compute_evidence_consensus(relationship_types: list[str]) -> EvidenceConsensus:
    """Compute Evidence Consensus from the relationship-edge types touching one claim.

    Only reads already-authored `RelationshipRecord` types -- never infers
    or creates a relationship. Fewer than 2 eligible edges (or 2+ edges
    that are entirely `qualifies`/`contextualizes`, with nothing to form a
    supports/contradicts ratio from) means no score is shown at all,
    labeled `insufficient` -- displaying a number here would imply
    agreement data that does not exist. `supersedes` edges do not count
    toward eligibility; see `docs/stability_and_tracking_design.md`.
    """

    eligible = [t for t in relationship_types if t in _CONSENSUS_ELIGIBLE_TYPES]
    edge_count = len(eligible)
    supports = eligible.count("supports")
    contradicts = eligible.count("contradicts")
    agreement_total = supports + contradicts

    if edge_count < 2:
        reliability = "insufficient"
    elif edge_count == 2:
        reliability = "low"
    elif edge_count <= 4:
        reliability = "moderate"
    else:
        reliability = "high"

    score = (
        round(supports / agreement_total * 100) if edge_count >= 2 and agreement_total > 0 else None
    )

    return EvidenceConsensus(
        relationship_edge_count=edge_count,
        supports_count=supports,
        contradicts_count=contradicts,
        score=score,
        reliability=reliability,
    )


@dataclass(frozen=True)
class ClaimConfidence:
    """Given quality and consensus together, how confident should we be right now."""

    score: int | None
    reliability: str
    mean_evidence_quality: float | None


def compute_claim_confidence(
    participating_qualities: list[EvidenceQuality], consensus: EvidenceConsensus
) -> ClaimConfidence:
    """Combine Evidence Quality and Evidence Consensus -- a product, never an average or max.

    Per `docs/ai_layer_architecture.md`: ten low-quality-but-agreeing
    studies must not produce high combined confidence, so this multiplies
    rather than averages. If Evidence Consensus has no score (fewer than 2
    eligible relationship edges), Claim Confidence is not computed at all
    -- the claim's own Evidence Quality is still valid and displayable,
    just not a combined confidence number.
    """

    if consensus.score is None or not participating_qualities:
        return ClaimConfidence(
            score=None, reliability=consensus.reliability, mean_evidence_quality=None
        )

    mean_quality = sum(quality.score for quality in participating_qualities) / len(
        participating_qualities
    )
    score = round((mean_quality / 100) * (consensus.score / 100) * 100)
    return ClaimConfidence(
        score=score, reliability=consensus.reliability, mean_evidence_quality=mean_quality
    )


@dataclass(frozen=True)
class EvidenceCoverage:
    """Corpus-relative coverage: how much of the corpus participates in a confirmed relationship.

    Deliberately corpus-relative, not universe-relative -- this project has
    no defensible estimate of how many relevant papers exist in the real
    literature, and inventing one would violate the seam. See the design
    doc's "Evidence Coverage" section.
    """

    total_records: int
    records_in_relationship: int
    percentage: int


def compute_evidence_coverage(
    *, total_records: int, records_in_relationship: int
) -> EvidenceCoverage:
    """Compute corpus-relative Evidence Coverage."""

    percentage = round(records_in_relationship / total_records * 100) if total_records else 0
    return EvidenceCoverage(
        total_records=total_records,
        records_in_relationship=records_in_relationship,
        percentage=percentage,
    )


def render_synthesis(
    *,
    consensus: EvidenceConsensus,
    quality: EvidenceQuality,
    confidence: ClaimConfidence,
    coverage: EvidenceCoverage,
) -> list[str]:
    """Render a deterministic, templated synthesis over the computed numbers.

    Not an LLM call -- see the design doc's "Synthesis, without an LLM"
    section. Every line here is directly traceable to a computed field
    above; nothing is generated prose.
    """

    lines = [
        f"{consensus.relationship_edge_count} relationship(s) recorded for this claim: "
        f"{consensus.supports_count} support, {consensus.contradicts_count} contradict.",
        f"Evidence Quality: {quality.score}/100 ({quality.study_design_tier}, "
        f"{'manually reviewed' if quality.manually_reviewed else 'automated, pending review'}).",
    ]
    if consensus.score is None:
        lines.append(
            f"Evidence Consensus: not yet assessable (reliability: {consensus.reliability})."
        )
        lines.append(
            "Claim Confidence: not yet assessable (needs at least one more relationship edge)."
        )
    else:
        lines.append(
            f"Evidence Consensus: {consensus.score}/100 "
            f"({consensus.supports_count} of {consensus.relationship_edge_count} agree)."
        )
        lines.append(
            f"Claim Confidence: {confidence.score}/100, reliability: {confidence.reliability} "
            f"({consensus.relationship_edge_count} relationships)."
        )
    lines.append(
        f"Evidence coverage: {coverage.records_in_relationship} of {coverage.total_records} "
        f"corpus records ({coverage.percentage}%) participate in a confirmed relationship."
    )
    return lines
