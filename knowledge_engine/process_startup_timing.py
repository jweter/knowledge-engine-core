"""Measure `ke`'s own per-invocation startup cost (issue #433 item 1).

`knowledge-engine-ai` currently invokes Core through `ke` subprocesses. This
module answers the resulting question raised in issue #433: how much of one
invocation is fixed process-startup overhead (interpreter import chain plus
Typer argument parsing) versus the separate, additional costs of opening the
local database and (when a caller asks) getting an embedding generator ready
to embed -- for `--generator local`, loading the `sentence-transformers`
model weights -- timed independently of each other and of whatever
retrieval/search/acquisition work the calling command itself does. None of
these numbers are folded into any command's own `duration_ms`; this module
only measures the fixed costs a command pays before its own work starts, so
a persistent-host redesign decision can be made from real elapsed time
rather than a guess.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from knowledge_engine import _PACKAGE_IMPORT_MONOTONIC
from knowledge_engine.database import Database
from knowledge_engine.vector_search.generator import EmbeddingGenerator

PROCESS_STARTUP_TIMING_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ProcessStartupTiming:
    """One invocation's own startup cost, in whole milliseconds."""

    schema_version: int
    import_to_command_ms: int
    database_open_ms: int
    embedding_generator_ready_ms: int | None = None
    embedding_generator_model_id: str | None = None

    def to_dict(self) -> dict[str, int | str | None]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def measure_process_startup_timing(
    build_database: Callable[[], Database],
    *,
    build_embedding_generator: Callable[[], EmbeddingGenerator] | None = None,
) -> ProcessStartupTiming:
    """Measure this invocation's own startup cost.

    `import_to_command_ms` is the elapsed time between
    `knowledge_engine`'s own package import (the earliest moment this
    process's code can observe, captured once at import time as
    `knowledge_engine._PACKAGE_IMPORT_MONOTONIC`) and this function
    running -- covering every submodule import the `ke` command surface
    needs plus Typer's argument parsing and dispatch, the fixed overhead a
    persistent-host redesign would eliminate. It does not include the
    Python interpreter's own startup before it began importing this
    package.

    `database_open_ms` separately times constructing `build_database()`'s
    `Database` and calling `initialize()` (schema/index readiness), kept
    apart from `import_to_command_ms` so a caller can see how much of a
    read/write command's overhead is process startup versus opening the
    local database, distinct from either and from the command's own
    retrieval/search/acquisition work.

    `embedding_generator_ready_ms`/`embedding_generator_model_id` are only
    populated when `build_embedding_generator` is given (measuring an
    embedding generator has real cost -- a local model's weights, or a
    required API key -- so it is opt-in, unlike the two costs above every
    invocation already pays). When given, `build_embedding_generator()` is
    called and then the returned generator's `dimension` property is read,
    which forces `SentenceTransformerEmbeddingGenerator` to load its model
    weights if they are not already loaded; `OpenAiEmbeddingGenerator.
    dimension` is a fixed local lookup with no comparable cost, so this
    reports near-zero for it by design, not by omission.
    """

    observed_at = time.monotonic()
    import_to_command_ms = int((observed_at - _PACKAGE_IMPORT_MONOTONIC) * 1000)

    database_started = time.monotonic()
    database = build_database()
    database.initialize()
    database_open_ms = int((time.monotonic() - database_started) * 1000)

    embedding_generator_ready_ms: int | None = None
    embedding_generator_model_id: str | None = None
    if build_embedding_generator is not None:
        generator_started = time.monotonic()
        embedding_generator = build_embedding_generator()
        _ = embedding_generator.dimension
        embedding_generator_ready_ms = int((time.monotonic() - generator_started) * 1000)
        embedding_generator_model_id = embedding_generator.model_id

    return ProcessStartupTiming(
        schema_version=PROCESS_STARTUP_TIMING_SCHEMA_VERSION,
        import_to_command_ms=import_to_command_ms,
        database_open_ms=database_open_ms,
        embedding_generator_ready_ms=embedding_generator_ready_ms,
        embedding_generator_model_id=embedding_generator_model_id,
    )
