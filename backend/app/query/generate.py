"""Answer generation (scope §6, step 4).

Streams a response with per-claim [n] citations keyed to the retrieved sources,
using a fixed citation-aware system prompt (kept constant so it can be context-
cached, §8). Response format (narrative / tabular / bullet) is left to the model to
adapt to the query. The same numbering is returned as the evidence array (§10).
"""

from __future__ import annotations

from typing import AsyncIterator

from app.models import llm
from app.schemas import EvidenceItem

# Constant across requests -> eligible for provider context caching (scope §8).
SYSTEM_PROMPT = (
    "You answer questions about Indian renewable-energy (MNRE) documents using ONLY "
    "the numbered sources provided. Rules:\n"
    "1. Cite every factual claim inline with its source marker like [1], [2]. A "
    "sentence drawing on two sources ends with [1][3].\n"
    "2. Use ONLY the sources. If they do not support an answer, say so plainly and "
    "do not guess.\n"
    "3. Preserve exact figures, dates, scheme names, and reference numbers verbatim.\n"
    "4. Choose the clearest format for the question: a short narrative, a markdown "
    "table for comparisons/numbers, or bullets for lists. Do not be asked; decide.\n"
    "5. Answer in the same language as the question when it is not English.\n"
)


def build_sources(chunks: list[dict]) -> tuple[str, list[EvidenceItem]]:
    """Number the reranked chunks; return the prompt block and evidence items."""
    lines: list[str] = []
    evidence: list[EvidenceItem] = []
    for i, c in enumerate(chunks, start=1):
        p = c["payload"]
        section = p.get("section") or ""
        page = p.get("page")
        # Small-to-big: hand the fuller parent-section label to the model as context.
        header = f"[{i}] {p.get('filename')}"
        if section:
            header += f" · {section}"
        if page is not None:
            header += f" · p.{page}"
        lines.append(f"{header}\n{p.get('text', '')}")
        evidence.append(
            EvidenceItem(
                n=i,
                document=p.get("filename", ""),
                section=section,
                page=page,
                score=round(float(c.get("rerank_score", c.get("score", 0.0))), 4),
                snippet=(p.get("text", "")[:400]),
            )
        )
    return "\n\n".join(lines), evidence


async def stream_answer(query: str, chunks: list[dict]) -> AsyncIterator[str]:
    sources, _ = build_sources(chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Sources:\n{sources}\n\nQuestion: {query}"},
    ]
    async for delta in llm.chat_stream(messages, model=llm.settings.model_generation):
        yield delta


async def stream_sql_answer(query: str, sql_result: dict) -> AsyncIterator[str]:
    rows = sql_result.get("rows", [])
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "The following exact rows were returned from the structured database "
                f"for the question. Cite them as [1] (the database result).\n"
                f"SQL: {sql_result.get('sql')}\n"
                f"Rows: {rows}\n\nQuestion: {query}"
            ),
        },
    ]
    # Fast tier: exact-number answers should return quickly (scope §8, <1.5s).
    async for delta in llm.chat_stream(messages, model=llm.settings.model_fast):
        yield delta
