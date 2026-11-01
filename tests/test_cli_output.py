from tests.cli_output import unwrapped


def test_unwrapped_rejoins_a_sentence_split_across_panel_lines() -> None:
    panel = (
        "\x1b[31m\u256d\u2500\u2500 Error \u2500\u2500\u256e\x1b[0m\n"
        "\u2502 Output file already exists: C:\a\very\long\path.json. Use --force to \u2502\n"
        "\u2502 overwrite.                                                      \u2502\n"
        "\u2570\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u256f\n"
    )

    assert "Use --force to overwrite." in unwrapped(panel)
    assert "\x1b" not in unwrapped(panel)


def test_unwrapped_leaves_plain_text_readable() -> None:
    assert unwrapped("a  b\n\tc") == "a b c"
