"use client";

import { useEffect, useState } from "react";
import { login } from "@/lib/api";
import Logo from "@/components/Logo";

const KEY = "ragemb_authed";

export function signOut() {
  localStorage.removeItem(KEY);
  location.reload();
}

export default function LoginGate({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setAuthed(localStorage.getItem(KEY) === "1");
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      localStorage.setItem(KEY, "1");
      setAuthed(true);
    } catch (err: any) {
      setError(err.message || "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  if (authed === null) return null; // avoid a flash before we know auth state
  if (authed) return <>{children}</>;

  return (
    <div className="flex h-full items-center justify-center bg-[#f8fafc] p-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm rounded-xl border border-line bg-white p-6 shadow-sm"
      >
        <div className="mb-5 flex items-center gap-2">
          <Logo className="h-7 w-auto" />
          <span className="h-5 w-px bg-line" />
          <span className="font-semibold tracking-tight text-ink">RAG.EMB</span>
        </div>
        <h1 className="text-base font-semibold text-ink">Sign in</h1>
        <p className="mt-1 text-sm text-subtle">
          Enter your credentials to access the sandbox.
        </p>

        <label className="mt-4 block text-xs font-medium text-subtle">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-accent"
          placeholder="you@emb.global"
          required
        />

        <label className="mt-3 block text-xs font-medium text-subtle">
          Password
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="mt-1 w-full rounded-md border border-line px-3 py-2 text-sm outline-none focus:border-accent"
          placeholder="••••••••"
          required
        />

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={busy}
          className="mt-5 w-full rounded-md bg-accent py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
