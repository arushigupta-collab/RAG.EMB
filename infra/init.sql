-- PostgreSQL schema for the MNRE RAG sandbox (scope §5, §6).
-- Applied automatically by the postgres container on first boot.

CREATE TABLE IF NOT EXISTS documents (
    doc_id              TEXT PRIMARY KEY,
    filename            TEXT NOT NULL,
    fmt                 TEXT,
    category            TEXT,
    status              TEXT NOT NULL DEFAULT 'queued',
    classify_method     TEXT,
    classify_confidence REAL,
    extract_method      TEXT,
    extract_confidence  REAL,
    low_confidence      BOOLEAN NOT NULL DEFAULT FALSE,
    chunk_count         INTEGER NOT NULL DEFAULT 0,
    indexed_dense       INTEGER NOT NULL DEFAULT 0,
    indexed_sparse      INTEGER NOT NULL DEFAULT 0,
    rows_to_sql         INTEGER NOT NULL DEFAULT 0,
    error               TEXT,
    stages              JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Exact numerical/tabular data for the Text-to-SQL path (Financial Data category).
-- row_data holds normalised key/value pairs so heterogeneous sheets share one table.
CREATE TABLE IF NOT EXISTS financial_rows (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    sheet       TEXT,
    row_data    JSONB NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_financial_rows_doc ON financial_rows(doc_id);
CREATE INDEX IF NOT EXISTS idx_financial_rows_data ON financial_rows USING gin (row_data);

-- Action items extracted from meeting minutes (Records and Correspondence).
CREATE TABLE IF NOT EXISTS action_items (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    agenda_item TEXT,
    owner       TEXT,
    action      TEXT,
    due         TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_action_items_doc ON action_items(doc_id);
