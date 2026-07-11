"""Format detection + dispatch to the right parser (scope §3).

Text-layer documents go to deterministic parsers (exact, fast, never invent text);
scanned/image content goes to the OCR path. PDFs are probed for an extractable
text layer to decide between the two.
"""

from __future__ import annotations

import os

import fitz  # PyMuPDF

from app.ingestion.types import ExtractResult

# Minimum extractable characters per page to treat a PDF as text-layer, not scanned.
_PDF_TEXT_CHARS_PER_PAGE = 40


def detect_and_extract(path: str, filename: str) -> ExtractResult:
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return _extract_pdf(path)
    if ext in (".docx", ".doc"):
        from app.ingestion.extract.office import extract_docx

        return extract_docx(path, legacy=ext == ".doc")
    if ext in (".pptx", ".ppt"):
        from app.ingestion.extract.office import extract_pptx

        return extract_pptx(path, legacy=ext == ".ppt")
    if ext in (".xlsx", ".xls", ".xlsm"):
        from app.ingestion.extract.office import extract_excel

        return extract_excel(path, ext)
    if ext in (".csv", ".tsv"):
        from app.ingestion.extract.office import extract_csv

        return extract_csv(path, ext)
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp"):
        from app.ingestion.extract.image import extract_image

        return extract_image(path)
    if ext in (".html", ".htm") or filename.startswith(("http://", "https://")):
        from app.ingestion.extract.web import extract_web

        return extract_web(path if os.path.exists(path) else filename)

    raise ValueError(f"Unsupported file type: {ext or filename}")


def _extract_pdf(path: str) -> ExtractResult:
    doc = fitz.open(path)
    total_chars = sum(len(page.get_text("text")) for page in doc)
    text_layer = total_chars >= _PDF_TEXT_CHARS_PER_PAGE * max(len(doc), 1)
    doc.close()

    if text_layer:
        from app.ingestion.extract.pdf_text import extract_pdf_text

        return extract_pdf_text(path)

    from app.ingestion.extract.pdf_scanned import extract_pdf_scanned

    return extract_pdf_scanned(path)
