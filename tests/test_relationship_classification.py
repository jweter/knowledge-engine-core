from knowledge_engine.llm import LocalLLMError
from knowledge_engine.relationship_classification import (
    ALLOWED_RELATIONSHIP_TYPES,
    classify_relationship,
)


class _FakeLLM:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        del prompt, max_tokens
        return self.response


def _claim(**overrides: object) -> dict[str, object]:
    claim: dict[str, object] = {
        "evidence_record_id": "ev-a",
        "claim_text": "Semaglutide reduced body weight versus placebo (p<0.001).",
        "outcome": "Mean percent body weight change from baseline.",
        "result_summary": "Mean difference -12.4 kg (95% CI -13.4 to -11.5).",
    }
    claim.update(overrides)
    return claim


def test_accepts_a_grounded_proposal_with_a_valid_relationship_type() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "supports", '
        '"quoted_evidence": "Semaglutide reduced body weight versus placebo (p<0.001).", '
        '"rationale": "Both claims report the same direction of effect for semaglutide '
        'versus placebo on body weight."}'
    )
    claim_a = _claim()
    claim_b = _claim(evidence_record_id="ev-b")

    result = classify_relationship(llm, claim_a, claim_b)

    assert result.accepted is True
    assert result.relationship_type == "supports"
    assert result.source_evidence_record_id == "ev-a"
    assert result.target_evidence_record_id == "ev-b"
    assert result.skipped_reason is None
    assert "same direction of effect" in (result.rationale or "")


def test_rejects_an_unrecognized_relationship_type() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "refutes", '
        '"quoted_evidence": "Semaglutide reduced body weight versus placebo (p<0.001).", '
        '"rationale": "These claims disagree."}'
    )

    result = classify_relationship(llm, _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert result.relationship_type is None
    assert "unrecognized relationship_type" in (result.skipped_reason or "")


def test_rejects_quoted_evidence_not_grounded_in_either_claim() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "contradicts", '
        '"quoted_evidence": "This drug caused a total reversal of diabetes in every '
        'participant studied.", '
        '"rationale": "The two claims disagree about the drug\'s effect."}'
    )

    result = classify_relationship(llm, _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert result.relationship_type is None
    assert "not grounded" in (result.skipped_reason or "")


def test_rejects_unparseable_model_output() -> None:
    llm = _FakeLLM("I think these two claims are related somehow.")

    result = classify_relationship(llm, _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert result.skipped_reason == "model output not parseable"


def test_rejects_an_empty_quoted_evidence() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "supports", "quoted_evidence": "", "rationale": "Because reasons."}'
    )

    result = classify_relationship(llm, _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert result.skipped_reason == "empty quoted_evidence or rationale"


def test_rejects_an_empty_rationale() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "supports", '
        '"quoted_evidence": "Semaglutide reduced body weight versus placebo (p<0.001).", '
        '"rationale": ""}'
    )

    result = classify_relationship(llm, _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert result.skipped_reason == "empty quoted_evidence or rationale"


def test_all_allowed_relationship_types_are_the_project_schema_five() -> None:
    assert set(ALLOWED_RELATIONSHIP_TYPES) == {
        "supports",
        "contradicts",
        "qualifies",
        "contextualizes",
        "supersedes",
    }


def test_grounding_can_pass_using_only_the_second_claims_text() -> None:
    llm = _FakeLLM(
        '{"relationship_type": "qualifies", '
        '"quoted_evidence": "Mean difference -12.4 kg (95% CI -13.4 to -11.5).", '
        '"rationale": "The confidence interval is wide relative to the effect size."}'
    )
    claim_a = _claim(claim_text=None, outcome=None, result_summary=None)
    claim_b = _claim(evidence_record_id="ev-b")

    result = classify_relationship(llm, claim_a, claim_b)

    assert result.accepted is True
    assert result.relationship_type == "qualifies"


def test_model_call_failure_is_reported_not_raised() -> None:
    class _RaisingLLM:
        def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
            del prompt, max_tokens
            raise LocalLLMError("Ollama unreachable")

    result = classify_relationship(_RaisingLLM(), _claim(), _claim(evidence_record_id="ev-b"))

    assert result.accepted is False
    assert "model call failed" in (result.skipped_reason or "")
