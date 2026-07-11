// Mirrors backend/app/schemas.py (scope §10).

export interface IngestStageSnapshot {
  stage: "classify" | "extract" | "chunk" | "index";
  detail: string;
  status: string;
}

export interface DocumentRecord {
  doc_id: string;
  filename: string;
  fmt: string | null;
  category: string | null;
  status: string;
  classify_method: string | null;
  classify_confidence: number | null;
  extract_method: string | null;
  extract_confidence: number | null;
  low_confidence: boolean;
  chunk_count: number;
  indexed_dense: number;
  indexed_sparse: number;
  rows_to_sql: number;
  error: string | null;
  stages: IngestStageSnapshot[];
}

export interface StepEvent {
  label: string;
  sublabel: string;
  elapsed_ms: number;
}

export interface EvidenceItem {
  n: number;
  document: string;
  section: string;
  page: number | null;
  score: number;
  snippet: string;
}

export interface GroundingEvent {
  verdict: "verified" | "no-source";
  detail: string;
}
