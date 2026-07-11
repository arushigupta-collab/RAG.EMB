import "./globals.css";
import type { Metadata } from "next";
import Logo from "@/components/Logo";

export const metadata: Metadata = {
  title: "RAG.EMB",
  description: "EMB Global RAG",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex h-screen flex-col">
          <header className="shrink-0 border-b border-line bg-white">
            <div className="flex items-center gap-3 px-6 py-2.5">
              <Logo className="h-8 w-auto" />
              <span className="h-6 w-px bg-line" />
              <span className="text-lg font-semibold tracking-tight text-ink">
                RAG.EMB
              </span>
            </div>
          </header>
          <main className="min-h-0 flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
