#!/usr/bin/env bash
# Run the sandbox locally WITHOUT Docker, as the REAL multi-process stack:
#
#   Postgres      : your running local server (role/db "mnre" on localhost:5432)
#   Redis         : local redis-server on :6379 (Celery broker + live SSE pub/sub)
#   Qdrant        : local qdrant server on :6333 (tools/qdrant binary)
#   FastAPI       : API on :8000
#   Celery worker : threads pool, parallel OCR/ingestion across documents
#   Frontend      : Next.js on :3000
#
# This is the real stack (no eager mode): ingestion is asynchronous and parallel.
#
# Prereqs: Postgres running with the mnre role+db; backend venv created; Qdrant
# binary at tools/qdrant; redis installed (brew install redis).
#
# Usage: ./run-local.sh          (Ctrl-C stops everything it started)

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p data/uploads data/logs data/qdrant-server/storage/collections data/qdrant-server/snapshots

# Shared env for API + worker (override the docker-oriented values in .env).
export POSTGRES_DSN="postgresql://mnre:mnre@localhost:5432/mnre"
export QDRANT_URL="http://localhost:6333"
export REDIS_URL="redis://localhost:6379/0"
export UPLOAD_DIR="$ROOT/data/uploads"
export CELERY_EAGER="false"
export PYTHONPATH="$ROOT/backend"
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY="YES"

PIDS=()
cleanup() { echo; echo "stopping..."; for p in "${PIDS[@]}"; do kill "$p" 2>/dev/null || true; done; }
trap cleanup INT TERM

# 1) Redis
if ! redis-cli ping >/dev/null 2>&1; then
  echo "starting redis..."; redis-server --port 6379 --daemonize yes --dir "$ROOT/data/logs"
fi
echo "redis: $(redis-cli ping)"

# 2) Qdrant server
if ! curl -s http://localhost:6333/healthz >/dev/null 2>&1; then
  echo "starting qdrant..."
  QDRANT__STORAGE__STORAGE_PATH="$ROOT/data/qdrant-server/storage" \
  QDRANT__STORAGE__SNAPSHOTS_PATH="$ROOT/data/qdrant-server/snapshots" \
  QDRANT__SERVICE__HTTP_PORT=6333 \
    nohup "$ROOT/tools/qdrant" > "$ROOT/data/logs/qdrant.log" 2>&1 &
  PIDS+=($!)
  until curl -s http://localhost:6333/healthz >/dev/null 2>&1; do sleep 1; done
fi
echo "qdrant: up"

# 3) FastAPI
echo "starting API on :8000 ..."
backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  > "$ROOT/data/logs/api.log" 2>&1 &
PIDS+=($!)

# 4) Celery worker (threads pool -> parallel, I/O-bound OCR across documents)
echo "starting Celery worker (threads, concurrency=6) ..."
backend/.venv/bin/celery -A app.tasks.celery_app.celery_app worker \
  --pool=threads --concurrency=6 --loglevel=info \
  > "$ROOT/data/logs/worker.log" 2>&1 &
PIDS+=($!)

# 5) Frontend
echo "starting frontend on :3000 ..."
( cd frontend && NEXT_PUBLIC_API_BASE="http://localhost:8000" npm run dev \
  > "$ROOT/data/logs/frontend.log" 2>&1 ) &
PIDS+=($!)

echo
echo "All services starting. Open http://localhost:3000  (Ctrl-C to stop)"
echo "Logs in data/logs/. Postgres is managed separately (brew services)."
wait
