"""Re-rank stage (scope §6.1, step 3).

Cross-encoder re-ranks the hybrid candidates and keeps the top-k for generation.
Thin async wrapper over the Jina rerank client that maps scores back onto the
candidate payloads.
"""

from __future__ import annotations

from app.config import settings
from app.models import rerank as rerank_model


async def rerank_candidates(query: str, candidates: list[dict]) -> list[dict]:
    if not candidates:
        return []
    docs = [_doc_text(c["payload"]) for c in candidates]
    ranked = await rerank_model.rerank(query, docs, top_k=settings.rerank_top_k)
    out: list[dict] = []
    for r in ranked:
        c = dict(candidates[r["index"]])
        c["rerank_score"] = r["score"]
        out.append(c)
    return out


def _doc_text(payload: dict) -> str:
    section = payload.get("section") or ""
    text = payload.get("text") or ""
    return f"{section}\n{text}" if section else text
