"use client";

import { useCallback, useEffect, useState } from "react";
import UploadPanel from "@/components/UploadPanel";
import DocumentList from "@/components/DocumentList";
import ProcessingTrace from "@/components/ProcessingTrace";
import EvidencePanel from "@/components/EvidencePanel";
import AnswerText from "@/components/AnswerText";
import LoginGate, { signOut } from "@/components/LoginGate";
import { listDocuments } from "@/lib/api";
import { streamSSE } from "@/lib/sse";
import type {
  DocumentRecord,
  EvidenceItem,
  GroundingEvent,
  StepEvent,
} from "@/lib/types";

const SUGGESTIONS = [
  "What Central Financial Assistance does PM Surya Ghar provide for rooftop solar?",
  "पीएम सूर्य घर योजना के तहत कितनी केंद्रीय वित्तीय सहायता मिलती है?",
  "What is India's non-fossil power capacity target for 2030?",
  "अपतटीय पवन ऊर्जा के लिए नोडल मंत्रालय और एजेंसी कौन हैं?",
  "What is the total sanctioned capacity across all states?",
  "कोयला आधारित ताप संयंत्रों के लिए न्यूनतम RGO कितना है?",
];

export default function App() {
  // --- Sources (left) ---
  const [docs, setDocs] = useState<DocumentRecord[]>([]);
  const refresh = useCallback(async () => {
    try {
      setDocs(await listDocuments());
    } catch {
      /* backend may still be starting */
    }
  }, []);
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh]);

  // --- Chat (right) ---
  const [query, setQuery] = useState("");
  const [steps, setSteps] = useState<StepEvent[]>([]);
  const [answer, setAnswer] = useState("");
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [grounding, setGrounding] = useState<GroundingEvent | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [asked, setAsked] = useState<string>("");

  async function ask(qArg?: string) {
    const q = (qArg ?? query).trim();
    if (!q || streaming) return;
    setQuery(q);
    setAsked(q);
    setSteps([]);
    setAnswer("");
    setEvidence([]);
    setGrounding(null);
    setStreaming(true);
    try {
      await streamSSE(
        "/query",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
        },
        {
          step: (s: StepEvent) => setSteps((prev) => [...prev, s]),
          token: (t: { delta: string }) => setAnswer((prev) => prev + t.delta),
          evidence: (items: EvidenceItem[]) => setEvidence(items),
          grounding: (g: GroundingEvent) => setGrounding(g),
          done: () => setStreaming(false),
        }
      );
    } catch (e: any) {
      setAnswer(`Error: ${e.message}`);
    } finally {
      setStreaming(false);
    }
  }

  const doneCount = docs.filter((d) => d.status === "done").length;

  return (
    <LoginGate>
    <div className="flex h-full">
      {/* LEFT — Sources */}
      <aside className="flex w-[400px] shrink-0 flex-col border-r border-line bg-white">
        <div className="flex shrink-0 items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold text-ink">Sources</h2>
          <span className="text-xs text-subtle">
            {doneCount}/{docs.length} ready
          </span>
        </div>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <UploadPanel onUploaded={refresh} />
          <DocumentList docs={docs} />
        </div>
      </aside>

      {/* RIGHT — Chat */}
      <section className="flex min-w-0 flex-1 flex-col bg-[#f8fafc]">
        <div className="flex shrink-0 items-center justify-between border-b border-line px-6 py-3">
          <h2 className="text-sm font-semibold text-ink">Chat</h2>
          <button
            onClick={signOut}
            className="text-xs text-subtle hover:text-ink"
          >
            Sign out
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {!asked && !streaming ? (
            <div className="flex h-full items-center justify-center">
              <div className="max-w-md text-center">
                <p className="text-sm text-subtle">
                  Ask a question about your documents in English or Hindi. Each
                  answer shows how it was produced and cites its sources.
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-3xl space-y-4">
              {asked && (
                <div className="text-right">
                  <span className="inline-block rounded-2xl bg-accent px-4 py-2 text-sm text-white">
                    {asked}
                  </span>
                </div>
              )}

              {(steps.length > 0 || streaming) && (
                <ProcessingTrace steps={steps} streaming={streaming} />
              )}

              {(answer || grounding) && (
                <div className="rounded-lg border border-line bg-white p-4">
                  {grounding?.verdict === "no-source" ? (
                    <p className="text-sm text-amber-800">
                      No source in the uploaded documents supports an answer to
                      this question, so nothing is returned.
                    </p>
                  ) : (
                    <>
                      <AnswerText text={answer} onCite={setHighlight} />
                      {grounding?.verdict === "verified" && (
                        <div className="mt-3 inline-flex items-center gap-1 rounded bg-green-50 px-2 py-0.5 text-xs text-green-800">
                          grounded · every claim traces to a source
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {evidence.length > 0 && (
                <EvidencePanel
                  items={evidence}
                  highlight={highlight}
                  onHover={setHighlight}
                />
              )}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="shrink-0 border-t border-line bg-white px-6 py-4">
          <div className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-xl border border-line p-2 focus-within:border-accent">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    ask();
                  }
                }}
                rows={1}
                placeholder="Start typing…"
                className="max-h-40 min-h-[2.25rem] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none"
              />
              <button
                onClick={() => ask()}
                disabled={streaming || !query.trim()}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white disabled:opacity-40"
                aria-label="Send"
              >
                {streaming ? "…" : "→"}
              </button>
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  disabled={streaming}
                  className="rounded-full border border-line bg-white px-3 py-1.5 text-left text-sm text-ink hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
    </LoginGate>
  );
}
