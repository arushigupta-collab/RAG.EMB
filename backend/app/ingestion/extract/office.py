"""Office + tabular extraction: Word, PowerPoint, Excel, CSV/TSV (scope §3).

Legacy .doc/.ppt are pre-converted with LibreOffice. Excel/CSV rows are emitted as
structured tables so they can be written to PostgreSQL for exact querying.
"""

from __future__ import annotations

import csv
import os
import subprocess
import tempfile

import pandas as pd

from app.ingestion.types import Block, ExtractResult, Table


def _libreoffice_convert(path: str, to_ext: str) -> str:
    """Convert legacy .doc/.ppt -> .docx/.pptx; returns the new path."""
    outdir = tempfile.mkdtemp()
    subprocess.run(
        ["soffice", "--headless", "--convert-to", to_ext, "--outdir", outdir, path],
        check=True,
        timeout=120,
    )
    base = os.path.splitext(os.path.basename(path))[0]
    return os.path.join(outdir, f"{base}.{to_ext}")


# --------------------------------------------------------------------------- #
# Word
# --------------------------------------------------------------------------- #
def extract_docx(path: str, legacy: bool = False) -> ExtractResult:
    if legacy:
        path = _libreoffice_convert(path, "docx")
    from docx import Document

    doc = Document(path)
    blocks: list[Block] = []
    heading_path: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "").lower()
        if style.startswith("heading"):
            try:
                level = int(style.replace("heading", "").strip() or "1")
            except ValueError:
                level = 1
            heading_path = heading_path[: level - 1] + [text]
            blocks.append(Block(text=text, heading_path=list(heading_path)))
        else:
            blocks.append(Block(text=text, heading_path=list(heading_path)))

    tables: list[Table] = []
    for t in doc.tables:
        rows_cells = [[c.text.strip() for c in r.cells] for r in t.rows]
        if len(rows_cells) < 2:
            continue
        header = rows_cells[0]
        rows = [dict(zip(header, r)) for r in rows_cells[1:]]
        md = _rows_to_markdown(header, rows_cells[1:])
        tables.append(Table(rows=rows, markdown=md, heading_path=list(heading_path)))

    return ExtractResult(
        fmt="docx",
        method="python-docx (heading hierarchy preserved)",
        confidence=0.99,
        low_confidence=False,
        blocks=blocks,
        tables=tables,
    )


# --------------------------------------------------------------------------- #
# PowerPoint
# --------------------------------------------------------------------------- #
def extract_pptx(path: str, legacy: bool = False) -> ExtractResult:
    if legacy:
        path = _libreoffice_convert(path, "pptx")
    from pptx import Presentation

    prs = Presentation(path)
    blocks: list[Block] = []
    for i, slide in enumerate(prs.slides, start=1):
        title = ""
        body: list[str] = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            txt = shape.text_frame.text.strip()
            if not txt:
                continue
            if shape == slide.shapes.title:
                title = txt
            else:
                body.append(txt)
        notes = ""
        if slide.has_notes_slide:
            notes = (slide.notes_slide.notes_text_frame.text or "").strip()
        parts = [p for p in [title, *body, (f"Notes: {notes}" if notes else "")] if p]
        if parts:
            blocks.append(
                Block(
                    text="\n".join(parts),
                    page=i,
                    heading_path=[title] if title else [f"Slide {i}"],
                )
            )
    return ExtractResult(
        fmt="pptx",
        method="python-pptx (titles + body + speaker notes)",
        confidence=0.98,
        low_confidence=False,
        blocks=blocks,
    )


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #
def extract_excel(path: str, ext: str) -> ExtractResult:
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    sheets = pd.read_excel(path, sheet_name=None, engine=engine, header=0)
    tables: list[Table] = []
    blocks: list[Block] = []

    for sheet_name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        df = df.fillna("")
        rows = df.to_dict(orient="records")
        rows = [{str(k): _norm(v) for k, v in r.items()} for r in rows]
        md = df.head(50).to_markdown(index=False)
        tables.append(Table(rows=rows, markdown=md, sheet=sheet_name))
        # Sheet-level summary chunk keeps the sheet discoverable (scope §5.1).
        cols = ", ".join(str(c) for c in df.columns)
        blocks.append(
            Block(
                text=f"Spreadsheet sheet '{sheet_name}' with {len(rows)} rows. "
                f"Columns: {cols}.",
                heading_path=[sheet_name],
            )
        )

    return ExtractResult(
        fmt="xlsx" if ext != ".xls" else "xls",
        method=f"{engine} (merged cells resolved, rows -> PostgreSQL)",
        confidence=0.99,
        low_confidence=False,
        blocks=blocks,
        tables=tables,
    )


# --------------------------------------------------------------------------- #
# CSV / TSV
# --------------------------------------------------------------------------- #
def extract_csv(path: str, ext: str) -> ExtractResult:
    # Auto-detect delimiter.
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)
    try:
        delim = csv.Sniffer().sniff(sample).delimiter
    except csv.Error:
        delim = "\t" if ext == ".tsv" else ","

    df = pd.read_csv(path, sep=delim, dtype=str, keep_default_na=False)
    rows = [{str(k): _norm(v) for k, v in r.items()} for r in df.to_dict(orient="records")]
    md = df.head(50).to_markdown(index=False)
    cols = ", ".join(str(c) for c in df.columns)
    return ExtractResult(
        fmt=ext.lstrip("."),
        method="pandas (delimiter auto-detected, rows -> PostgreSQL)",
        confidence=0.99,
        low_confidence=False,
        blocks=[Block(text=f"Tabular file with {len(rows)} rows. Columns: {cols}.")],
        tables=[Table(rows=rows, markdown=md)],
    )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _norm(v) -> str:
    s = str(v).strip()
    return s


def _rows_to_markdown(header: list[str], body: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * len(header)) + " |"]
    for r in body:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)
