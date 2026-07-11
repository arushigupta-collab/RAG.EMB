"""Per-document ingestion task (scope §5): classify -> extract -> chunk -> index.

Each stage publishes a per-stage update (scope §10) and the document registry is
updated so the corpus view reflects live progress. One failed file never blocks the
rest of the batch (scope §5.1): failures are caught, recorded, and reported.
"""

from __future__ import annotations

from app.events import publish_done, publish_stage
from app.ingestion import index
from app.ingestion.chunk import chunk_document
from app.ingestion.classify import classify
from app.ingestion.extract.router import detect_and_extract
from app.schemas import DocCategory
from app.stores.postgres import upsert_document
from app.tasks.celery_app import celery_app


@celery_app.task(name="ingest.process_document")
def process_document(job_id: str, doc_id: str, filename: str, path: str) -> None:
    stages: list[dict] = []
    record = {
        "doc_id": doc_id,
        "filename": filename,
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
    }

    def emit(stage: str, status: str, detail: str) -> None:
        stages.append({"stage": stage, "detail": detail, "status": status})
        record["status"] = status
        upsert_document({**record, "stages": stages})
        publish_stage(
            job_id,
            {
                "doc_id": doc_id,
                "filename": filename,
                "stage": stage,
                "status": status,
                "detail": detail,
            },
        )

    try:
        # 1) Extract first so classification can use the header text.
        emit("extract", "extracting", "detecting format and reading content")
        extracted = detect_and_extract(path, filename)
        header_text = "\n".join(b.text for b in extracted.blocks[:8])
        record.update(
            fmt=extracted.fmt,
            extract_method=extracted.method,
            extract_confidence=round(extracted.confidence, 2),
            low_confidence=extracted.low_confidence,
        )
        low_note = " · low-confidence content flagged" if extracted.low_confidence else ""
        emit("extract", "extracting", f"{extracted.method}{low_note}")

        # 2) Classify.
        emit("classify", "classifying", "assigning category")
        category, method, conf = classify(filename, header_text)
        record.update(
            category=category.value, classify_method=method, classify_confidence=conf
        )
        emit("classify", "classifying", f"{category.value} · {method} ({conf:.0%})")

        # 3) Chunk.
        emit("chunk", "chunking", "structure-aware chunking")
        title = filename.rsplit(".", 1)[0].replace("_", " ")
        chunks = chunk_document(doc_id, filename, title, category, extracted)
        record["chunk_count"] = len(chunks)
        emit("chunk", "chunking", f"{len(chunks)} chunks (section/table boundaries)")

        # 4) Index: vectors -> Qdrant; rows / action items -> PostgreSQL.
        emit("index", "indexing", "embedding and indexing")
        dense_n, sparse_n = index.index_chunks(chunks)
        # Only true spreadsheets (CSV/TSV/Excel) feed the exact-query SQL store:
        # their rows have a consistent schema for Text-to-SQL. PDF find_tables output
        # is fragmentary and would pollute the store, so it stays as vector chunks
        # only. (Scope §4/§5: exact numeric data comes from disbursement/capacity
        # sheets, which are spreadsheets.)
        rows = 0
        if extracted.fmt in ("csv", "tsv", "xlsx", "xls"):
            rows = index.write_tables_to_sql(doc_id, filename, extracted)
        actions = 0
        if category == DocCategory.records_correspondence:
            actions = index.extract_action_items(doc_id, filename, extracted)
        record.update(indexed_dense=dense_n, indexed_sparse=sparse_n, rows_to_sql=rows)
        detail = f"{dense_n} vectors -> Qdrant"
        if rows:
            detail += f" · {rows} rows -> PostgreSQL"
        if actions:
            detail += f" · {actions} action items"
        emit("index", "done", detail)

        record["status"] = "done"
        upsert_document({**record, "stages": stages})

    except Exception as exc:  # noqa: BLE001 - isolate failures per document
        record.update(status="failed", error=str(exc))
        stages.append({"stage": "index", "detail": str(exc), "status": "failed"})
        upsert_document({**record, "stages": stages})
        publish_stage(
            job_id,
            {
                "doc_id": doc_id,
                "filename": filename,
                "stage": "index",
                "status": "failed",
                "detail": str(exc),
            },
        )
    finally:
        publish_done(job_id)
