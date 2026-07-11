"""Query API (scope §10).

POST /query (SSE): emits ordered `step` events, then `token` deltas, then a final
`evidence` array, then a `grounding` verdict. Citation markers stay as [n] in the
answer text so they map to the evidence array.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.query.pipeline import run_query
from app.schemas import QueryRequest

router = APIRouter(tags=["query"])


@router.post("/query")
async def query(req: QueryRequest):
    async def event_source():
        async for ev in run_query(req.query, req.language):
            etype = ev.pop("type")
            if etype == "step":
                yield {"event": "step", "data": json.dumps(ev)}
            elif etype == "token":
                yield {"event": "token", "data": json.dumps(ev)}
            elif etype == "evidence":
                yield {"event": "evidence", "data": json.dumps(ev["items"])}
            elif etype == "grounding":
                yield {"event": "grounding", "data": json.dumps(ev)}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_source())
