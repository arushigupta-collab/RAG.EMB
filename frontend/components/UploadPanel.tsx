"use client";

import { useRef, useState } from "react";
import { uploadFiles } from "@/lib/api";

export default function UploadPanel({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>("");

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setMsg("");
    try {
      const { job_id } = await uploadFiles(Array.from(files));
      setMsg(`Accepted ${files.length} file(s). Processing… (job ${job_id.slice(0, 8)})`);
      onUploaded();
    } catch (e: any) {
      setMsg(`Upload failed: ${e.message}`);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div className="rounded-lg border border-line bg-white p-5">
      <h2 className="font-medium text-ink">Upload documents</h2>
      <p className="mt-1 text-sm text-subtle">
        Select up to 500 files (PDF, Word, PowerPoint, Excel, CSV, images).
        Processing runs in the background; you can watch each file below.
      </p>
      <div className="mt-4">
        <button
          disabled={busy}
          onClick={() => inputRef.current?.click()}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Choose files"}
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {msg && <p className="mt-3 text-sm text-subtle">{msg}</p>}
    </div>
  );
}
