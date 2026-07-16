"""Deterministic planning for immutable resume and retry import runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from knowledge_engine.models import ImportItem

RunMode = Literal["resume", "retry_failed"]
PlanAction = Literal["process", "skip"]

_SAFE_PRIOR_STATUSES = {"imported"}
_SAFE_DUPLICATE_OUTCOMES = {
    "exact_hash_duplicate",
    "doi_same_hash_duplicate",
}


@dataclass(frozen=True)
class PlannedImportItem:
    """One deterministic decision for an item in a new linked run."""

    source_id: str
    action: PlanAction
    reason_code: str
    prior_import_item_id: str | None


@dataclass(frozen=True)
class ImportRunPlan:
    """Immutable resume/retry plan derived from one prior run."""

    mode: RunMode
    parent_import_run_id: str
    items: tuple[PlannedImportItem, ...]


def plan_linked_run(
    *,
    mode: RunMode,
    parent_import_run_id: str,
    current_items: list[ImportItem],
    prior_items: list[ImportItem],
) -> ImportRunPlan:
    """Plan a new run without mutating prior attempts or using manifest row order."""

    current_by_source = _items_by_source_id(current_items, label="current")
    prior_by_source = _items_by_source_id(prior_items, label="prior")

    planned: list[PlannedImportItem] = []
    for source_id in sorted(current_by_source):
        prior = prior_by_source.get(source_id)
        if mode == "resume":
            planned.append(_plan_resume_item(source_id, prior))
        else:
            planned.append(_plan_retry_item(source_id, prior))

    return ImportRunPlan(
        mode=mode,
        parent_import_run_id=parent_import_run_id,
        items=tuple(planned),
    )


def _items_by_source_id(
    items: list[ImportItem], *, label: str
) -> dict[str, ImportItem]:
    indexed: dict[str, ImportItem] = {}
    for item in items:
        source_id = (item.source_id or "").strip()
        if not source_id:
            raise ValueError(f"{label} import item is missing stable source_id")
        if source_id in indexed:
            raise ValueError(
                f"{label} import items contain duplicate source_id: {source_id}"
            )
        indexed[source_id] = item
    return indexed


def _plan_resume_item(source_id: str, prior: ImportItem | None) -> PlannedImportItem:
    if prior is None:
        return PlannedImportItem(source_id, "process", "new_source", None)
    if prior.item_status in _SAFE_PRIOR_STATUSES:
        return PlannedImportItem(
            source_id,
            "skip",
            "prior_success",
            prior.import_item_id,
        )
    if (
        prior.item_status == "skipped"
        and prior.duplicate_outcome in _SAFE_DUPLICATE_OUTCOMES
    ):
        return PlannedImportItem(
            source_id,
            "skip",
            "prior_safe_duplicate",
            prior.import_item_id,
        )
    if prior.item_status == "failed":
        return PlannedImportItem(
            source_id,
            "skip",
            "failed_requires_explicit_retry",
            prior.import_item_id,
        )
    return PlannedImportItem(
        source_id,
        "process",
        "prior_unresolved",
        prior.import_item_id,
    )


def _plan_retry_item(source_id: str, prior: ImportItem | None) -> PlannedImportItem:
    if prior is not None and prior.item_status == "failed":
        return PlannedImportItem(
            source_id,
            "process",
            "retry_prior_failure",
            prior.import_item_id,
        )
    return PlannedImportItem(
        source_id,
        "skip",
        "not_failed_in_parent",
        prior.import_item_id if prior is not None else None,
    )
