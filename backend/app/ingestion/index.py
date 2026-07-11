"""Dual-path indexing (scope §5, step 5).

Text chunks -> Jina dense + FastEmbed sparse -> Qdrant (RRF hybrid ready).
Tables / numerical rows / action items -> PostgreSQL for exact querying.
"""

from __future__ import annotations

import asyncio
import json
import threading

from app.ingestion.chunk import Chunk
from app.ingestion.types import ExtractResult
from app.models import embeddings, llm
from app.schemas import DocCategory
from app.stores import postgres, qdrant

# Serialise indexing so overlapping ingests don't race the embedded (single-writer)
# Qdrant or the FastEmbed sparse model.
_INDEX_LOCK = threading.Lock()


def index_chunks(chunks: list[Chunk]) -> tuple[int, int]:
    """Embed and upsert chunks into Qdrant. Returns (dense_count, sparse_count)."""
    if not chunks:
        return 0, 0
    qdrant.ensure_collection()

    texts = [c.embed_text for c in chunks]
    # Serialize embedding + upsert across worker threads: OCR (the slow, parallel
    # part) runs outside this lock, but the Jina embed calls are gated so parallel
    # workers don't collectively exceed the embeddings rate limit (429).
    with _INDEX_LOCK:
        dense = asyncio.run(embeddings.embed_passages(texts))
        sparse = embeddings.sparse_embed(texts)
        points = []
        for c, d, s in zip(chunks, dense, sparse):
            points.append(
                {
                    "id": c.chunk_id,
                    "dense": d,
                    "sparse": s,
                    "payload": {
                        "doc_id": c.doc_id,
                        "filename": c.filename,
                        "category": c.category,
                        "text": c.text,
                        "section": c.section,
                        "page": c.page,
                        "language": c.language,
                        "extraction_confidence": c.extraction_confidence,
                        "low_confidence": c.low_confidence,
                        "is_table": c.is_table,
                        "ref_number": c.ref_number,
                        "parent_section": c.parent_section,
                    },
                }
            )
        qdrant.upsert_chunks(points)
    return len(points), len(points)


def write_tables_to_sql(doc_id: str, filename: str, extracted: ExtractResult) -> int:
    """Persist every table's rows to PostgreSQL for the exact-query path."""
    total = 0
    for i, table in enumerate(extracted.tables):
        sheet = table.sheet or f"table_{i + 1}"
        total += postgres.insert_financial_rows(doc_id, filename, sheet, table.rows)
    return total


def extract_action_items(doc_id: str, filename: str, extracted: ExtractResult) -> int:
    """Records & Correspondence: pull action items to PostgreSQL (scope §4, §5)."""
    text = "\n".join(b.text for b in extracted.blocks)[:8000]
    if not text.strip():
        return 0
    prompt = (
        "Extract action items from these meeting minutes / correspondence. "
        "Return JSON: {\"items\": [{\"agenda_item\": str, \"owner\": str, "
        "\"action\": str, \"due\": str}]}. Use empty strings when unknown. "
        "If there are no action items, return an empty list.\n\n" + text
    )
    try:
        data = asyncio.run(llm.chat_json([{"role": "user", "content": prompt}]))
        items = data.get("items", [])
    except Exception:
        items = []
    return postgres.insert_action_items(doc_id, filename, items)
