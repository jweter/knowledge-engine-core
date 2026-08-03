from typing import TypedDict, cast

from knowledge_engine.evidence_review_automate import automate_review_for_record
from knowledge_engine.extraction import LLM_GROUNDED_PICO_RULES_VERSION

_PAGE_TEXT = (
    "A total of 318 participants were enrolled. Participants received "
    "SiPore21 or a matching placebo for 12 weeks. The primary endpoint "
    "was change in HbA1c from baseline to Week 12. SiPore21 significantly "
    "reduced HbA1c from baseline (p=0.0036), whereas no significant "
    "reduction was observed with placebo (p=0.0872)."
)


class _ReviewChecklist(TypedDict):
    automated_classification: bool
    llm_grounded: bool
    human_reviewed: bool
    fields_grounded: list[str]


class _FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        return self.response


def _automated_record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "evidence_record_id": "auto-001",
        "extraction_method": "m52-evidence-classification-v1",
        "claim_text": "SiPore21 significantly reduced HbA1c from baseline (p=0.0036).",
        "population": "ARTICLE HISTORY boilerplate glued on by mistake.",
        "intervention": "ARTICLE HISTORY boilerplate glued on by mistake.",
        "comparator": None,
        "outcome": None,
        "source_span": {"section": "results", "page_number": 1},
        "review_checklist": {},
    }
    record.update(overrides)
    return record


def test_grounded_fields_are_written_and_record_is_relabeled() -> None:
    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "Participants received SiPore21 or a matching placebo for 12 weeks.", '
        '"comparator": "", "outcome": ""}'
    )
    record = _automated_record()

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert result.updated is True
    assert set(result.fields_grounded) == {"population", "intervention"}
    assert record["population"] == "A total of 318 participants were enrolled."
    assert record["intervention"] == (
        "Participants received SiPore21 or a matching placebo for 12 weeks."
    )
    assert record["extraction_method"] == LLM_GROUNDED_PICO_RULES_VERSION
    checklist = cast(_ReviewChecklist, record["review_checklist"])
    assert checklist["llm_grounded"] is True
    assert checklist["human_reviewed"] is False
    assert "population" in checklist["fields_grounded"]


def test_ungrounded_fields_are_left_unchanged_not_blanked() -> None:
    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "", "comparator": "", "outcome": ""}'
    )
    record = _automated_record()
    original_intervention = record["intervention"]

    automate_review_for_record(llm, record, _PAGE_TEXT)

    assert record["intervention"] == original_intervention


def test_fabricated_field_is_never_accepted() -> None:
    llm = _FakeLLM(
        '{"population": "", "intervention": "", "comparator": "", '
        '"outcome": "Tirzepatide reduced HbA1c by 2.1% versus insulin glargine."}'
    )
    record = _automated_record()

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert "outcome" not in result.fields_grounded
    assert record["outcome"] is None


def test_no_grounded_field_leaves_record_untouched() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')
    record = _automated_record()
    original = dict(record)

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert result.updated is False
    assert result.skipped_reason == "no PICO field passed grounding"
    assert record == original


def test_already_manually_reviewed_record_is_skipped() -> None:
    llm = _FakeLLM(
        '{"population": "irrelevant", "intervention": "", "comparator": "", "outcome": ""}'
    )
    record = _automated_record(extraction_method="manual_human_review")

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert result.updated is False
    assert result.skipped_reason == "already manually reviewed"
    assert record["extraction_method"] == "manual_human_review"


def test_human_reviewed_checklist_is_skipped_even_with_old_extraction_method() -> None:
    """A human-reviewed record keeps its prior `extraction_method` as
    provenance (the convention `_build_evidence_review_queue` documents) --
    only `review_checklist.human_reviewed` marks it as actually reviewed.
    The automation must honor that convention, not just the literal
    `extraction_method` value, or it will silently reprocess and overwrite
    a genuinely human-reviewed record."""

    llm = _FakeLLM(
        '{"population": "irrelevant", "intervention": "", "comparator": "", "outcome": ""}'
    )
    record = _automated_record(
        extraction_method="m52-evidence-classification-v1",
        review_checklist={"human_reviewed": True, "source_verified": True},
    )
    original_population = record["population"]

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert result.updated is False
    assert result.skipped_reason == "already manually reviewed"
    assert record["population"] == original_population
    assert record["extraction_method"] == "m52-evidence-classification-v1"


def test_review_checklist_merge_preserves_existing_keys() -> None:
    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "", "comparator": "", "outcome": ""}'
    )
    record = _automated_record(review_checklist={"some_other_key": "kept"})

    automate_review_for_record(llm, record, _PAGE_TEXT)

    checklist = record["review_checklist"]
    assert isinstance(checklist, dict)
    assert checklist["some_other_key"] == "kept"
    assert checklist["llm_grounded"] is True


def test_missing_claim_text_is_skipped() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')
    record = _automated_record(claim_text=None)

    result = automate_review_for_record(llm, record, _PAGE_TEXT)

    assert result.updated is False
    assert result.skipped_reason == "no claim_text on this record"


def test_missing_page_text_is_skipped() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')
    record = _automated_record()

    result = automate_review_for_record(llm, record, None)

    assert result.updated is False
    assert result.skipped_reason == "source page text unavailable"
