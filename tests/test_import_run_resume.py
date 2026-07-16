from knowledge_engine.import_runs.resume import plan_linked_run
from knowledge_engine.models import ImportItem


def _item(
    item_id: str,
    source_id: str | None,
    *,
    status: str,
    duplicate_outcome: str | None = None,
) -> ImportItem:
    return ImportItem(
        import_item_id=item_id,
        import_run_id="run",
        source_id=source_id,
        csv_line_number=1,
        title="Title",
        normalized_doi=None,
        inclusion_status="included",
        usage_status="approved_open_access",
        local_path="paper.pdf",
        item_status=status,
        duplicate_outcome=duplicate_outcome,
        matched_paper_id=None,
        matched_import_item_id=None,
        computed_content_hash=None,
        duplicate_evidence_json=None,
        retry_of_import_item_id=None,
        blocks_manifest=False,
        blocks_import=False,
        warning_count=0,
        structural_error_count=0,
        import_blocker_count=0,
        created_at="2026-07-16T00:00:00+00:00",
        completed_at="2026-07-16T00:00:00+00:00",
    )


def test_resume_uses_stable_source_identity_and_skips_safe_prior_outcomes() -> None:
    current = [
        _item("current-new", "source-new", status="valid"),
        _item("current-success", "source-success", status="valid"),
        _item("current-duplicate", "source-duplicate", status="valid"),
        _item("current-failed", "source-failed", status="valid"),
        _item("current-review", "source-review", status="valid"),
    ]
    prior = [
        _item("prior-review", "source-review", status="needs_review"),
        _item("prior-failed", "source-failed", status="failed"),
        _item("prior-success", "source-success", status="imported"),
        _item(
            "prior-duplicate",
            "source-duplicate",
            status="skipped",
            duplicate_outcome="exact_hash_duplicate",
        ),
    ]

    plan = plan_linked_run(
        mode="resume",
        parent_import_run_id="parent-run",
        current_items=current,
        prior_items=prior,
    )

    decisions = {item.source_id: (item.action, item.reason_code) for item in plan.items}
    assert decisions == {
        "source-duplicate": ("skip", "prior_safe_duplicate"),
        "source-failed": ("skip", "failed_requires_explicit_retry"),
        "source-new": ("process", "new_source"),
        "source-review": ("process", "prior_unresolved"),
        "source-success": ("skip", "prior_success"),
    }
    assert plan.parent_import_run_id == "parent-run"


def test_retry_failed_processes_only_failed_parent_items() -> None:
    current = [
        _item("current-failed", "source-failed", status="valid"),
        _item("current-success", "source-success", status="valid"),
        _item("current-new", "source-new", status="valid"),
    ]
    prior = [
        _item("prior-success", "source-success", status="imported"),
        _item("prior-failed", "source-failed", status="failed"),
    ]

    plan = plan_linked_run(
        mode="retry_failed",
        parent_import_run_id="parent-run",
        current_items=current,
        prior_items=prior,
    )

    decisions = {item.source_id: (item.action, item.reason_code) for item in plan.items}
    assert decisions == {
        "source-failed": ("process", "retry_prior_failure"),
        "source-new": ("skip", "not_failed_in_parent"),
        "source-success": ("skip", "not_failed_in_parent"),
    }
    failed = next(item for item in plan.items if item.source_id == "source-failed")
    assert failed.prior_import_item_id == "prior-failed"


def test_planning_rejects_missing_or_duplicate_stable_source_identity() -> None:
    valid = [_item("prior", "source-1", status="failed")]

    try:
        plan_linked_run(
            mode="resume",
            parent_import_run_id="parent-run",
            current_items=[_item("missing", None, status="valid")],
            prior_items=valid,
        )
    except ValueError as exc:
        assert "missing stable source_id" in str(exc)
    else:
        raise AssertionError("missing source_id should fail closed")

    try:
        plan_linked_run(
            mode="resume",
            parent_import_run_id="parent-run",
            current_items=[
                _item("one", "source-1", status="valid"),
                _item("two", "source-1", status="valid"),
            ],
            prior_items=valid,
        )
    except ValueError as exc:
        assert "duplicate source_id" in str(exc)
    else:
        raise AssertionError("duplicate source_id should fail closed")
