"use client";

import type { StepEvent } from "@/lib/types";

// Live processing trace shown above each answer (scope §9): every pipeline stage
// with its per-step timing, so the committee sees exactly how the answer formed.
export default function ProcessingTrace({
  steps,
  streaming,
}: {
  steps: StepEvent[];
  streaming: boolean;
}) {
  if (steps.length === 0 && !streaming) return null;
  return (
    <div className="rounded-md border border-line bg-slate-50 px-3 py-2 text-xs">
      <div className="mb-1 font-medium text-subtle">Processing</div>
      <ol className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {steps.map((s, i) => (
          <li key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-slate-300">›</span>}
            <span className="rounded bg-white px-2 py-0.5 text-ink ring-1 ring-line">
              <span className="font-medium">{s.label}</span>
              {s.sublabel && (
                <span className="text-subtle"> · {s.sublabel}</span>
              )}
              <span className="ml-1 tabular-nums text-slate-400">
                {s.elapsed_ms}ms
              </span>
            </span>
          </li>
        ))}
        {streaming && (
          <li className="animate-pulse text-subtle">generating…</li>
        )}
      </ol>
    </div>
  );
}
