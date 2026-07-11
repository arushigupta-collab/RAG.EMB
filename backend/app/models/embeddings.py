"""Embeddings: Jina dense (API) + FastEmbed sparse (local, CPU).

Hybrid retrieval (scope §6.1) needs a dense channel and a learned-sparse channel.
Jina embeddings are dense-only, so the sparse (lexical) channel is produced locally
by FastEmbed SPLADE — no GPU. Both are fused with RRF in the Qdrant store layer.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Iterable

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.config import settings

# FastEmbed's model init + tqdm progress bar are not thread-safe on first use;
# serialise model loading and sparse embedding across threads.
_sparse_lock = threading.Lock()

# Per-request batch size for Jina embeddings (keeps requests small under parallel
# ingestion so we stay within rate limits).
_EMBED_BATCH = 96


def _is_retryable(exc: Exception) -> bool:
    """Retry on rate limits (429) and transient server/network errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return isinstance(exc, (httpx.TransportError, httpx.TimeoutException))


# --------------------------------------------------------------------------- #
# Dense — Jina API
# --------------------------------------------------------------------------- #
@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential_jitter(initial=1, max=30),
    stop=stop_after_attempt(6),
    reraise=True,
)
async def _jina_embed(texts: list[str], task: str) -> list[list[float]]:
    payload = {
        "model": settings.jina_embed_model,
        "task": task,
        "input": [{"text": t} for t in texts],
    }
    headers = {
        "Authorization": f"Bearer {settings.jina_api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{settings.jina_base_url}/embeddings", headers=headers, json=payload
        )
        r.raise_for_status()
        data = r.json()["data"]
    # Jina preserves input order.
    return [row["embedding"] for row in sorted(data, key=lambda d: d["index"])]


async def embed_passages(texts: list[str]) -> list[list[float]]:
    # Batch so large documents don't send one oversized request under parallelism.
    out: list[list[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        out.extend(await _jina_embed(texts[i : i + _EMBED_BATCH], settings.jina_task_passage))
    return out


async def embed_query(text: str) -> list[float]:
    return (await _jina_embed([text], settings.jina_task_query))[0]


# --------------------------------------------------------------------------- #
# Sparse — FastEmbed SPLADE (local, CPU)
# --------------------------------------------------------------------------- #
@lru_cache
def _sparse_model():
    # Imported lazily so the API process starts without loading model weights.
    from fastembed import SparseTextEmbedding

    return SparseTextEmbedding(model_name=settings.sparse_model)


def warmup_sparse() -> None:
    """Load the sparse model once at startup to avoid a first-use thread race."""
    with _sparse_lock:
        _sparse_model().embed(["warmup"])


def sparse_embed(texts: Iterable[str]) -> list[dict]:
    """Return Qdrant-shaped sparse vectors: {'indices': [...], 'values': [...]}."""
    with _sparse_lock:
        out = []
        for emb in _sparse_model().embed(list(texts)):
            out.append({"indices": emb.indices.tolist(), "values": emb.values.tolist()})
        return out


def sparse_embed_one(text: str) -> dict:
    return sparse_embed([text])[0]
