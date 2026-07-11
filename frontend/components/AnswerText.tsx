"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders the answer as Markdown (GFM tables, lists, bold) with clickable [n]
// citation chips (scope §9, §10). Citation markers are rewritten to links like
// [n](#cite-n) so they survive Markdown parsing, then rendered as chips that
// highlight/scroll to the matching evidence entry.
export default function AnswerText({
  text,
  onCite,
}: {
  text: string;
  onCite: (n: number | null) => void;
}) {
  const md = text.replace(/\[(\d+)\]/g, "[$1](#cite-$1)");

  return (
    <div className="text-sm leading-relaxed text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            const m = /^#cite-(\d+)$/.exec(href || "");
            if (m) {
              const n = parseInt(m[1], 10);
              return (
                <button
                  onMouseEnter={() => onCite(n)}
                  onMouseLeave={() => onCite(null)}
                  onClick={() => {
                    onCite(n);
                    document
                      .getElementById(`evidence-${n}`)
                      ?.scrollIntoView({ behavior: "smooth", block: "center" });
                  }}
                  className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-accent/10 px-1 align-super text-[10px] font-semibold text-accent hover:bg-accent hover:text-white"
                >
                  {n}
                </button>
              );
            }
            return (
              <a href={href} className="text-accent underline">
                {children}
              </a>
            );
          },
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          ul: ({ children }) => (
            <ul className="mb-2 ml-5 list-disc space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 ml-5 list-decimal space-y-1">{children}</ol>
          ),
          li: ({ children }) => <li>{children}</li>,
          h1: ({ children }) => (
            <h3 className="mb-1 mt-2 font-semibold text-ink">{children}</h3>
          ),
          h2: ({ children }) => (
            <h3 className="mb-1 mt-2 font-semibold text-ink">{children}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="mb-1 mt-2 font-semibold text-ink">{children}</h4>
          ),
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
          th: ({ children }) => (
            <th className="border border-line px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-line px-2 py-1 align-top">{children}</td>
          ),
        }}
      >
        {md}
      </ReactMarkdown>
    </div>
  );
}
