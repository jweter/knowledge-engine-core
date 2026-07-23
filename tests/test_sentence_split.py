from knowledge_engine.sentence_split import split_sentence_spans, split_sentences


def test_splits_on_terminal_punctuation_followed_by_capital() -> None:
    text = "First sentence. Second sentence! Third sentence?"
    assert split_sentences(text) == [
        "First sentence.",
        "Second sentence!",
        "Third sentence?",
    ]


def test_does_not_split_at_a_known_abbreviation() -> None:
    text = "Outcomes vs. controls were compared. A second sentence follows."
    assert split_sentences(text) == [
        "Outcomes vs. controls were compared.",
        "A second sentence follows.",
    ]


def test_does_not_split_at_et_al() -> None:
    text = "Smith et al. reported a large effect. Later work confirmed it."
    assert split_sentences(text) == [
        "Smith et al. reported a large effect.",
        "Later work confirmed it.",
    ]


def test_single_sentence_with_no_terminal_punctuation() -> None:
    assert split_sentences("A title with no terminal punctuation") == [
        "A title with no terminal punctuation"
    ]


def test_empty_text_produces_no_sentences() -> None:
    assert split_sentences("") == []


def test_split_sentence_spans_returns_offsets_into_original_text() -> None:
    text = "First sentence. Second sentence."
    spans = split_sentence_spans(text)
    assert [text[start:end] for start, end in spans] == [
        "First sentence.",
        "Second sentence.",
    ]
