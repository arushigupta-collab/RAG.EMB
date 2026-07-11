"use client";

import { useState } from "react";

// Prefers the real asset at /public/emb-logo.png (drop your file there).
// Falls back to an inline SVG recreation only if that file is missing.
export default function Logo({ className = "" }: { className?: string }) {
  const [useFile, setUseFile] = useState(true);

  if (useFile) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src="/emb-logo.png"
        alt="EMB Global"
        className={className}
        onError={() => setUseFile(false)}
      />
    );
  }

  const petals = [0, 51, 103, 154, 206, 257, 309];
  return (
    <svg
      className={className}
      viewBox="0 0 210 92"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="EMB Global"
    >
      <g fill="#57c46a" transform="translate(2 0)">
        {petals.map((a) => (
          <ellipse
            key={a}
            cx="170"
            cy="14"
            rx="5.2"
            ry="11"
            transform={`rotate(${a} 170 27)`}
          />
        ))}
        <circle cx="170" cy="27" r="4.2" fill="#3aa552" />
      </g>
      <text x="0" y="40" fontFamily="Arial, Helvetica, sans-serif" fontWeight="800" fontSize="40" letterSpacing="-1" fill="#0f172a">EMB</text>
      <text x="0" y="84" fontFamily="Arial, Helvetica, sans-serif" fontWeight="800" fontSize="40" letterSpacing="-1" fill="#0f172a">GLOBAL</text>
    </svg>
  );
}
