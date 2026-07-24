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

from knowledge_engine.extraction.sections import SectionSpan, section_content
from knowledge_engine.parser import ParsedPage
from knowledge_engine.sentence_split import split_sentence_spans

PICO_EXTRACTION_RULES_VERSION = "m28-pico-v1"

# A study-design phrase or heading is usually reused verbatim; PICO values are
# not, so each field is scoped only to the section types most likely to state
# it plainly rather than reference someone else's prior work (mirroring
# `classify_study_type`'s Abstract/Methods-only scoping rationale). Outcome
# and comparator cues also appear in Results, since a paper's own primary
# outcome or comparison arm is frequently restated there.
_POPULATION_SECTION_TYPES = frozenset({"abstract", "methods"})
_INTERVENTION_SECTION_TYPES = frozenset({"abstract", "methods"})
_COMPARATOR_SECTION_TYPES = frozenset({"abstract", "methods", "results"})
_OUTCOME_SECTION_TYPES = frozenset({"abstract", "methods", "results"})

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
    into a low-confidence value.
    """

    return PicoFields(
        population=_first_matching_sentence(
            pages, sections, _POPULATION_SECTION_TYPES, _POPULATION_PATTERN
        ),
        intervention=_first_matching_sentence(
            pages, sections, _INTERVENTION_SECTION_TYPES, _INTERVENTION_PATTERN
        ),
        comparator=_first_matching_sentence(
            pages, sections, _COMPARATOR_SECTION_TYPES, _COMPARATOR_PATTERN
        ),
        outcome=_first_matching_sentence(pages, sections, _OUTCOME_SECTION_TYPES, _OUTCOME_PATTERN),
        rules_version=PICO_EXTRACTION_RULES_VERSION,
    )


def _first_matching_sentence(
    pages: Sequence[ParsedPage],
    sections: Sequence[SectionSpan],
    section_types: frozenset[str],
    pattern: re.Pattern[str],
) -> str | None:
    """Return the first cue-matching sentence across scoped sections, in document order."""

    for section in sections:
        if section.section_type not in section_types:
            continue
        text = section_content(pages, section)
        for start, end in split_sentence_spans(text):
            sentence = text[start:end]
            if pattern.search(sentence):
                return sentence.strip()
    return None
