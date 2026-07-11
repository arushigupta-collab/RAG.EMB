"""API-contract models (scope §10).

`/ingest` -> job id + per-stage updates (classify, extract, chunk, index).
`/query`  -> ordered `step` events, then `token` deltas, then `evidence[]`,
             then a final `grounding` verdict. Citation markers stay as [n].
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Shared enums
# --------------------------------------------------------------------------- #
class DocCategory(str, Enum):
    structured_policy = "Structured Policy"
    financial_data = "Financial Data"
    records_correspondence = "Records and Correspondence"
    implementation_reports = "Implementation Reports"


class QueryType(str, Enum):
    semantic = "Semantic"
    numerical_lookup = "Numerical Lookup"
    aggregate = "Aggregate"
    comparison = "Comparison"
    mixed = "Mixed"


class DocStatus(str, Enum):
    queued = "queued"
    classifying = "classifying"
    extracting = "extracting"
    chunking = "chunking"
    indexing = "indexing"
    done = "done"
    failed = "failed"


# --------------------------------------------------------------------------- #
# Ingestion
# --------------------------------------------------------------------------- #
class IngestAccepted(BaseModel):
    job_id: str
    documents: list["IngestDocRef"]


class IngestDocRef(BaseModel):
    doc_id: str
    filename: str


class StageUpdate(BaseModel):
    """One per-stage update emitted during ingestion."""

    doc_id: str
    filename: str
    stage: Literal["classify", "extract", "chunk", "index"]
    status: DocStatus
    detail: str = ""  # human-readable detail string (scope §10)


class IngestStageSnapshot(BaseModel):
    """Detail shown per stage in the corpus-view expander (scope §9)."""

    stage: Literal["classify", "extract", "chunk", "index"]
    detail: str
    status: DocStatus


class DocumentRecord(BaseModel):
    doc_id: str
    filename: str
    fmt: str  # detected format, e.g. "pdf-text", "pdf-scanned", "docx"
    category: Optional[DocCategory] = None
    status: DocStatus
    classify_method: Optional[str] = None
    classify_confidence: Optional[float] = None
    extract_method: Optional[str] = None
    extract_confidence: Optional[float] = None
    low_confidence: bool = False  # OCR / handwriting / sub-150-DPI flag
    chunk_count: int = 0
    indexed_dense: int = 0
    indexed_sparse: int = 0
    rows_to_sql: int = 0
    error: Optional[str] = None
    stages: list[IngestStageSnapshot] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Query — SSE event payloads
# --------------------------------------------------------------------------- #
class StepEvent(BaseModel):
    """`step` event: one per pipeline stage (scope §10)."""

    label: str          # e.g. "Classify"
    sublabel: str = ""  # e.g. "Semantic · language: hi"
    elapsed_ms: int


class TokenEvent(BaseModel):
    """`token` event: a streamed answer delta."""

    delta: str


class EvidenceItem(BaseModel):
    """One entry in the final `evidence` array; maps to a [n] marker."""

    n: int
    document: str
    section: str = ""
    page: Optional[int] = None
    score: float = 0.0
    snippet: str = ""


class GroundingEvent(BaseModel):
    verdict: Literal["verified", "no-source"]
    detail: str = ""


class QueryRequest(BaseModel):
    query: str
    # Optional client hint; server still classifies authoritatively.
    language: Optional[str] = None


IngestAccepted.model_rebuild()
