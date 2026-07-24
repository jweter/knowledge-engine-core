"""Parse and validate externally-generated paper embeddings (Phase 3's option 3).

Until an `EmbeddingGenerator` is implemented (see `generator.py`), the only
way a paper gets an embedding is a vector some external tool -- a notebook,
a one-off script, any embedding provider -- already computed. This module
only parses and structurally validates that external input; it never
generates a vector itself and never invents or guesses `embedding_model`,
matching the "never invent unsupported metadata" principle already
enforced throughout the M14 manifest-curation pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXTERNAL_VECTOR_INGESTION_RULES_VERSION = "m30-external-vector-ingestion-v1"

_REQUIRED_VECTOR_FIELDS = frozenset({"paper_id", "vector", "embedding_model"})


@dataclass(frozen=True)
class ExternalVectorRecord:
    """One paper's externally-supplied embedding vector."""

    paper_id: int
    vector: tuple[float, ...]
    embedding_model: str


@dataclass(frozen=True)
class VectorIngestionResult:
    """Outcome of parsing one externally-supplied vectors file."""

    records: tuple[ExternalVectorRecord, ...]
    errors: tuple[str, ...]
    dimension: int | None
    embedding_model: str | None


def load_external_vectors(path: Path) -> VectorIngestionResult:
    """Parse and validate a JSONL file of externally-generated paper embeddings.

    Each line must be a JSON object: `{"paper_id": int, "vector": [float,
    ...], "embedding_model": str}`. Every vector in the file must share the
    same dimension AND the same `embedding_model` -- a mismatch of either is
    reported, never silently truncated, padded, or mixed. Vectors from
    different embedding models are not comparable even when their
    dimensions happen to coincide (L2 distance between them is meaningless);
    allowing them into the same index would silently rank unrelated vector
    spaces together. Does not check that `paper_id` actually exists in the
    database; the caller (the `embedding-index-build` command) does that
    referential check, mirroring how `relationship-validate`'s structural
    parsing and referential evidence check are separate steps.
    """

    if not path.exists():
        return VectorIngestionResult(
            records=(),
            errors=(f"Vectors file does not exist: {path}",),
            dimension=None,
            embedding_model=None,
        )

    lines = path.read_text(encoding="utf-8").splitlines()
    if not any(line.strip() for line in lines):
        return VectorIngestionResult(
            records=(),
            errors=("Vectors file contains no records.",),
            dimension=None,
            embedding_model=None,
        )

    errors: list[str] = []
    records: list[ExternalVectorRecord] = []
    seen_paper_ids: set[int] = set()
    dimension: int | None = None
    embedding_model: str | None = None

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue

        parsed = _parse_line(stripped, line_number, errors)
        if parsed is None:
            continue

        paper_id, vector, record_embedding_model = parsed
        if paper_id in seen_paper_ids:
            errors.append(f"Line {line_number}: duplicate paper_id: {paper_id}.")
            continue

        if dimension is None:
            dimension = len(vector)
        elif len(vector) != dimension:
            errors.append(
                f"Line {line_number}: vector has dimension {len(vector)}, expected "
                f"{dimension} (from an earlier record in this file)."
            )
            continue

        if embedding_model is None:
            embedding_model = record_embedding_model
        elif record_embedding_model != embedding_model:
            errors.append(
                f"Line {line_number}: embedding_model is '{record_embedding_model}', "
                f"expected '{embedding_model}' (from an earlier record in this file). "
                "A single vectors file must come from exactly one embedding model."
            )
            continue

        seen_paper_ids.add(paper_id)
        records.append(
            ExternalVectorRecord(
                paper_id=paper_id, vector=tuple(vector), embedding_model=record_embedding_model
            )
        )

    return VectorIngestionResult(
        records=tuple(records),
        errors=tuple(errors),
        dimension=dimension,
        embedding_model=embedding_model,
    )


def _parse_line(
    stripped: str, line_number: int, errors: list[str]
) -> tuple[int, list[float], str] | None:
    """Parse and structurally validate one JSONL line. Appends to `errors` on failure."""

    try:
        record = json.loads(stripped)
    except json.JSONDecodeError:
        errors.append(f"Line {line_number}: invalid JSON.")
        return None
    if not isinstance(record, dict):
        errors.append(f"Line {line_number}: record must be a JSON object.")
        return None

    missing = sorted(_REQUIRED_VECTOR_FIELDS - record.keys())
    if missing:
        errors.append(f"Line {line_number}: missing required field(s): {', '.join(missing)}.")
        return None

    paper_id = _validate_paper_id(record["paper_id"], line_number, errors)
    embedding_model = _validate_embedding_model(record["embedding_model"], line_number, errors)
    vector = _validate_vector(record["vector"], line_number, errors)
    if paper_id is None or embedding_model is None or vector is None:
        return None
    return paper_id, vector, embedding_model


def _validate_paper_id(value: Any, line_number: int, errors: list[str]) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"Line {line_number}: paper_id must be an integer.")
        return None
    return value


def _validate_embedding_model(value: Any, line_number: int, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"Line {line_number}: embedding_model must be a non-empty string.")
        return None
    return value


def _validate_vector(value: Any, line_number: int, errors: list[str]) -> list[float] | None:
    if not isinstance(value, list) or not value:
        errors.append(f"Line {line_number}: vector must be a non-empty array of numbers.")
        return None
    if not all(
        isinstance(component, int | float) and not isinstance(component, bool)
        for component in value
    ):
        errors.append(f"Line {line_number}: vector must contain only numbers.")
        return None
    return [float(component) for component in value]
