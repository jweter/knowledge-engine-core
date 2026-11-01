"""Helpers for asserting on CLI output that Rich may have wrapped."""

from __future__ import annotations

import re

from click import unstyle

# Rich draws error panels with these glyphs; a wrapped sentence can span panel lines.
_PANEL_BORDERS = re.compile("[│╭╮╰╯─]")


def unwrapped(output: str) -> str:
    """Return ``output`` as one line of single-spaced text, without ANSI styling or panel borders.

    Rich wraps messages to the console width, and a message that embeds a temporary path wraps at
    a different place for every path length, so substring assertions must not depend on it.
    """

    return " ".join(_PANEL_BORDERS.sub(" ", unstyle(output)).split())
