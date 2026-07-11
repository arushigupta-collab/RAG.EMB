# MNRE RAG Interface Testing Sandbox (Stage 2)

A self-service RAG web app for MNRE's Stage 2 Independent Interface Testing. Upload
250–500 mixed-format documents, then query them in English, Hindi, or a regional
language. Every processing step and every source citation is shown on screen.

Built to `MNRE_RAG_Sandbox_Scope.md` (v1.3). This is the **demo build**: generation
and OCR run on OpenRouter; embeddings and re-ranking run on the Jina API; the
retrieval and store stack (Qdrant + PostgreSQL) is identical to the on-prem
production build.

## Architecture

```
Next.js (SSE)  ──POST /ingest (multipart)─►  FastAPI ─► Celery/Redis ─► ingestion
               └─POST /query  (SSE)───────►  FastAPI ─► query pipeline (streaming)

Ingestion:  classify → extract (format-routed) → chunk (structure-aware) → index
              → Qdrant (Jina dense + BM25 sparse, RRF)  +  PostgreSQL (rows/actions)
Query:      classify → { hybrid retrieve → rerank | Text-to-SQL } → generate → verify

Models:  OpenRouter (generation + OCR),  Jina (dense embeddings + rerank),
         FastEmbed BM25 (sparse channel, CPU)
```

## Prerequisites

- Docker + Docker Compose
- An **OpenRouter** API key (generation, OCR, classification, Text-to-SQL)
- A **Jina** API key (dense embeddings + re-ranking)

No GPU is required: the embedding and re-rank models run on Jina's API, and the
sparse channel runs on CPU.

## Run locally

```bash
cp .env.example .env          # then fill in OPENROUTER_API_KEY and JINA_API_KEY
docker compose up --build
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health

> **Model ids** in `.env` (`MODEL_GENERATION`, `MODEL_FAST`, `MODEL_OCR`) follow the
> scope's naming and must be verified against live OpenRouter slugs before a real
> testing window. They are the only model settings; nothing is hardcoded.

## Config

Everything is env-driven (`backend/app/config.py`) so the same containers move to
GCP with only environment changes (scope §11): endpoints, keys, connection strings,
model ids, and retrieval knobs (`RRF_K`, `RETRIEVE_TOP_K`, `RERANK_TOP_K`,
`GROUNDING_THRESHOLD`).

## Verifying against the acceptance criteria (scope §14)

1. **Boot** — `docker compose up`; all six services healthy; the two surfaces load.
2. **Ingestion** — In *Corpus*, upload a mixed batch (text PDF, scanned PDF, .docx,
   .pptx, .xlsx, .csv, image, and a Hindi/Devanagari doc). Expand each row to see the
   category + method, the parser/extraction method, chunk count, and index result.
   A handwritten scan is flagged **low-confidence**. A deliberately corrupt file
   fails without blocking the batch.
3. **Semantic query** — In *Ask*, ask a policy question spanning ≥2 documents. The
   live trace shows Classify → Retrieve → Re-rank → Generate with per-step timing;
   the streamed answer has clickable `[n]` citations mapping to the evidence panel
   (document, section, page, score, passage); grounding = **verified**.
4. **Numerical query** — Ask for a disbursement/capacity figure. It routes to
   Text-to-SQL and returns the exact value, traceable to a source row.
5. **Out-of-corpus** — Ask something absent. The answer is **declined**
   (grounding = no-source), not fabricated.
6. **Multilingual** — Repeat a query in Hindi and one regional language over English
   sources; answers are coherent and cited.

## Layout

```
backend/app/
  config.py schemas.py main.py
  api/{ingest,query}.py            # scope §10 contract over SSE
  ingestion/{classify,chunk,index}.py + extract/*   # scope §3–5
  query/{classify,retrieve,sql,rerank,generate,verify,pipeline}.py  # scope §6
  models/{llm,embeddings,rerank}.py  # OpenRouter + Jina wrappers (swap points)
  stores/{qdrant,postgres}.py
  tasks/{celery_app,ingest_tasks}.py
frontend/app/{corpus,ask}/page.tsx  + components/*   # scope §9
infra/init.sql
```

## Production vs demo (scope §12)

Swap points are isolated in `backend/app/models/`: generation/OCR (OpenRouter → Vertex
or on-prem Savan) and embeddings/rerank are one-file changes. Qdrant, PostgreSQL, and
the parser stack are identical in both environments.
