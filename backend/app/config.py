"""Single source of truth for keys, endpoints, model ids, and thresholds.

Everything is env-driven (scope §15) so the same container runs locally and on
GCP with only environment changes. Nothing here is hardcoded to a secret.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Our settings intentionally start with "model_" (model ids); opt out of
        # pydantic's protected-namespace warning for them.
        protected_namespaces=(),
    )

    # --- App ---
    app_name: str = "MNRE RAG Sandbox"
    environment: str = "local"  # local | gcp
    cors_origins: str = "*"

    # --- Access (simple login gate) --- set via env (.env), never hardcoded.
    auth_email: str = ""
    auth_password: str = ""

    # --- OpenRouter (generation + OCR + classification/Text-to-SQL) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Model ids are placeholders per scope; verify against live OpenRouter slugs.
    model_generation: str = "google/gemini-3.1-pro"          # scope §7 generation
    model_fast: str = "google/gemini-3.5-flash"              # fast tier / classify / Text-to-SQL
    model_ocr: str = "google/gemini-3.1-pro"                 # multimodal OCR
    openrouter_app_url: str = "https://mnre-sandbox.local"   # OpenRouter attribution headers
    openrouter_app_title: str = "MNRE RAG Sandbox"

    # --- Jina (dense embeddings + rerank) ---
    jina_api_key: str = ""
    jina_base_url: str = "https://api.jina.ai/v1"
    jina_embed_model: str = "jina-embeddings-v3"
    jina_embed_dim: int = 1024
    jina_rerank_model: str = "jina-reranker-v2-base-multilingual"
    # jina-embeddings-v3 task adapters:
    jina_task_passage: str = "retrieval.passage"
    jina_task_query: str = "retrieval.query"

    # --- Sparse channel (local, CPU, no GPU) ---
    # BM25 is language-agnostic and matches literal tokens (acronyms, ref numbers,
    # figures, technical English inside Hindi text) verbatim, which suits the
    # multilingual corpus. Swap to "prithivida/Splade_PP_en_v1" for learned sparse.
    sparse_model: str = "Qdrant/bm25"

    # --- Stores ---
    qdrant_url: str = "http://qdrant:6333"
    # If set, use embedded on-disk Qdrant at this path instead of a server
    # (no-Docker local run). Leave empty to use qdrant_url.
    qdrant_local_path: str = ""
    qdrant_collection: str = "mnre_chunks"
    postgres_dsn: str = "postgresql://mnre:mnre@postgres:5432/mnre"

    # --- Celery / Redis ---
    redis_url: str = "redis://redis:6379/0"
    # If true, Celery runs tasks inline in the calling process (no broker/worker),
    # for a single-process local run without Redis.
    celery_eager: bool = False

    # --- Retrieval / generation knobs (scope §6.1, §8) ---
    rrf_k: int = 60
    retrieve_top_k: int = 20        # candidates into re-rank
    rerank_top_k: int = 5           # into generation
    grounding_threshold: float = 0.30  # min rerank score to answer, else withhold

    # --- Chunking (scope §5.1) ---
    chunk_target_tokens: int = 500
    chunk_min_tokens: int = 250
    chunk_max_tokens: int = 1000

    # --- Ingestion ---
    upload_dir: str = "/data/uploads"
    ocr_dpi: int = 300
    ocr_min_dpi: int = 150
    # Max concurrent OCR calls process-wide (bounds per-page fan-out across all
    # documents so the OpenRouter rate limit isn't exceeded).
    ocr_concurrency: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
