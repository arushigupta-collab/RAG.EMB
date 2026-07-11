"""Image extraction — same OCR path as scanned PDF (scope §3)."""

from __future__ import annotations

import mimetypes

from app.config import settings
from app.ingestion.extract.ocr import ocr_image_bytes
from app.ingestion.types import Block, ExtractResult


def extract_image(path: str) -> ExtractResult:
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        data = f.read()
    result = ocr_image_bytes(data, mime=mime)
    conf = float(result.get("confidence", 0.7))
    low = bool(result.get("handwritten")) or conf < 0.6
    text = (result.get("text") or "").strip()
    return ExtractResult(
        fmt="image",
        method=f"OpenRouter OCR ({settings.model_ocr})",
        confidence=conf,
        low_confidence=low,
        blocks=[Block(text=text, page=1, low_confidence=low)] if text else [],
        language=result.get("language"),
    )
