"use client";

import type { EvidenceItem } from "@/lib/types";

// Evidence panel (scope §9): each [n] citation maps here to its source document,
// section, page, relevance score, and the retrieved passage.
export default function EvidencePanel({
  items,
  highlight,
  onHover,
}: {
  items: EvidenceItem[];
  highlight: number | null;
  onHover: (n: number | null) => void;
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-white p-4 text-sm text-subtle">
        Sources will appear here once you ask a question.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium text-ink">Sources</h3>
      {items.map((e) => (
        <div
          key={e.n}
          id={`evidence-${e.n}`}
          onMouseEnter={() => onHover(e.n)}
          onMouseLeave={() => onHover(null)}
          className={`rounded-lg border p-3 text-sm transition ${
            highlight === e.n
              ? "border-accent ring-1 ring-accent"
              : "border-line"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-xs font-semibold text-white">
              {e.n}
            </span>
            <span className="flex-1 truncate font-medium text-ink">
              {e.document}
            </span>
            <span className="text-xs text-subtle">
              {(e.score * 100).toFixed(0)}%
            </span>
          </div>
          <div className="mt-1 text-xs text-subtle">
            {e.section}
            {e.page != null && ` · p.${e.page}`}
          </div>
          <p className="mt-2 border-l-2 border-line pl-2 text-xs text-ink">
            {e.snippet}
          </p>
        </div>
      ))}
    </div>
  );
}
