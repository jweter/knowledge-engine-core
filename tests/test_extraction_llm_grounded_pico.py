from knowledge_engine.extraction.claims import ClaimCandidate
from knowledge_engine.extraction.llm_grounded_pico import (
    LLM_GROUNDED_PICO_RULES_VERSION,
    extract_pico_for_candidate,
)
from knowledge_engine.llm import LocalLLMError

_PAGE_TEXT = (
    "A total of 318 participants were enrolled. Participants received "
    "SiPore21 or a matching placebo for 12 weeks. The primary endpoint "
    "was change in HbA1c from baseline to Week 12. SiPore21 significantly "
    "reduced HbA1c from baseline (p=0.0036), whereas no significant "
    "reduction was observed with placebo (p=0.0872)."
)


class _FakeLLM:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.prompts: list[str] = []
        self.max_tokens_seen: list[int] = []

    def generate(self, prompt: str, *, max_tokens: int = 400) -> str:
        self.prompts.append(prompt)
        self.max_tokens_seen.append(max_tokens)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _candidate() -> ClaimCandidate:
    sentence = "SiPore21 significantly reduced HbA1c from baseline (p=0.0036)."
    return ClaimCandidate(
        sentence_text=sentence,
        section_type="results",
        page_number=1,
        start_offset=0,
        end_offset=len(sentence),
        matched_signal="p_value",
        rules_version="test",
    )


def test_all_fields_grounded_when_llm_quotes_the_page_verbatim() -> None:
    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "Participants received SiPore21 or a matching placebo for 12 weeks.", '
        '"comparator": "Participants received SiPore21 or a matching placebo for 12 weeks.", '
        '"outcome": "The primary endpoint was change in HbA1c from baseline to Week 12."}'
    )

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.rules_version == LLM_GROUNDED_PICO_RULES_VERSION
    assert result.population.value == "A total of 318 participants were enrolled."
    assert result.population.grounding is not None
    assert result.population.grounding.grounded is True
    assert result.intervention.value is not None
    assert result.outcome.value is not None


def test_fabricated_field_is_dropped_not_accepted() -> None:
    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "", '
        '"comparator": "", '
        '"outcome": "Tirzepatide reduced HbA1c by 2.1% versus insulin glargine."}'
    )

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value is not None
    assert result.outcome.value is None
    assert result.outcome.grounding is not None
    assert result.outcome.grounding.grounded is False


def test_empty_string_fields_are_ungrounded_with_no_grounding_result() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value is None
    assert result.population.grounding is None
    assert result.intervention.value is None
    assert result.comparator.value is None
    assert result.outcome.value is None


def test_llm_response_wrapped_in_markdown_code_fence_is_still_parsed() -> None:
    llm = _FakeLLM(
        "```json\n"
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "", "comparator": "", "outcome": ""}\n'
        "```"
    )

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value == "A total of 318 participants were enrolled."


def test_malformed_json_response_leaves_every_field_ungrounded() -> None:
    llm = _FakeLLM("I could not find any relevant information on this page.")

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value is None
    assert result.intervention.value is None
    assert result.comparator.value is None
    assert result.outcome.value is None


def test_llm_error_leaves_every_field_ungrounded_rather_than_raising() -> None:
    llm = _FakeLLM(LocalLLMError("Could not reach Ollama."))

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value is None
    assert result.intervention.value is None
    assert result.comparator.value is None
    assert result.outcome.value is None


def test_prompt_includes_the_candidate_sentence_and_page_text() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')
    candidate = _candidate()

    extract_pico_for_candidate(llm, candidate, _PAGE_TEXT)

    assert len(llm.prompts) == 1
    assert candidate.sentence_text in llm.prompts[0]
    assert _PAGE_TEXT in llm.prompts[0]


def test_max_tokens_is_passed_through_to_the_llm() -> None:
    llm = _FakeLLM('{"population": "", "intervention": "", "comparator": "", "outcome": ""}')

    extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT, max_tokens=250)

    assert llm.max_tokens_seen == [250]


def test_trailing_brace_after_the_json_object_does_not_corrupt_parsing() -> None:
    """A greedy `\\{.*\\}` regex would span from the first `{` all the way to
    the LAST `}` in the response, swallowing this trailing aside and
    producing invalid JSON -- the fix bounds the match to a single flat,
    non-nested object, so the real answer still parses."""

    llm = _FakeLLM(
        '{"population": "A total of 318 participants were enrolled.", '
        '"intervention": "", "comparator": "", "outcome": ""} '
        "Note: the shape above follows the format shown as {example}."
    )

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.population.value == "A total of 318 participants were enrolled."


def test_a_field_only_present_in_an_unrelated_paper_section_is_not_grounded() -> None:
    """A proposed field that sounds plausible but is not actually on this
    page must fail grounding -- the check is presence, not plausibility."""

    llm = _FakeLLM(
        '{"population": "", "intervention": "", "comparator": "", '
        '"outcome": "No serious adverse events were reported during the trial."}'
    )

    result = extract_pico_for_candidate(llm, _candidate(), _PAGE_TEXT)

    assert result.outcome.value is None
