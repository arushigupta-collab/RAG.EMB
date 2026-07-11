"""Text-to-SQL path for exact numerical / aggregate queries (scope §6, step 2).

Financial rows live in PostgreSQL as `financial_rows(doc_id, filename, sheet,
row_data jsonb)`. The fast tier generates a single read-only SELECT over the JSONB
keys actually present in the corpus; execution is guarded (read-only, single
statement, SELECT/WITH only) by the store layer.
"""

from __future__ import annotations

from app.models import llm
from app.stores import postgres


def _available_keys(limit: int = 200) -> list[str]:
    with postgres.conn() as c:
        rows = c.execute(
            "SELECT DISTINCT jsonb_object_keys(row_data) AS k "
            "FROM financial_rows LIMIT %s",
            (limit,),
        ).fetchall()
    return sorted(r["k"] for r in rows)


def _sample_rows(limit: int = 3) -> list[dict]:
    with postgres.conn() as c:
        rows = c.execute(
            "SELECT filename, sheet, row_data FROM financial_rows LIMIT %s", (limit,)
        ).fetchall()
    return rows


async def answer_with_sql(query: str) -> dict:
    """Return {sql, rows, keys} for the exact-query path (empty rows if none)."""
    keys = _available_keys()
    if not keys:
        return {"sql": None, "rows": [], "keys": []}

    samples = _sample_rows()
    prompt = (
        "You write PostgreSQL for a single read-only query.\n"
        "Table: financial_rows(doc_id text, filename text, sheet text, row_data jsonb).\n"
        "Each row's data is in the JSONB column `row_data`. Access fields with "
        "row_data->>'Field'. Cast to numeric for math, e.g. "
        "(row_data->>'Capacity')::numeric. Always also SELECT filename and sheet so "
        "results are traceable to their source.\n"
        f"Available row_data keys: {keys}\n"
        f"Example rows: {[s['row_data'] for s in samples]}\n"
        "Return JSON: {\"sql\": \"<one SELECT statement, no trailing semicolon>\"}.\n\n"
        f"Question: {query}"
    )
    data = await llm.chat_json(
        [{"role": "user", "content": prompt}], model=llm.settings.model_fast
    )
    sql = (data.get("sql") or "").strip()
    if not sql:
        return {"sql": None, "rows": [], "keys": keys}
    try:
        rows = postgres.run_readonly_sql(sql)
    except Exception as exc:  # noqa: BLE001 - surface as no-result, never crash
        return {"sql": sql, "rows": [], "keys": keys, "error": str(exc)}
    return {"sql": sql, "rows": rows, "keys": keys}
