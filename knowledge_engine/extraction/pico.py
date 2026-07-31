"""Deterministic PICO-adjacent extraction: population, intervention, comparator, outcome.

`docs/phase2_design.md`'s "Next priorities" note named full PICO extraction
extending M26's `study_type`/`limitations` methodology to free-form prose as
the next Phase 2 priority, since -- unlike a study-design phrase or a
"Limitations" heading -- PICO values are typically embedded in ordinary
sentences rather than signaled by a fixed heading. Tuning needed a real
corpus large enough to show real phrasing patterns; a sample of the 605-paper
`glp1_weight_loss` corpus's actual abstracts was read before writing the
patterns below, rather than guessing them speculatively (the same standard
`docs/phase2_design.md` already held M14/M17 to).

Each field is the first cue-matching sentence found in its scoped section
types, in document order -- never a summary, paraphrase, or guess. A field
with no matching cue is `None`, exactly like `classify_study_type` and
`extract_limitations`. Unlike `study_type` (a closed-vocabulary
classification), PICO values are free text: the matched sentence itself is
the value, the same shape as `ClaimCandidate.sentence_text`, since a fixed
label vocabulary cannot honestly represent an arbitrary population or
intervention description.

No new dependency and no LLM, matching the extraction methodology already
decided in `docs/phase2_design.md`. The accepted tradeoff is the same weaker
recall already documented there: real papers phrase population, intervention,
comparator, and outcome statements in enough different ways that a
conservative cue-phrase match will miss many of them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from knowledge_engine.extraction.sections import SectionSpan, section_page_ranges
from knowledge_engine.extraction.table_filter import is_table_derived
from knowledge_engine.parser import ParsedPage
from knowledge_engine.sentence_split import split_sentence_spans

PICO_EXTRACTION_RULES_VERSION = "m28-pico-v4"

# A study-design phrase or heading is usually reused verbatim; PICO values are
# not, so each field is scoped only to the section types most likely to state
# it plainly rather than reference someone else's prior work (mirroring
# `classify_study_type`'s Abstract/Methods-only scoping rationale). Outcome
# and comparator cues also appear in Results, since a paper's own primary
# outcome or comparison arm is frequently restated there.
#
# v2 (M38 follow-up): M16's section-detection v2 change (recognizing inline
# "Label: text" headings, not just a heading alone on its own line) now
# correctly splits a structured abstract's "Background: ... Methods: ...
# Results: ... Conclusion: ..." into separate methods/results/conclusion
# spans, where previously the whole thing stayed one undivided `abstract`
# span -- which every PICO field already scanned. Re-measuring after that fix
# showed PICO coverage regressed across the board (e.g. all-four-fields
# coverage dropped from 220 to 184 papers out of 943) because population and
# intervention cues that used to be reachable inside that single scanned
# abstract blob are now correctly labeled `results`/`conclusion`, section
# types those two fields never scanned. Widening scoping to match restores
# that reachability without loosening the cue patterns themselves.
#
# v3 (post-M40 batch-review finding): a single dense clinical-trial sentence
# routinely satisfies more than one field's cue pattern at once -- "304
# participants were randomly assigned to semaglutide 2.4 mg or placebo"
# matches both the population pattern (a cohort-size clause) and the
# intervention pattern ("assigned to"). Because each field used to scan
# independently for its own first match, this produced the same sentence
# duplicated verbatim across two or more fields on a real, measured 11-14%
# of draft items that had both fields populated -- clearly wrong to a human
# reviewer even though each individual match was itself correct. Extraction
# now proceeds in a fixed population -> intervention -> comparator -> outcome
# order and each field skips any sentence an earlier field already claimed,
# continuing to scan for the next distinct cue-matching sentence instead.
# This is still "the first cue-matching sentence, never a summary or
# paraphrase" -- just scoped to sentences not already spoken for by an
# earlier PICO field for the same paper.
#
# v4: scanning now proceeds per-page (via `section_page_ranges`, the same
# helper M17's claim-candidate detection uses) instead of over each
# section's already-joined multi-page text, so a candidate sentence can be
# checked against its own page's `table_text` and excluded when it is very
# likely table content -- see `knowledge_engine.extraction.table_filter`.
# A side effect, matching the same accepted precedent M17 already
# established: a sentence that spans across a page boundary is no longer
# joined into one continuous sentence for matching purposes.
_POPULATION_SECTION_TYPES = frozenset({"abstract", "methods", "results"})
_INTERVENTION_SECTION_TYPES = frozenset({"abstract", "methods", "results"})
_COMPARATOR_SECTION_TYPES = frozenset({"abstract", "methods", "results", "conclusion"})
_OUTCOME_SECTION_TYPES = frozenset({"abstract", "methods", "results", "conclusion"})

# A numeric cohort-size clause ("1,840,044 women without...", "253 patients
# with STEMI...", "4234 adults aged >= 18 years...") was the single most
# consistent population signal found reading real corpus abstracts -- far
# more consistent than any fixed keyword like "population" or "participants"
# alone, which not every paper uses.
_POPULATION_PATTERN = re.compile(
    r"(?i)\b\d[\d,]*\s+(?:patients|participants|subjects|women|men|adults|"
    r"children|volunteers|individuals)\b"
)
_INTERVENTION_PATTERN = re.compile(
    r"(?i)\b(?:received|administered|treated with|randomi[sz]ed to|assigned to|underwent)\b"
)
_COMPARATOR_PATTERN = re.compile(
    r"(?i)\b(?:versus|vs\.?|compared (?:to|with)|control group|placebo)\b"
)
_OUTCOME_PATTERN = re.compile(
    r"(?i)\b(?:primary outcome|secondary outcome|outcome measure|main outcome|"
    r"endpoint|assessed using|measured using|evaluated using)\b"
)


@dataclass(frozen=True)
class PicoFields:
    """One paper's deterministically extracted PICO-adjacent fields.

    Paper-level, like `study_type`/`limitations` -- the same value applies to
    every draft item generated from the same paper, since PICO describes the
    paper's overall design, not any one claim sentence.
    """

    population: str | None
    intervention: str | None
    comparator: str | None
    outcome: str | None
    rules_version: str


def extract_pico(pages: Sequence[ParsedPage], sections: Sequence[SectionSpan]) -> PicoFields:
    """Extract population/intervention/comparator/outcome from explicit cues.

    Returns a `PicoFields` with every field independently `None` when no
    scoped section or no cue match was found -- absence is never guessed
    into a low-confidence value. Fields are extracted in a fixed
    population -> intervention -> comparator -> outcome order and each later
    field skips any sentence an earlier field already claimed, so a single
    sentence that happens to satisfy two cue patterns at once is never
    duplicated verbatim across two fields.
    """

    claimed_sentences: set[str] = set()

    population = _first_matching_sentence(
        pages, sections, _POPULATION_SECTION_TYPES, _POPULATION_PATTERN, claimed_sentences
    )
    intervention = _first_matching_sentence(
        pages, sections, _INTERVENTION_SECTION_TYPES, _INTERVENTION_PATTERN, claimed_sentences
    )
    comparator = _first_matching_sentence(
        pages, sections, _COMPARATOR_SECTION_TYPES, _COMPARATOR_PATTERN, claimed_sentences
    )
    outcome = _first_matching_sentence(
        pages, sections, _OUTCOME_SECTION_TYPES, _OUTCOME_PATTERN, claimed_sentences
    )

    return PicoFields(
        population=population,
        intervention=intervention,
        comparator=comparator,
        outcome=outcome,
        rules_version=PICO_EXTRACTION_RULES_VERSION,
    )


def _first_matching_sentence(
    pages: Sequence[ParsedPage],
    sections: Sequence[SectionSpan],
    section_types: frozenset[str],
    pattern: re.Pattern[str],
    claimed_sentences: set[str],
) -> str | None:
    """Return the first cue-matching, not-yet-claimed sentence across scoped sections.

    Sentences already claimed by an earlier PICO field (for the same paper)
    are skipped in favor of the next distinct cue-matching sentence, so two
    fields never end up holding the exact same sentence. A sentence that is
    very likely table content (`is_table_derived`) is skipped the same way.
    The returned sentence is added to `claimed_sentences` before returning,
    so later fields see it as claimed too.
    """

    pages_by_number = {page.page_number: page for page in pages}
    for section in sections:
        if section.section_type not in section_types:
            continue
        heading_stripped = False
        for page_number, local_start, local_end in section_page_ranges(section, pages):
            page = pages_by_number[page_number]
            region = page.text[local_start:local_end]
            if not heading_stripped:
                # A section's heading_text is captured at exactly
                # section.start_offset on section.start_page_number (see
                # `detect_sections`), so it can only appear within this
                # first page's own local region -- equivalent to how
                # `section_content` strips it from the joined text, just
                # computed per-page here so table filtering below can use
                # each page's own `table_text`.
                heading_index = region.find(section.heading_text)
                if heading_index != -1:
                    region = region[heading_index + len(section.heading_text) :]
                heading_stripped = True
            for start, end in split_sentence_spans(region):
                sentence = region[start:end].strip()
                if sentence in claimed_sentences:
                    continue
                if is_table_derived(sentence, page.table_text):
                    continue
                if pattern.search(sentence):
                    claimed_sentences.add(sentence)
                    return sentence
    return None
