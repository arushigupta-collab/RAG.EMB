"""Grounding / verification (scope §6, step 5).

Two mechanisms:
1. Retrieval-time grounding threshold: if the best reranked candidate scores below
   the threshold, the corpus does not support an answer -> withhold ("no-source").
2. Post-generation citation check: every [n] marker in the answer must reference a
   real source. Numerical claims should trace to a retrieved chunk / SQL row.
"""

from __future__ import annotations

import re

from app.config import settings

_CITE_RE = re.compile(r"\[(\d+)\]")


def passes_threshold(chunks: list[dict]) -> bool:
    if not chunks:
        return False
    best = max(float(c.get("rerank_score", c.get("score", 0.0))) for c in chunks)
    return best >= settings.grounding_threshold


def verify_citations(answer: str, num_sources: int) -> tuple[str, str]:
    """Return (verdict, detail). Verdict is 'verified' or 'no-source'."""
    markers = {int(m) for m in _CITE_RE.findall(answer)}
    if not markers:
        # No citations produced -> treat as ungrounded unless it is an explicit
        # "not supported" style refusal handled upstream.
        return "no-source", "answer produced no citations"
    invalid = {n for n in markers if n < 1 or n > num_sources}
    if invalid:
        return "no-source", f"answer cited non-existent sources: {sorted(invalid)}"
    return "verified", f"{len(markers)} citation(s), all resolve to sources"
