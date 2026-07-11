"""Internal data model passed between extract -> chunk -> index (scope §3, §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Block:
    """A unit of extracted narrative text with its structural context."""

    text: str
    page: Optional[int] = None
    heading_path: list[str] = field(default_factory=list)  # section breadcrumb
    low_confidence: bool = False  # OCR/handwriting/sub-150-DPI (scope §3)


@dataclass
class Table:
    """A structured table kept whole (scope §5.1). Rows also feed PostgreSQL."""

    rows: list[dict]           # normalised row dicts
    markdown: str              # structural serialisation for the vector chunk
    page: Optional[int] = None
    sheet: Optional[str] = None
    heading_path: list[str] = field(default_factory=list)


@dataclass
class ExtractResult:
    fmt: str                   # e.g. "pdf-text", "pdf-scanned", "docx", "xlsx"
    method: str                # parser/engine description for the corpus view
    confidence: float          # 0..1 extraction confidence
    low_confidence: bool       # any low-confidence content present
    blocks: list[Block] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    language: Optional[str] = None
