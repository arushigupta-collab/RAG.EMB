"""Qdrant store: named dense + sparse vectors, RRF hybrid search (scope §5, §6.1).

Dense vectors come from Jina; sparse from local FastEmbed SPLADE. Qdrant's Query
API performs the reciprocal-rank fusion across both prefetch branches.
"""

from __future__ import annotations

import threading
from functools import lru_cache

from qdrant_client import QdrantClient, models

from app.config import settings

DENSE = "dense"
SPARSE = "sparse"

# Guards concurrent first-time collection creation across worker threads.
_ensure_lock = threading.Lock()


@lru_cache
def client() -> QdrantClient:
    # Embedded on-disk mode for a no-server local run; otherwise a Qdrant server.
    if settings.qdrant_local_path:
        return QdrantClient(path=settings.qdrant_local_path)
    return QdrantClient(url=settings.qdrant_url, prefer_grpc=False)


def ensure_collection() -> None:
    c = client()
    if c.collection_exists(settings.qdrant_collection):
        return
    # Lock guards threads in this process; the try/except handles the cross-process
    # race (another worker created it between the check and create) idempotently.
    with _ensure_lock:
        if c.collection_exists(settings.qdrant_collection):
            return
        try:
            c.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config={
                    DENSE: models.VectorParams(
                        size=settings.jina_embed_dim, distance=models.Distance.COSINE
                    )
                },
                sparse_vectors_config={SPARSE: models.SparseVectorParams()},
            )
        except Exception as exc:  # noqa: BLE001
            if "already exists" not in str(exc).lower():
                raise


def upsert_chunks(points: list[dict]) -> None:
    """points: [{id, dense:[...], sparse:{indices,values}, payload:{...}}]."""
    c = client()
    c.upsert(
        collection_name=settings.qdrant_collection,
        points=[
            models.PointStruct(
                id=p["id"],
                vector={
                    DENSE: p["dense"],
                    SPARSE: models.SparseVector(
                        indices=p["sparse"]["indices"], values=p["sparse"]["values"]
                    ),
                },
                payload=p["payload"],
            )
            for p in points
        ],
    )


def hybrid_search(
    dense_vec: list[float], sparse_vec: dict, top_k: int
) -> list[dict]:
    """Dense + sparse searches fused with reciprocal rank fusion (scope §6.1).

    RRF is computed in Python so this works identically in embedded (local) and
    server modes. rank constant k defaults to settings.rrf_k (~60).
    """
    c = client()

    dense_hits = c.query_points(
        collection_name=settings.qdrant_collection,
        query=dense_vec,
        using=DENSE,
        limit=top_k,
        with_payload=True,
    ).points

    sparse_hits = c.query_points(
        collection_name=settings.qdrant_collection,
        query=models.SparseVector(
            indices=sparse_vec["indices"], values=sparse_vec["values"]
        ),
        using=SPARSE,
        limit=top_k,
        with_payload=True,
    ).points

    k = settings.rrf_k
    fused: dict = {}
    for hits in (dense_hits, sparse_hits):
        for rank, pt in enumerate(hits):
            entry = fused.setdefault(
                pt.id, {"id": pt.id, "payload": pt.payload, "score": 0.0}
            )
            entry["score"] += 1.0 / (k + rank + 1)
    ranked = sorted(fused.values(), key=lambda e: e["score"], reverse=True)
    return ranked[:top_k]
