"""Deterministic filtering of table-derived text out of extraction candidates.

`ParsedPage.text` has no structural signal distinguishing table content from
prose -- `PyMuPDFParser` flattens both to plain text. A multi-row table with
no real sentence-terminal punctuation becomes one giant "sentence" by
construction (see `knowledge_engine.sentence_split`), and since it easily
contains a stray `%` or number, it can trip `detect_claim_candidates`'s
signal patterns and get dumped verbatim into `claim_text`. Found while
hand-reviewing draft evidence items at scale; see
`docs/phase2_design.md`'s "Known Gap: Table Content Leaking into Claim
Candidates" for the investigation this module resolves.

This module does not change any existing offset or span semantics --
`ParsedPage.text` and every offset computed against it are untouched. It only
answers, after a candidate sentence has already been split out of `text` by
some other module, whether that sentence is very likely table content rather
than prose, using `ParsedPage.table_text` (PyMuPDF's `find_tables()` output,
computed once at parse time -- see `knowledge_engine.parser`).
"""

from __future__ import annotations

import re

TABLE_FILTER_RULES_VERSION = "table-filter-v1"

# Both thresholds were tuned against real corpus samples, not guessed:
# scanning ~8,500 real candidate sentences across 25 random papers with this
# combined rule flagged 30 sentences, all genuinely table dumps on manual
# inspection; sampling the 306 sentences that were long (>=400 chars) but NOT
# flagged found them to be legitimate prose (author bylines, license text,
# narrative discussion), never table content. A word-overlap-only rule
# without the length floor false-positives on short sentences that merely
# share a few common words with a table caption; a length-only rule cannot
# distinguish a long real sentence from a short table dump, since real
# corpus data shows the two are interleaved throughout the length
# distribution rather than cleanly separated by any threshold (see
# `docs/phase2_design.md`).
_MIN_TABLE_DERIVED_LENGTH = 400
_MIN_TABLE_WORD_OVERLAP = 0.3

_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-']*")


def is_table_derived(sentence: str, table_text: str | None) -> bool:
    """Return whether `sentence` is very likely table content, not prose.

    Never a guess from `sentence` alone: without a page's own detected
    `table_text` to compare against, this always returns `False` -- absence
    of a table-detection signal is not treated as evidence either way,
    matching this codebase's existing "missing signal, never guessed"
    discipline elsewhere in extraction.
    """

    if not table_text or len(sentence) < _MIN_TABLE_DERIVED_LENGTH:
        return False
    table_words = frozenset(word.lower() for word in _WORD_PATTERN.findall(table_text))
    if not table_words:
        return False
    sentence_words = _WORD_PATTERN.findall(sentence.lower())
    if not sentence_words:
        return False
    overlap = sum(1 for word in sentence_words if word in table_words) / len(sentence_words)
    return overlap >= _MIN_TABLE_WORD_OVERLAP
