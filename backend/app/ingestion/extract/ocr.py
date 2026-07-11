"""OCR via OpenRouter multimodal (scope §3, demo build).

One call per rasterised page/image. The prompt asks for faithful transcription
(Devanagari, regional scripts, tables, charts) and an explicit low-confidence flag
for handwriting or degraded scans, so unverifiable content is never presented as
fact. Production swaps this for a dedicated engine (Sarvam Vision / Surya, §12).
"""

from __future__ import annotations

import asyncio
import base64
import json
import re
import threading

from app.config import settings
from app.models import llm

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")

# Process-wide cap on concurrent OCR calls (shared across all documents/threads)
# so parallel per-page fan-out stays within the provider rate limit.
_OCR_SEM = threading.Semaphore(settings.ocr_concurrency)

_OCR_PROMPT = (
    "You are an OCR engine for Indian government documents. Transcribe ALL text "
    "faithfully and verbatim, preserving Devanagari and regional scripts, numbers, "
    "dates, and reference numbers exactly. Render tables as GitHub-flavoured "
    "markdown, keeping every row intact. Do not summarise, translate, or invent "
    "text. Respond as JSON: "
    '{"text": "<full transcription incl. markdown tables>", '
    '"language": "<primary ISO code>", '
    '"handwritten": <true|false>, '
    '"confidence": <0.0-1.0>}'
)


def _parse_ocr(raw: str) -> dict:
    """Parse the model's OCR JSON robustly.

    Primary path is JSON mode (clean JSON). As a safety net we also strip a
    markdown ```json fence and retry. A parse failure is NOT low OCR quality, so
    the fallback keeps the (fence-stripped) text and a neutral confidence rather
    than defaulting to a value that would trip the low-confidence flag.
    """
    for candidate in (raw, _FENCE_RE.sub("", raw).strip()):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception:  # noqa: BLE001
            continue
    # Last-resort object slice.
    try:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            return json.loads(raw[start : end + 1])
    except Exception:  # noqa: BLE001
        pass
    # Could not parse structure: treat cleaned text as the transcription with a
    # neutral (non-flagging) confidence.
    return {
        "text": _FENCE_RE.sub("", raw).strip(),
        "language": None,
        "handwritten": False,
        "confidence": 0.8,
    }


def ocr_image_bytes(png_bytes: bytes, mime: str = "image/png") -> dict:
    """Return {text, language, handwritten, confidence} for one image."""
    b64 = base64.b64encode(png_bytes).decode("ascii")
    # JSON mode -> clean, properly-escaped JSON without a markdown fence.
    with _OCR_SEM:
        raw = asyncio.run(
            llm.vision(
                _OCR_PROMPT, b64, mime=mime, response_format={"type": "json_object"}
            )
        )
    data = _parse_ocr(raw)
    data.setdefault("text", "")
    data.setdefault("confidence", 0.8)
    data.setdefault("handwritten", False)
    return data
