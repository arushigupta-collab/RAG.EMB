"use client";

import { useState } from "react";
import type { DocumentRecord } from "@/lib/types";

const STATUS_COLOR: Record<string, string> = {
  done: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  queued: "bg-slate-100 text-slate-600",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLOR[status] || "bg-amber-100 text-amber-800";
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}

function StageDetail({ doc }: { doc: DocumentRecord }) {
  const stageOrder = ["classify", "extract", "chunk", "index"] as const;
  const byStage = Object.fromEntries(doc.stages.map((s) => [s.stage, s]));
  return (
    <div className="space-y-2 border-t border-line bg-slate-50 px-4 py-3 text-sm">
      {stageOrder.map((name) => {
        const s = byStage[name];
        return (
          <div key={name} className="flex items-start gap-3">
            <span className="w-20 shrink-0 font-medium capitalize text-ink">
              {name}
            </span>
            <span className="text-subtle">
              {s ? s.detail : "—"}
            </span>
          </div>
        );
      })}
      <div className="flex flex-wrap gap-x-6 gap-y-1 pt-2 text-xs text-subtle">
        <span>chunks: {doc.chunk_count}</span>
        <span>
          indexed: {doc.indexed_dense} dense / {doc.indexed_sparse} sparse
        </span>
        {doc.rows_to_sql > 0 && <span>rows→SQL: {doc.rows_to_sql}</span>}
        {doc.classify_confidence != null && (
          <span>
            classify conf: {(doc.classify_confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {doc.error && <p className="pt-1 text-xs text-red-700">Error: {doc.error}</p>}
    </div>
  );
}

export default function DocumentList({ docs }: { docs: DocumentRecord[] }) {
  const [open, setOpen] = useState<string | null>(null);

  if (docs.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-subtle">
        No documents yet. Upload a batch above to begin.
      </p>
    );
  }

  return (
    <div className="divide-y divide-line overflow-hidden rounded-lg border border-line bg-white">
      {docs.map((doc) => (
        <div key={doc.doc_id}>
          <button
            onClick={() => setOpen(open === doc.doc_id ? null : doc.doc_id)}
            className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50"
          >
            <span className="flex-1 truncate text-sm font-medium text-ink">
              {doc.filename}
            </span>
            <span className="text-xs text-subtle">{doc.fmt || "—"}</span>
            <span className="w-40 truncate text-xs text-subtle">
              {doc.category || "—"}
            </span>
            {doc.low_confidence && (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                low-confidence
              </span>
            )}
            <StatusBadge status={doc.status} />
          </button>
          {open === doc.doc_id && <StageDetail doc={doc} />}
        </div>
      ))}
    </div>
  );
}
