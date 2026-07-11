"""Ingestion API (scope §10).

POST /ingest              : multipart bulk upload -> job id + doc refs; enqueues
                            one async Celery task per file.
GET  /ingest/{job}/events : SSE stream of per-stage updates for that job.
GET  /documents           : corpus-view listing.
GET  /documents/{doc_id}  : one document with its five ingestion stages.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.events import subscribe_stages
from app.schemas import IngestAccepted, IngestDocRef
from app.stores.postgres import get_document, list_documents, upsert_document
from app.tasks.ingest_tasks import process_document

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestAccepted)
async def ingest(files: list[UploadFile]) -> IngestAccepted:
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    job_id = uuid.uuid4().hex
    os.makedirs(settings.upload_dir, exist_ok=True)
    queued: list[dict] = []  # internal: carries the on-disk path

    for f in files:
        doc_id = uuid.uuid4().hex
        dest = os.path.join(settings.upload_dir, f"{doc_id}__{f.filename}")
        with open(dest, "wb") as out:
            out.write(await f.read())

        # Register immediately so the corpus view shows it as queued.
        upsert_document(
            {
                "doc_id": doc_id,
                "filename": f.filename,
                "fmt": None,
                "category": None,
                "status": "queued",
                "classify_method": None,
                "classify_confidence": None,
                "extract_method": None,
                "extract_confidence": None,
                "low_confidence": False,
                "chunk_count": 0,
                "indexed_dense": 0,
                "indexed_sparse": 0,
                "rows_to_sql": 0,
                "error": None,
                "stages": [],
            }
        )
        queued.append({"doc_id": doc_id, "filename": f.filename, "path": dest})

    if settings.celery_eager:
        # Single-process local run: process inline in a worker thread (sequential,
        # so the embedded Qdrant single-writer and blocking asyncio.run calls are
        # safe) so we don't block the event loop.
        async def _run_all():
            for r in queued:
                await asyncio.to_thread(
                    process_document, job_id, r["doc_id"], r["filename"], r["path"]
                )

        asyncio.create_task(_run_all())
    else:
        for r in queued:
            process_document.delay(job_id, r["doc_id"], r["filename"], r["path"])

    return IngestAccepted(
        job_id=job_id,
        documents=[
            IngestDocRef(doc_id=r["doc_id"], filename=r["filename"]) for r in queued
        ],
    )


@router.get("/ingest/{job_id}/events")
async def ingest_events(job_id: str):
    async def event_source():
        async for update in subscribe_stages(job_id):
            if update.get("event") == "job_done":
                yield {"event": "job_done", "data": "{}"}
                break
            yield {"event": "stage", "data": _json(update)}

    return EventSourceResponse(event_source())


@router.get("/documents")
async def documents() -> list[dict]:
    return list_documents()


@router.get("/documents/{doc_id}")
async def document(doc_id: str) -> dict:
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def _json(obj: dict) -> str:
    import json

    return json.dumps(obj)
