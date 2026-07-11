"""Query classification (scope §6, step 1).

Detects language and classifies the query as Semantic / Numerical Lookup /
Aggregate / Comparison / Mixed on the fast tier. This selects the retrieval path:
Semantic/Comparison -> hybrid vector search; Numerical Lookup/Aggregate -> SQL.
"""

from __future__ import annotations

from app.models import llm
from app.schemas import QueryType

_PROMPT = (
    "Classify a user query about Indian renewable-energy government documents.\n"
    "Return JSON: {\"type\": one of "
    "[\"Semantic\",\"Numerical Lookup\",\"Aggregate\",\"Comparison\",\"Mixed\"], "
    "\"language\": \"<ISO 639-1 code of the query language>\"}.\n\n"
    "The numeric types apply ONLY when the answer must be read or computed from "
    "rows of an uploaded spreadsheet/table (e.g. per-state figures, disbursement "
    "sheets, capacity tables):\n"
    "- 'Numerical Lookup' = one exact value for a specific entity/row (e.g. "
    "'disbursed CFA for Gujarat').\n"
    "- 'Aggregate' = sum/count/average/max/total across rows (e.g. 'total "
    "sanctioned capacity across all states').\n"
    "- 'Comparison' = compare figures for two or more entities/rows.\n\n"
    "'Semantic' = the answer is stated in policy/report TEXT — scheme rules, "
    "rates, eligibility, definitions, procedures — EVEN IF the question is phrased "
    "as 'how much', 'what percentage', or 'kitni/kitna'. A scheme's benefit rate "
    "(e.g. 'how much CFA does PM Surya Ghar give for rooftop solar') is Semantic, "
    "not Numerical, because it is defined in guidelines, not a data table.\n"
    "'Mixed' = genuinely needs both narrative text and tabular numbers.\n"
    "When unsure between Semantic and a numeric type, choose Semantic.\n\n"
    "Query: "
)


async def classify_query(query: str) -> tuple[QueryType, str]:
    try:
        data = await llm.chat_json(
            [{"role": "user", "content": _PROMPT + query}], model=llm.settings.model_fast
        )
        qtype = QueryType(data["type"])
        lang = (data.get("language") or "en").lower()[:5]
        return qtype, lang
    except Exception:
        # Default to the semantic path in English on any failure.
        return QueryType.semantic, "en"


def uses_sql(qtype: QueryType) -> bool:
    return qtype in (QueryType.numerical_lookup, QueryType.aggregate)
