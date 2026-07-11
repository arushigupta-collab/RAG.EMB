"""Document classification into four categories (scope §4).

Filename patterns + header keywords first (deterministic, free); a lightweight
model fallback (OpenRouter fast tier) only when those are inconclusive. The method
used and a confidence are recorded and shown per document in the corpus view.
"""

from __future__ import annotations

import asyncio
import json
import re

from app.models import llm
from app.schemas import DocCategory

_PATTERNS = {
    DocCategory.financial_data: [
        r"disburse", r"capacity", r"\bMW\b", r"\bcrore\b", r"budget", r"expenditure",
        r"sanction", r"release", r"financial", r"allocation",
    ],
    DocCategory.structured_policy: [
        r"guideline", r"circular", r"scheme", r"standard", r"policy", r"notification",
        r"regulation", r"amendment",
    ],
    DocCategory.records_correspondence: [
        r"minutes", r"meeting", r"agenda", r"note", r"correspondence", r"letter",
        r"memorandum", r"OM\b",
    ],
    DocCategory.implementation_reports: [
        r"progress", r"status", r"implementation", r"report", r"review", r"quarterly",
        r"annual report",
    ],
}


def _rule_score(filename: str, header_text: str) -> tuple[DocCategory | None, float]:
    hay = f"{filename}\n{header_text}".lower()
    scores: dict[DocCategory, int] = {}
    for cat, patterns in _PATTERNS.items():
        scores[cat] = sum(1 for p in patterns if re.search(p, hay))
    total = sum(scores.values())
    if total == 0:
        return None, 0.0
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0
    # Require a clear margin; a tie is inconclusive and defers to the model.
    if best_score == 0 or best_score == second_score:
        return None, 0.0
    # Confidence = share of matches going to the top category.
    return best, best_score / total


async def _model_classify(filename: str, header_text: str) -> tuple[DocCategory, float]:
    cats = [c.value for c in DocCategory]
    prompt = (
        "Classify this Indian government document into exactly one category.\n"
        f"Categories: {cats}\n"
        f"Filename: {filename}\n"
        f"First page/heading text:\n{header_text[:1500]}\n\n"
        'Respond as JSON: {"category": "<one of the categories>", '
        '"confidence": <0.0-1.0>}'
    )
    data = await llm.chat_json([{"role": "user", "content": prompt}])
    cat = DocCategory(data["category"])
    return cat, float(data.get("confidence", 0.7))


def classify(filename: str, header_text: str) -> tuple[DocCategory, str, float]:
    """Return (category, method, confidence)."""
    cat, conf = _rule_score(filename, header_text)
    if cat is not None and conf >= 0.5:
        return cat, "rules (filename + header keywords)", round(conf, 2)
    # Inconclusive -> model fallback.
    try:
        cat, conf = asyncio.run(_model_classify(filename, header_text))
        return cat, f"model fallback ({llm.settings.model_fast})", round(conf, 2)
    except Exception:
        # Safe default if the model call fails.
        return (
            DocCategory.structured_policy,
            "default (classification inconclusive)",
            0.3,
        )
