"""Scanned-PDF extraction (scope §3).

pdf2image rasterises each page at 300 DPI (with deskew/denoise), then the OCR pass
transcribes it. Low-confidence pages (handwriting, sub-150-DPI) are flagged so they
are stored separately and never presented as verified fact.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from pdf2image import convert_from_path

from app.config import settings
from app.ingestion.extract.ocr import ocr_image_bytes
from app.ingestion.types import Block, ExtractResult


def _deskew(pil_img) -> bytes:
    """Fast, light preprocess before OCR: grayscale + cheap deskew.

    The previous heavy fastNlMeansDenoising pass dominated CPU on 300-DPI pages and
    gave little benefit for a frontier multimodal OCR model, so it is dropped. The
    skew angle is estimated on a downscaled copy (cheap) and the full-res image is
    rotated only when the skew is meaningful.
    """
    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    h, w = img.shape

    # Estimate skew on a downscaled copy so minAreaRect is cheap.
    scale = 1000.0 / max(h, w)
    small = (
        cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else img
    )
    coords = np.column_stack(np.where(small < 200))
    if coords.size:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        if abs(angle) > 0.5:
            m = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            img = cv2.warpAffine(
                img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


def _ocr_page(args) -> tuple[int, dict]:
    page_no, pil_img = args
    return page_no, ocr_image_bytes(_deskew(pil_img))


def extract_pdf_scanned(path: str) -> ExtractResult:
    pages = convert_from_path(path, dpi=settings.ocr_dpi)

    # Pages are independent, so OCR them concurrently. A process-wide semaphore in
    # ocr.py bounds total in-flight OCR calls (across all docs) to stay within the
    # provider's rate limit; this only controls per-document fan-out.
    results: list[dict] = [None] * len(pages)  # type: ignore[list-item]
    with ThreadPoolExecutor(max_workers=settings.ocr_concurrency) as ex:
        for page_no, res in ex.map(
            _ocr_page, [(i, p) for i, p in enumerate(pages, start=1)]
        ):
            results[page_no - 1] = res

    blocks: list[Block] = []
    confidences: list[float] = []
    any_low = False
    language = None
    for page_no, result in enumerate(results, start=1):
        conf = float(result.get("confidence", 0.7))
        low = bool(result.get("handwritten")) or conf < 0.6
        any_low = any_low or low
        confidences.append(conf)
        language = language or result.get("language")
        text = (result.get("text") or "").strip()
        if text:
            blocks.append(Block(text=text, page=page_no, low_confidence=low))

    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    return ExtractResult(
        fmt="pdf-scanned",
        method=f"pdf2image {settings.ocr_dpi}DPI + OpenRouter OCR ({settings.model_ocr})",
        confidence=avg_conf,
        low_confidence=any_low,
        blocks=blocks,
        language=language,
    )
