"""FastAPI entrypoint for the MNRE RAG sandbox."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, ingest, query
from app.config import settings
from app.stores.qdrant import ensure_collection


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Best-effort: create the Qdrant collection on boot. Non-fatal if Qdrant is
    # still starting; the ingestion path also ensures it.
    try:
        ensure_collection()
    except Exception:  # noqa: BLE001
        pass
    # Pre-load the sparse embedding model so the first concurrent ingest does not
    # race FastEmbed's tqdm/model init.
    try:
        from app.models.embeddings import warmup_sparse

        await asyncio.to_thread(warmup_sparse)
    except Exception:  # noqa: BLE001
        pass
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ingest.router)
app.include_router(query.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
