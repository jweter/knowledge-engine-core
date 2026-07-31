from knowledge_engine.extraction import TABLE_FILTER_RULES_VERSION, is_table_derived


def test_table_filter_rules_version_is_stable() -> None:
    assert TABLE_FILTER_RULES_VERSION == "table-filter-v1"


def test_is_table_derived_returns_false_without_table_text() -> None:
    long_sentence = "word " * 100

    assert is_table_derived(long_sentence, None) is False
    assert is_table_derived(long_sentence, "") is False


def test_is_table_derived_returns_false_for_short_sentences() -> None:
    """Even a sentence entirely composed of table words is not flagged if short --
    the length floor exists because short sentences too easily share a few
    words with a table caption by coincidence."""

    table_text = "Outcome Value 95% CI p-value 12.4 0.001"
    short_sentence = "Outcome Value 95% CI."

    assert is_table_derived(short_sentence, table_text) is False


def test_is_table_derived_flags_a_long_sentence_with_high_table_word_overlap() -> None:
    table_text = (
        "Characteristic Value Semaglutide Dulaglutide SMD Age years "
        "59.3 59.3 0.001 Sex Female 1393 1777 0.006"
    )
    sentence = (
        "Characteristic Value Semaglutide Dulaglutide SMD "
        "Age years 59.3 59.3 0.001 Sex Female"
    ) * 5  # pad past the length floor while keeping high word overlap

    assert is_table_derived(sentence, table_text) is True


def test_is_table_derived_does_not_flag_a_long_real_sentence() -> None:
    table_text = "Outcome Placebo Semaglutide RR 95% CI 0.9 1.85 (1.20, 2.50)"
    real_sentence = (
        "In this randomized, double-blind, placebo-controlled trial, participants "
        "receiving semaglutide 2.4 mg once weekly experienced significantly greater "
        "reductions in body weight compared with those receiving placebo, with the "
        "effect sustained through the full 104-week treatment period and observed "
        "consistently across all prespecified demographic and clinical subgroups, "
        "including older adults, those with prediabetes, and participants enrolled "
        "at sites across multiple countries and regions worldwide."
    )

    assert len(real_sentence) >= 400
    assert is_table_derived(real_sentence, table_text) is False


def test_is_table_derived_overlap_ratio_boundary() -> None:
    """A sentence with well under 30% table-word overlap is not flagged; one
    with well over 30% overlap is -- verified overlap ratios (not just
    plausible-looking strings), since this threshold is the crux of the
    whole filter."""

    table_text = "alpha beta gamma delta epsilon"
    # ~10% overlap: 1 table word ("alpha") in ~10 total words, repeated.
    below_threshold = ("alpha unrelated words that pad out the length past four hundred " * 8)[
        :420
    ]
    # ~34% overlap: 2 table words ("alpha", "beta") in 6 total words, repeated.
    above_threshold = ("alpha beta unrelated pad words here " * 12)[:420]

    assert len(below_threshold) >= 400
    assert len(above_threshold) >= 400
    assert is_table_derived(below_threshold, table_text) is False
    assert is_table_derived(above_threshold, table_text) is True
