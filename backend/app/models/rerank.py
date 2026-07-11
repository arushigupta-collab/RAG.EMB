"""Cross-encoder re-ranking via the Jina rerank API (scope §6.1, step 3).

Takes the top-20 hybrid candidates and returns the top-k (default 5) with scores.
"""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def rerank(query: str, documents: list[str], top_k: int | None = None) -> list[dict]:
    """Return [{'index': i, 'score': s}, ...] sorted by relevance, top_k retained."""
    if not documents:
        return []
    top_k = top_k or settings.rerank_top_k
    payload = {
        "model": settings.jina_rerank_model,
        "query": query,
        "documents": documents,
        "top_n": min(top_k, len(documents)),
        "return_documents": False,
    }
    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{settings.jina_base_url}/rerank", headers=headers, json=payload
        )
        r.raise_for_status()
        results = r.json()["results"]
    return [
        {"index": row["index"], "score": row["relevance_score"]} for row in results
    ]
