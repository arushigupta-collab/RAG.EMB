"""Text-layer PDF extraction (scope §3).

PyMuPDF for text + heading structure; pdfplumber and camelot for tables. Tables
are extracted as structured rows and kept whole (never flattened / split mid-row).
"""

from __future__ import annotations

import fitz  # PyMuPDF

from app.ingestion.types import Block, ExtractResult, Table


def _looks_like_heading(span: dict, body_size: float) -> bool:
    # Larger or bold text relative to body is treated as a heading boundary.
    size = span.get("size", body_size)
    bold = bool(span.get("flags", 0) & 2 ** 4)
    return size >= body_size * 1.15 or bold


def extract_pdf_text(path: str) -> ExtractResult:
    doc = fitz.open(path)
    blocks: list[Block] = []
    heading_path: list[str] = []

    # Estimate a body font size from the median span size.
    sizes: list[float] = []
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip():
                        sizes.append(span["size"])
    body_size = sorted(sizes)[len(sizes) // 2] if sizes else 11.0

    for page_no, page in enumerate(doc, start=1):
        for b in page.get_text("dict")["blocks"]:
            line_texts: list[str] = []
            is_heading = False
            for line in b.get("lines", []):
                spans = line.get("spans", [])
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                line_texts.append(text)
                if spans and _looks_like_heading(spans[0], body_size):
                    is_heading = True
            block_text = " ".join(line_texts).strip()
            if not block_text:
                continue
            if is_heading and len(block_text) < 120:
                # Update the running section breadcrumb.
                heading_path = [*heading_path[:0], block_text]
                blocks.append(
                    Block(text=block_text, page=page_no, heading_path=list(heading_path))
                )
            else:
                blocks.append(
                    Block(text=block_text, page=page_no, heading_path=list(heading_path))
                )
    doc.close()

    tables = _extract_tables(path)

    return ExtractResult(
        fmt="pdf-text",
        method="PyMuPDF (text+layout+tables via find_tables)",
        confidence=0.98,
        low_confidence=False,
        blocks=blocks,
        tables=tables,
    )


def _extract_tables(path: str) -> list[Table]:
    """Fast, all-pages table extraction via PyMuPDF's built-in find_tables().

    This is C-level and needs no ghostscript, so it scales to large reports where
    camelot's per-page scan is impractical. Tables are kept whole (scope §5.1).
    """
    tables: list[Table] = []
    doc = fitz.open(path)
    for page_no, page in enumerate(doc, start=1):
        try:
            found = page.find_tables()
        except Exception:
            continue
        for t in getattr(found, "tables", []):
            try:
                matrix = t.extract()
            except Exception:
                continue
            matrix = [[(c or "").strip() for c in row] for row in matrix]
            rows = _matrix_to_rows(matrix)
            if rows:
                tables.append(
                    Table(rows=rows, markdown=_matrix_to_md(matrix), page=page_no)
                )
    doc.close()
    return tables


def _matrix_to_rows(matrix: list[list[str]]) -> list[dict]:
    # Require >= 2 columns and >= 2 rows so a stray text block is not a "table".
    if len(matrix) < 2 or len(matrix[0]) < 2:
        return []
    header = [c or f"col_{i}" for i, c in enumerate(matrix[0])]
    rows = []
    for r in matrix[1:]:
        rows.append({header[i]: (r[i] if i < len(r) else "") for i in range(len(header))})
    return rows


def _matrix_to_md(matrix: list[list[str]]) -> str:
    if not matrix:
        return ""
    header = matrix[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for r in matrix[1:]:
        cells = [r[i] if i < len(r) else "" for i in range(len(header))]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
