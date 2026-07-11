"""Hybrid retrieval (scope §6.1).

A single Jina query embedding (dense) and a local FastEmbed sparse vector are
searched concurrently in Qdrant and fused with RRF, returning the top-N candidates.
Dense captures meaning/paraphrase and cross-lingual reach; sparse matches the exact
tokens government policy text is dense with (PM-KUSUM, ALMM, CFA, ref numbers).
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.models import embeddings
from app.stores import qdrant


async def hybrid_retrieve(query: str, top_k: int | None = None) -> list[dict]:
    top_k = top_k or settings.retrieve_top_k

    # Dense (async API) and sparse (CPU, run in a thread) computed concurrently.
    dense_task = asyncio.create_task(embeddings.embed_query(query))
    sparse_task = asyncio.create_task(asyncio.to_thread(embeddings.sparse_embed_one, query))
    dense_vec, sparse_vec = await asyncio.gather(dense_task, sparse_task)

    # Qdrant performs the RRF fusion across the two prefetch branches.
    return await asyncio.to_thread(qdrant.hybrid_search, dense_vec, sparse_vec, top_k)
