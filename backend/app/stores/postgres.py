"""PostgreSQL store: document registry + exact numerical/tabular data (scope §5, §6).

- `documents`      : per-document status + stage detail for the corpus view.
- `financial_rows` : rows extracted from Financial Data sheets for exact SQL answers.
- `action_items`   : action items extracted from meeting minutes.

The Text-to-SQL path (query/sql.py) runs read-only SELECTs against this store.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from app.config import settings


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.postgres_dsn, row_factory=dict_row) as c:
        yield c


# --------------------------------------------------------------------------- #
# Document registry
# --------------------------------------------------------------------------- #
def upsert_document(doc: dict) -> None:
    with conn() as c:
        c.execute(
            """
            INSERT INTO documents (doc_id, filename, fmt, category, status,
                classify_method, classify_confidence, extract_method,
                extract_confidence, low_confidence, chunk_count, indexed_dense,
                indexed_sparse, rows_to_sql, error, stages)
            VALUES (%(doc_id)s, %(filename)s, %(fmt)s, %(category)s, %(status)s,
                %(classify_method)s, %(classify_confidence)s, %(extract_method)s,
                %(extract_confidence)s, %(low_confidence)s, %(chunk_count)s,
                %(indexed_dense)s, %(indexed_sparse)s, %(rows_to_sql)s, %(error)s,
                %(stages)s)
            ON CONFLICT (doc_id) DO UPDATE SET
                fmt = EXCLUDED.fmt, category = EXCLUDED.category,
                status = EXCLUDED.status,
                classify_method = EXCLUDED.classify_method,
                classify_confidence = EXCLUDED.classify_confidence,
                extract_method = EXCLUDED.extract_method,
                extract_confidence = EXCLUDED.extract_confidence,
                low_confidence = EXCLUDED.low_confidence,
                chunk_count = EXCLUDED.chunk_count,
                indexed_dense = EXCLUDED.indexed_dense,
                indexed_sparse = EXCLUDED.indexed_sparse,
                rows_to_sql = EXCLUDED.rows_to_sql,
                error = EXCLUDED.error, stages = EXCLUDED.stages
            """,
            {**doc, "stages": json.dumps(doc.get("stages", []))},
        )
        c.commit()


def list_documents() -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
    for r in rows:
        if isinstance(r.get("stages"), str):
            r["stages"] = json.loads(r["stages"])
    return rows


def get_document(doc_id: str) -> dict | None:
    with conn() as c:
        r = c.execute(
            "SELECT * FROM documents WHERE doc_id = %s", (doc_id,)
        ).fetchone()
    if r and isinstance(r.get("stages"), str):
        r["stages"] = json.loads(r["stages"])
    return r


# --------------------------------------------------------------------------- #
# Financial rows + action items
# --------------------------------------------------------------------------- #
def insert_financial_rows(doc_id: str, filename: str, sheet: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    with conn() as c:
        for r in rows:
            c.execute(
                """INSERT INTO financial_rows (doc_id, filename, sheet, row_data)
                   VALUES (%s, %s, %s, %s)""",
                (doc_id, filename, sheet, json.dumps(r)),
            )
        c.commit()
    return len(rows)


def insert_action_items(doc_id: str, filename: str, items: list[dict]) -> int:
    if not items:
        return 0
    with conn() as c:
        for it in items:
            c.execute(
                """INSERT INTO action_items (doc_id, filename, agenda_item, owner, action, due)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    doc_id,
                    filename,
                    it.get("agenda_item"),
                    it.get("owner"),
                    it.get("action"),
                    it.get("due"),
                ),
            )
        c.commit()
    return len(items)


# --------------------------------------------------------------------------- #
# Read-only executor for the Text-to-SQL path (scope §6)
# --------------------------------------------------------------------------- #
def run_readonly_sql(sql: str, limit: int = 100) -> list[dict[str, Any]]:
    """Execute a single read-only SELECT inside a read-only transaction."""
    stripped = sql.strip().rstrip(";")
    if not stripped.lower().startswith(("select", "with")):
        raise ValueError("Only SELECT/WITH statements are allowed on the SQL path.")
    if ";" in stripped:
        raise ValueError("Multiple statements are not allowed.")
    with conn() as c:
        c.execute("SET TRANSACTION READ ONLY")
        rows = c.execute(f"SELECT * FROM ({stripped}) AS q LIMIT {limit}").fetchall()
    return rows
