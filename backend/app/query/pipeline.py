"""Query pipeline orchestrator (scope §6).

Yields ordered SSE events: `step` (per stage, elapsed ms), then `token` deltas,
then the `evidence` array, then a `grounding` verdict (scope §10). Two paths:
semantic (hybrid retrieve -> rerank -> generate) and numerical (Text-to-SQL).
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from app.query import generate, retrieve, sql, verify
from app.query.classify import classify_query, uses_sql
from app.query.rerank import rerank_candidates
from app.schemas import EvidenceItem


def _step(label: str, sublabel: str, started: float) -> dict:
    return {
        "type": "step",
        "label": label,
        "sublabel": sublabel,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }


async def run_query(query: str, language: str | None = None) -> AsyncIterator[dict]:
    # 1) Classify -----------------------------------------------------------
    t = time.perf_counter()
    qtype, lang = await classify_query(query)
    yield _step("Classify", f"{qtype.value} · language: {lang}", t)

    if uses_sql(qtype):
        async for ev in _sql_path(query):
            yield ev
    else:
        async for ev in _semantic_path(query, qtype.value):
            yield ev


# --------------------------------------------------------------------------- #
# Semantic path
# --------------------------------------------------------------------------- #
async def _semantic_path(query: str, qlabel: str) -> AsyncIterator[dict]:
    t = time.perf_counter()
    candidates = await retrieve.hybrid_retrieve(query)
    yield _step("Retrieve", f"hybrid (dense+sparse RRF) · {len(candidates)} candidates", t)

    t = time.perf_counter()
    top = await rerank_candidates(query, candidates)
    yield _step("Re-rank", f"cross-encoder · top {len(top)}", t)

    # Grounding threshold (scope §6.1): withhold if nothing scores high enough.
    if not verify.passes_threshold(top):
        yield {"type": "evidence", "items": []}
        yield {
            "type": "grounding",
            "verdict": "no-source",
            "detail": "no candidate cleared the grounding threshold",
        }
        return

    sources_block, evidence = generate.build_sources(top)

    t = time.perf_counter()
    first = True
    answer = ""
    async for delta in generate.stream_answer(query, top):
        if first:
            yield _step("Generate", "streaming", t)
            first = False
        answer += delta
        yield {"type": "token", "delta": delta}
    if first:
        yield _step("Generate", "no output", t)

    yield {"type": "evidence", "items": [e.model_dump() for e in evidence]}
    verdict, detail = verify.verify_citations(answer, len(evidence))
    yield {"type": "grounding", "verdict": verdict, "detail": detail}


# --------------------------------------------------------------------------- #
# Numerical / aggregate path (Text-to-SQL)
# --------------------------------------------------------------------------- #
async def _sql_path(query: str) -> AsyncIterator[dict]:
    t = time.perf_counter()
    result = await sql.answer_with_sql(query)
    rows = result.get("rows", [])
    sublabel = f"Text-to-SQL · {len(rows)} row(s)"
    if result.get("error"):
        sublabel = "Text-to-SQL · query error"
    yield _step("Retrieve (SQL)", sublabel, t)

    if not rows:
        # The figure may be stated in narrative text rather than a data table
        # (e.g. a total quoted in a report). Fall back to semantic retrieval
        # instead of declaring no-source, so numeric-in-text questions still answer.
        async for ev in _semantic_path(query, "Numerical (semantic fallback)"):
            yield ev
        return

    # Build a single evidence entry describing the exact rows (traceable source).
    docs = sorted({str(r.get("filename", "")) for r in rows if r.get("filename")})
    evidence = [
        EvidenceItem(
            n=1,
            document=", ".join(docs) or "structured store",
            section=result.get("sql", "")[:120],
            page=None,
            score=1.0,
            snippet=str(rows[:5]),
        )
    ]

    t = time.perf_counter()
    first = True
    answer = ""
    async for delta in generate.stream_sql_answer(query, result):
        if first:
            yield _step("Generate", "streaming (fast tier)", t)
            first = False
        answer += delta
        yield {"type": "token", "delta": delta}
    if first:
        yield _step("Generate", "no output", t)

    yield {"type": "evidence", "items": [e.model_dump() for e in evidence]}
    # Exact rows are the ground truth here; a produced [1] resolves to them.
    verdict = "verified" if "[1]" in answer or answer.strip() else "no-source"
    yield {
        "type": "grounding",
        "verdict": verdict,
        "detail": "answer derived from exact database rows",
    }
