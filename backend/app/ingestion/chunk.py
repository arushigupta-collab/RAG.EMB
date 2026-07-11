"""Structure-aware, category-specific chunking (scope §5.1).

Chunk on the boundaries the document already has (never fixed-size):
  - Structured Policy / Implementation Reports -> heading hierarchy (one per section)
  - Records and Correspondence                 -> agenda item / block
  - Financial Data                             -> rows go to SQL; a sheet-summary chunk
  - Tables (any doc)                           -> kept whole, also written to SQL

Each chunk carries rich metadata and has its section breadcrumb + document title
prepended to the embedded text (small-to-big: a parent-section pointer is stored).
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.config import settings
from app.ingestion.types import Block, ExtractResult
from app.schemas import DocCategory

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def _ntokens(text: str) -> int:
        return len(_ENC.encode(text))
except Exception:  # pragma: no cover - fallback if tiktoken unavailable
    def _ntokens(text: str) -> int:
        return max(1, len(text) // 4)


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    filename: str
    category: str
    text: str                    # text as stored / shown
    embed_text: str              # breadcrumb + title prepended, used for embedding
    section: str                 # breadcrumb string
    page: Optional[int]
    language: Optional[str]
    extraction_confidence: float
    low_confidence: bool
    is_table: bool
    ref_number: Optional[str]
    parent_section: str          # small-to-big pointer (fuller context)
    meta: dict = field(default_factory=dict)

    def payload(self) -> dict:
        d = asdict(self)
        return d


_REF_RE = None


def _ref_number(text: str) -> Optional[str]:
    import re

    global _REF_RE
    if _REF_RE is None:
        # Circular / reference / F.No. style identifiers common in MNRE material.
        _REF_RE = re.compile(
            r"(?:No\.|F\.No\.|Circular|Ref)\s*[:\-]?\s*[A-Z0-9()/\.\-]{4,}",
            re.IGNORECASE,
        )
    m = _REF_RE.search(text or "")
    return m.group(0) if m else None


def _breadcrumb(heading_path: list[str]) -> str:
    return " > ".join([h for h in heading_path if h])


def chunk_document(
    doc_id: str,
    filename: str,
    title: str,
    category: DocCategory,
    extracted: ExtractResult,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    # 1) Tables are kept whole, one chunk each (scope §5.1).
    for table in extracted.tables:
        section = _breadcrumb(table.heading_path) or (table.sheet or "Table")
        text = table.markdown
        chunks.append(
            _make_chunk(
                doc_id, filename, title, category, text, section, table.page,
                extracted, is_table=True, parent_section=section,
            )
        )

    # 2) Narrative blocks grouped into sections by breadcrumb.
    sections = _group_by_section(extracted.blocks)
    for section, blocks in sections:
        body = "\n".join(b.text for b in blocks).strip()
        if not body:
            continue
        page = next((b.page for b in blocks if b.page is not None), None)
        low = any(b.low_confidence for b in blocks)
        # Low-confidence content is chunked separately and flagged (scope §5.1).
        if low:
            hi = "\n".join(b.text for b in blocks if not b.low_confidence).strip()
            lo = "\n".join(b.text for b in blocks if b.low_confidence).strip()
            for part, is_low in [(hi, False), (lo, True)]:
                if part:
                    chunks.extend(
                        _emit_section(
                            doc_id, filename, title, category, section, part, page,
                            extracted, force_low=is_low,
                        )
                    )
        else:
            chunks.extend(
                _emit_section(
                    doc_id, filename, title, category, section, body, page, extracted,
                )
            )

    return chunks


def _emit_section(
    doc_id, filename, title, category, section, body, page, extracted, force_low=False
) -> list[Chunk]:
    """Bound section size to the target token window with in-section overlap."""
    out: list[Chunk] = []
    if _ntokens(body) <= settings.chunk_max_tokens:
        out.append(
            _make_chunk(
                doc_id, filename, title, category, body, section, page, extracted,
                parent_section=section, force_low=force_low,
            )
        )
        return out

    # Split recursively at paragraph boundaries with a 1-2 sentence overlap.
    paras = [p for p in body.split("\n") if p.strip()]
    cur: list[str] = []
    for para in paras:
        cur.append(para)
        if _ntokens("\n".join(cur)) >= settings.chunk_target_tokens:
            out.append(
                _make_chunk(
                    doc_id, filename, title, category, "\n".join(cur), section, page,
                    extracted, parent_section=section, force_low=force_low,
                )
            )
            overlap = cur[-1].split(". ")[-2:]  # trailing sentence(s) as seam overlap
            cur = [". ".join(overlap)] if overlap else []
    if cur and "".join(cur).strip():
        out.append(
            _make_chunk(
                doc_id, filename, title, category, "\n".join(cur), section, page,
                extracted, parent_section=section, force_low=force_low,
            )
        )
    return out


def _group_by_section(blocks: list[Block]) -> list[tuple[str, list[Block]]]:
    """Merge adjacent tiny sections up to the minimum size to avoid orphans."""
    grouped: list[tuple[str, list[Block]]] = []
    for b in blocks:
        section = _breadcrumb(b.heading_path)
        if grouped and grouped[-1][0] == section:
            grouped[-1][1].append(b)
        else:
            grouped.append((section, [b]))

    merged: list[tuple[str, list[Block]]] = []
    for section, bs in grouped:
        text = "\n".join(x.text for x in bs)
        if merged and _ntokens(text) < settings.chunk_min_tokens:
            prev_section, prev_bs = merged[-1]
            prev_bs.extend(bs)
        else:
            merged.append((section, list(bs)))
    return merged


def _make_chunk(
    doc_id, filename, title, category, text, section, page, extracted,
    is_table=False, parent_section="", force_low=False,
) -> Chunk:
    breadcrumb = section or title
    # Prepend document title + section breadcrumb so an isolated chunk keeps context.
    embed_text = f"{title}\n{breadcrumb}\n\n{text}" if breadcrumb else f"{title}\n\n{text}"
    low = force_low or (extracted.low_confidence and is_table is False and False)
    return Chunk(
        chunk_id=str(uuid.uuid4()),  # Qdrant point ids must be UUID or unsigned int
        doc_id=doc_id,
        filename=filename,
        category=category.value if isinstance(category, DocCategory) else str(category),
        text=text,
        embed_text=embed_text,
        section=breadcrumb,
        page=page,
        language=extracted.language,
        extraction_confidence=extracted.confidence,
        low_confidence=low,
        is_table=is_table,
        ref_number=_ref_number(text),
        parent_section=parent_section or breadcrumb,
    )
