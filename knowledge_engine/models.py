"""Database models for scientific source documents."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class SchemaVersion(Base):
    """Applied local database schema version."""

    __tablename__ = "schema_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    applied_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ManifestSnapshot(Base):
    """Exact corpus manifest inputs captured for an import run."""

    __tablename__ = "manifest_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    corpus_path: Mapped[str] = mapped_column(Text, nullable=False)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_json_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    source_csv_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    corpus_json_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_csv_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_json_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_csv_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    combined_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[str] = mapped_column(String(32), nullable=False)

    import_runs: Mapped[list[ImportRun]] = relationship(back_populates="manifest_snapshot")


class ImportRun(Base):
    """Durable record of one corpus validation/import-run attempt."""

    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_run_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    corpus_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    corpus_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    manifest_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    run_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="fresh")
    run_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    review_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="clear", index=True
    )
    manifest_validity: Mapped[str] = mapped_column(String(32), nullable=False)
    import_readiness: Mapped[str] = mapped_column(String(32), nullable=False)
    total_source_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_source_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structural_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(32), nullable=False)
    source_manifest_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    license_policy_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    corpus_path: Mapped[str] = mapped_column(Text, nullable=False)
    parent_import_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    manifest_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("manifest_snapshots.snapshot_id"), nullable=False, index=True
    )

    manifest_snapshot: Mapped[ManifestSnapshot] = relationship(back_populates="import_runs")
    items: Mapped[list[ImportItem]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ImportItem.csv_line_number"
    )
    issues: Mapped[list[ImportIssue]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ImportIssue.sequence"
    )

    __table_args__ = (
        CheckConstraint("total_source_rows >= 0", name="ck_import_runs_total_source_rows"),
        CheckConstraint("valid_source_rows >= 0", name="ck_import_runs_valid_source_rows"),
        CheckConstraint("warning_count >= 0", name="ck_import_runs_warning_count"),
        CheckConstraint(
            "structural_error_count >= 0", name="ck_import_runs_structural_error_count"
        ),
        CheckConstraint("import_blocker_count >= 0", name="ck_import_runs_import_blocker_count"),
    )


class ImportItem(Base):
    """Run-specific validation state for one source-manifest row."""

    __tablename__ = "import_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_item_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    import_run_id: Mapped[str] = mapped_column(
        ForeignKey("import_runs.import_run_id"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    csv_line_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_doi: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    inclusion_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    usage_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    local_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    item_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    duplicate_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    matched_paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id"), nullable=True, index=True
    )
    matched_import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    computed_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    blocks_manifest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocks_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warning_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    structural_error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    import_blocker_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_at: Mapped[str] = mapped_column(String(32), nullable=False)

    run: Mapped[ImportRun] = relationship(back_populates="items")
    issues: Mapped[list[ImportIssue]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ImportIssue.sequence"
    )

    __table_args__ = (
        CheckConstraint("warning_count >= 0", name="ck_import_items_warning_count"),
        CheckConstraint(
            "structural_error_count >= 0", name="ck_import_items_structural_error_count"
        ),
        CheckConstraint("import_blocker_count >= 0", name="ck_import_items_import_blocker_count"),
        UniqueConstraint("import_run_id", "csv_line_number", name="uq_item_run_line"),
    )


class ImportIssue(Base):
    """Persisted validation issue for an import run or item."""

    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    issue_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    import_run_id: Mapped[str] = mapped_column(
        ForeignKey("import_runs.import_run_id"), nullable=False, index=True
    )
    import_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_items.import_item_id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    field: Mapped[str | None] = mapped_column(String(256), nullable=True)
    csv_line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blocks_manifest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocks_import: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    run: Mapped[ImportRun] = relationship(back_populates="issues")
    item: Mapped[ImportItem | None] = relationship(back_populates="issues")

    __table_args__ = (UniqueConstraint("import_run_id", "sequence", name="uq_issue_run_sequence"),)


class PaperAuthor(Base):
    """Join table preserving author order for a paper."""

    __tablename__ = "paper_authors"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    paper: Mapped[Paper] = relationship(back_populates="author_links")
    author: Mapped[Author] = relationship(back_populates="paper_links")


class PaperKeyword(Base):
    """Join table for paper keywords."""

    __tablename__ = "paper_keywords"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), primary_key=True)

    paper: Mapped[Paper] = relationship(back_populates="keyword_links")
    keyword: Mapped[Keyword] = relationship(back_populates="paper_links")


class Journal(Base):
    """A publication venue."""

    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    issn: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    papers: Mapped[list[Paper]] = relationship(back_populates="journal")


class Author(Base):
    """A paper author."""

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    orcid: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper_links: Mapped[list[PaperAuthor]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )


class Keyword(Base):
    """A normalized keyword or topic label."""

    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper_links: Mapped[list[PaperKeyword]] = relationship(
        back_populates="keyword", cascade="all, delete-orphan"
    )


class Paper(Base):
    """Metadata for a scientific paper or source document."""

    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True, index=True)
    pmid: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    journal_id: Mapped[int | None] = mapped_column(ForeignKey("journals.id"), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_model: Mapped[str | None] = mapped_column(String(256), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    journal: Mapped[Journal | None] = relationship(back_populates="papers")
    text: Mapped[PaperText | None] = relationship(
        back_populates="paper", cascade="all, delete-orphan", uselist=False
    )
    author_links: Mapped[list[PaperAuthor]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperAuthor.position"
    )
    keyword_links: Mapped[list[PaperKeyword]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    pages: Mapped[list[PaperPage]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="PaperPage.page_number"
    )

    __table_args__ = (
        Index("ix_papers_embedding", "embedding_model", "embedding_id"),
        UniqueConstraint("content_hash", name="uq_papers_content_hash"),
    )


class PaperText(Base):
    """Extracted text for a paper."""

    __tablename__ = "paper_texts"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(128), nullable=False, default="pymupdf")
    extraction_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[Paper] = relationship(back_populates="text")


class PaperPage(Base):
    """Per-page normalized text, preserving page boundaries.

    Document-level ``PaperText.raw_text``/``body_text`` join every page's text
    together and discard which page any substring came from. Phase 2 evidence
    extraction needs an exact, reproducible (page_number, offset) citation for
    every claim, so this table retains each page's normalized text
    separately. A page's contribution to the joined ``raw_text`` is exactly
    its ``text`` value here; offsets computed against ``text`` are therefore
    directly usable as a source-span citation without a global-to-page offset
    mapping.

    Only populated going forward by ``PaperRepository.add_parsed_paper``. A
    paper imported before this table existed has zero rows here until a
    separate backfill utility re-parses its original local PDF -- which is
    only possible if that PDF file is still present, since page boundaries
    cannot be recovered from the already-joined ``raw_text``/``body_text``
    alone. Extraction logic must treat an empty ``pages`` list as "no page
    provenance available" rather than assuming every paper has one.

    ``table_text`` (schema v11) is a separate, best-effort signal: the
    concatenated, normalized text PyMuPDF's ``find_tables()`` detected as
    belonging to a table region on this page, or ``NULL`` when no table was
    detected or this page predates the v11 backfill. See
    ``knowledge_engine.parser.ParsedPage.table_text`` for why this is never
    subtracted from ``text`` itself, and
    ``knowledge_engine.extraction.table_filter`` for how it is used.
    """

    __tablename__ = "paper_pages"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    page_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    table_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    paper: Mapped[Paper] = relationship(back_populates="pages")


class ExtractionRun(Base):
    """Durable record of one `ke extraction-review-generate` invocation.

    Extraction rule versions (`extraction_context` in each draft item's own
    JSONL row) are already fully captured per item, so this table does not
    duplicate that as `extraction_items` rows -- it exists only so a paper's
    extraction history (when it ran, against which ruleset versions, how
    many draft items it produced, where they were written) can be found
    without re-reading every JSONL file `ke extraction-review-generate` has
    ever produced. `core` never re-runs extraction automatically on a
    ruleset change; a human decides when to re-invoke the command for a
    given paper.
    """

    __tablename__ = "extraction_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    extraction_run_id: Mapped[str] = mapped_column(
        String(36), nullable=False, unique=True, index=True
    )
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)
    section_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    section_detection_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_candidate_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_framing_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    draft_evidence_item_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    study_design_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    pico_extraction_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    paper: Mapped[Paper] = relationship()

    __table_args__ = (
        CheckConstraint("page_count >= 0", name="ck_extraction_runs_page_count"),
        CheckConstraint("section_count >= 0", name="ck_extraction_runs_section_count"),
        CheckConstraint("candidate_count >= 0", name="ck_extraction_runs_candidate_count"),
        CheckConstraint("draft_item_count >= 0", name="ck_extraction_runs_draft_item_count"),
    )


class GraphConcept(Base):
    """Phase 4 graph node: one resolved reference-layer term or PICO field value.

    See `docs/phase4_design.md`'s Architecture section. `definition`/
    `source_url`/`license` hold the actual M41-M45 lookup content (Wikipedia's
    `extract`, MeSH's `scope_note`, etc.) -- those lookup results are not
    persisted anywhere else, so a row here is their only durable home once a
    concept is linked into the graph. `source_reference_id` (the lookup's own
    `mesh_id`/`rxcui`/`cid`) is null for a bare PICO-derived concept with no
    resolved reference-layer match; `UniqueConstraint` below only dedupes
    real, identified lookups -- SQLite treats each `NULL` as distinct, so
    multiple bare PICO concepts are never falsely deduped by this constraint
    (see the design doc's "Concept-node duplication across sources" risk:
    no PICO-label deduplication is attempted in this first slice).
    """

    __tablename__ = "graph_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    license: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "source IN ('wikipedia','rxnorm','mesh','pubchem','pico')",
            name="ck_graph_concepts_source",
        ),
        UniqueConstraint(
            "source", "source_reference_id", name="uq_graph_concepts_source_reference"
        ),
    )


class GraphClaim(Base):
    """Phase 4 graph node: one *validated* `EvidenceRecord`, not a raw claim candidate.

    `evidence_record_id` is a plain, application-validated string reference,
    not a SQL foreign key -- `EvidenceRecord`s are JSONL objects appended by
    `_promote_evidence_records`, never rows in any SQLAlchemy table, so
    there is no table for a `ForeignKey()` to target. This node inherits its
    parent record's `research_question`/`evidence_direction`/`confidence_note`
    by reference; none of those judgment fields are duplicated here.

    `corpus_id` is nullable and unset by default -- the graph is
    deliberately corpus-agnostic (`ke graph-build` writes every corpus's
    claims into these same shared tables), so a claim only carries a
    `corpus_id` when a caller explicitly opts in via `ke graph-build
    --corpus <id>`. `NULL` means "unscoped," not "unknown"; nothing
    guesses a corpus for a claim that was never told one.
    """

    __tablename__ = "graph_claims"

    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    corpus_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class GraphClaimConcept(Base):
    """Phase 4 graph edge: which PICO field linked a claim to a concept.

    Real SQL foreign keys on both sides -- both endpoints are genuine
    `graph_*` rows, unlike `GraphClaim.evidence_record_id` above.
    """

    __tablename__ = "graph_claim_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("graph_claims.id"), nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("graph_concepts.id"), nullable=False, index=True
    )
    edge_role: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "edge_role IN ('population','intervention','comparator','outcome')",
            name="ck_graph_claim_concepts_edge_role",
        ),
        UniqueConstraint(
            "claim_id", "concept_id", "edge_role", name="uq_graph_claim_concepts_edge"
        ),
    )


class GraphClaimRelationship(Base):
    """Phase 4 graph edge: a graph-queryable projection of an M24 `RelationshipRecord`.

    `relationship_id` is a plain, application-validated string reference,
    the same non-enforced posture as `GraphClaim.evidence_record_id`, for
    the same reason: `RelationshipRecord`s are JSONL too, with no table to
    reference. This table does not replace `RelationshipRecord`s or `ke
    relationship-validate` -- it is a projection of the same validated data,
    not a second source of truth.

    `relationship_type` includes `supersedes` (M50) alongside the original
    four types: a human-authored claim that a newer claim revises an older
    one, the Stability Score revision-event mechanism
    `docs/stability_and_tracking_design.md` designed -- deliberately reusing
    this table rather than adding a new one. See that doc for why.
    """

    __tablename__ = "graph_claim_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    relationship_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    source_claim_id: Mapped[int] = mapped_column(
        ForeignKey("graph_claims.id"), nullable=False, index=True
    )
    target_claim_id: Mapped[int] = mapped_column(
        ForeignKey("graph_claims.id"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relationship_type IN "
            "('supports','contradicts','qualifies','contextualizes','supersedes')",
            name="ck_graph_claim_relationships_type",
        ),
    )


class GraphCitation(Base):
    """Phase 4 graph edge: one paper's reference list cites another *corpus* paper.

    Real foreign keys on both sides (unlike `GraphClaim.evidence_record_id`)
    since citing/cited are always genuine `papers` rows -- an edge is only
    created when a reference-list DOI actually matches a paper already in
    the corpus, never for an external DOI with no corresponding row. See
    `knowledge_engine/citation_extraction.py`'s module docstring for the
    real-corpus measurement (M47) that scoped this to DOI-substring
    matching rather than a structured, multi-format entry parser: only 5
    intra-corpus edges exist across the real 960-paper corpus, which does
    not justify the larger build.
    """

    __tablename__ = "graph_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    citing_paper_id: Mapped[int] = mapped_column(
        ForeignKey("papers.id"), nullable=False, index=True
    )
    cited_paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    raw_citation_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "citing_paper_id != cited_paper_id", name="ck_graph_citations_no_self_citation"
        ),
        UniqueConstraint("citing_paper_id", "cited_paper_id", name="uq_graph_citations_edge"),
    )
